"""Physics + statistics-based probability estimation for climate markets.

Replaces LLM-based estimation for climate/weather markets, where the
underlying random variable is a physical observable with known measurement
infrastructure (NWS ASOS / CLI) and characterizable forecast error.

Why not LLM here:
- Markets like "high temp >= 75F in NYC tomorrow" have a real probability
  governed by the forecast distribution, not by language reasoning.
- ASOS running_high vs threshold gives near-deterministic resolution intra-day.
- Forecast error is well-characterized empirically (~2-3F MAE day-ahead).

Phase 2a uses hardcoded forecast-error sigmas. Phase 2b will replace these
with NOAA-derived empirical distributions per (city, lead_time).
"""

from __future__ import annotations

from math import erf, sqrt
from typing import Any

from src.schemas.market import Market
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Forecast error standard deviations (degrees F) by lead time bucket.
# Sourced from typical NWS gridpoint forecast verification: ~1.5F at 0-6h,
# growing to ~3.5F at 48h+. Will be replaced with empirical NOAA data in 2b.
FORECAST_SIGMA_BY_LEAD_HOURS: list[tuple[float, float]] = [
    (3.0, 1.5),     # within 3 hours
    (6.0, 2.0),     # within 6 hours
    (12.0, 2.5),    # within 12 hours
    (24.0, 3.0),    # within 1 day
    (48.0, 3.5),    # within 2 days
]
DEFAULT_FAR_SIGMA = 4.5  # > 2 days out


def _sigma_for_lead(hours_to_event: float) -> float:
    for boundary, sigma in FORECAST_SIGMA_BY_LEAD_HOURS:
        if hours_to_event <= boundary:
            return sigma
    return DEFAULT_FAR_SIGMA


def _norm_cdf(z: float) -> float:
    """Standard normal CDF using erf (no scipy dependency)."""
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))


def _prob_observable_at_least(
    forecast_value: float, threshold: float, sigma: float
) -> float:
    """P(X >= threshold) for X ~ Normal(forecast_value, sigma).

    Returns 1 - Phi((threshold - forecast) / sigma).
    """
    if sigma <= 0:
        return 1.0 if forecast_value >= threshold else 0.0
    z = (threshold - forecast_value) / sigma
    return 1.0 - _norm_cdf(z)


def _clip_prob(p: float) -> float:
    """Avoid 0 / 1 outputs to keep downstream Kelly math stable."""
    return max(0.005, min(0.995, p))


class ClimateEstimator:
    """Physics-based estimator for climate markets.

    estimate(market, research_data) returns the same dict shape as the
    LLM-based ProbabilityEstimator for drop-in compatibility:
        {
            "yes_probability": float,
            "no_probability": float,
            "confidence": float,
            "reasoning": str,
        }
    """

    # When ASOS running high already crosses threshold by this margin,
    # treat as effectively resolved (CLI vs ASOS may differ by ~1F).
    ASOS_DECISIVE_MARGIN_F = 1.5

    def estimate(self, market: Market, research_data: dict[str, Any]) -> dict:
        info = market.climate_info
        if info is None:
            return self._uncertain("no_climate_info")

        # Phase 2a only handles 'above_equal' bracket semantics
        # (resolves YES iff observed >= threshold). Between/under brackets
        # need different logic and are deferred to a follow-up.
        if info.bracket_type != "above_equal":
            return self._uncertain(f"unsupported_bracket:{info.bracket_type}")

        collected = research_data.get("collected_data", {})

        # Concluded events: trust CLI report only.
        if collected.get("event_concluded"):
            return self._estimate_concluded(market, collected)

        market_type = info.market_type

        if market_type == "high_temp":
            return self._estimate_high_temp(market, collected)
        if market_type == "low_temp":
            return self._estimate_low_temp(market, collected)
        if market_type in ("snow", "rain"):
            return self._estimate_precip(market, collected)

        return self._uncertain(f"unsupported_market_type:{market_type}")

    # ------------------------------------------------------------------
    # Concluded
    # ------------------------------------------------------------------

    def _estimate_concluded(self, market: Market, collected: dict) -> dict:
        info = market.climate_info
        threshold = info.threshold
        market_type = info.market_type

        if collected.get("official_data_missing", True):
            return self._uncertain("concluded_no_cli_data")

        observed = self._observed_value_for_concluded(market_type, collected)
        if observed is None:
            return self._uncertain("concluded_no_observed_value")

        yes = self._yes_prob_from_observed(market_type, observed, threshold)
        return {
            "yes_probability": _clip_prob(yes),
            "no_probability": _clip_prob(1 - yes),
            "confidence": 0.99,
            "reasoning": (
                f"Concluded event. CLI observed {market_type}={observed} vs "
                f"threshold {threshold}. Resolution effectively known."
            ),
        }

    @staticmethod
    def _observed_value_for_concluded(market_type: str, collected: dict) -> float | None:
        if market_type == "high_temp":
            return collected.get("cli_high")
        if market_type == "low_temp":
            return collected.get("cli_low")
        if market_type == "snow":
            return collected.get("cli_snow")
        if market_type == "rain":
            return collected.get("cli_precip")
        return None

    @staticmethod
    def _yes_prob_from_observed(market_type: str, observed: float, threshold: float) -> float:
        # All four supported market types resolve YES when observed >= threshold
        # under the "above_equal" bracket. Bracket nuances (between/under) are
        # not yet handled — return 0.5 in unsupported brackets via caller.
        if market_type in ("high_temp", "snow", "rain"):
            return 0.99 if observed >= threshold else 0.01
        if market_type == "low_temp":
            # low_temp "above_equal" semantically means low temp >= threshold,
            # i.e. it didn't get colder than threshold.
            return 0.99 if observed >= threshold else 0.01
        return 0.5

    # ------------------------------------------------------------------
    # High temperature
    # ------------------------------------------------------------------

    def _estimate_high_temp(self, market: Market, collected: dict) -> dict:
        info = market.climate_info
        threshold = info.threshold
        running_high = collected.get("running_daily_high_f")
        forecast_high = self._forecast_peak_high(collected)
        is_day_of = collected.get("is_day_of_event") or market.is_day_of_event

        # Day-of decisive: ASOS running high already past threshold.
        if running_high is not None and is_day_of:
            margin = running_high - threshold
            if margin >= self.ASOS_DECISIVE_MARGIN_F:
                return _result(
                    yes=0.97,
                    confidence=0.95,
                    reasoning=(
                        f"Day-of: ASOS running high {running_high}F already exceeds "
                        f"threshold {threshold}F by {margin:.1f}F. Near-certain YES."
                    ),
                )

        # Day-of: running_high known but below threshold; estimate remaining peak.
        if running_high is not None and is_day_of and forecast_high is not None:
            peak_estimate = max(running_high, forecast_high)
            sigma = _sigma_for_lead(self._hours_to_close(market))
            yes = _prob_observable_at_least(peak_estimate, threshold, sigma)
            return _result(
                yes=yes,
                confidence=0.85,
                reasoning=(
                    f"Day-of: running high {running_high}F, forecast peak "
                    f"{forecast_high}F, threshold {threshold}F, sigma {sigma}F."
                ),
            )

        # Day-of without forecast: rely on running high vs threshold + small sigma
        if running_high is not None and is_day_of:
            sigma = 2.0
            yes = _prob_observable_at_least(running_high, threshold, sigma)
            return _result(
                yes=yes,
                confidence=0.70,
                reasoning=(
                    f"Day-of: running high {running_high}F, no forecast, "
                    f"threshold {threshold}F, sigma {sigma}F (heuristic)."
                ),
            )

        # Future event: pure forecast.
        if forecast_high is not None:
            sigma = _sigma_for_lead(self._hours_to_close(market))
            yes = _prob_observable_at_least(forecast_high, threshold, sigma)
            return _result(
                yes=yes,
                confidence=0.65,
                reasoning=(
                    f"Future: forecast high {forecast_high}F vs threshold "
                    f"{threshold}F, sigma {sigma}F."
                ),
            )

        return self._uncertain("no_high_temp_signal")

    # ------------------------------------------------------------------
    # Low temperature
    # ------------------------------------------------------------------

    def _estimate_low_temp(self, market: Market, collected: dict) -> dict:
        info = market.climate_info
        threshold = info.threshold
        running_low = collected.get("running_daily_low_f")
        forecast_low = self._forecast_min_low(collected)
        is_day_of = collected.get("is_day_of_event") or market.is_day_of_event

        # Day-of decisive: running_low already < threshold by margin → YES (low >= threshold) is dead.
        if running_low is not None and is_day_of:
            if threshold - running_low >= self.ASOS_DECISIVE_MARGIN_F:
                return _result(
                    yes=0.03,
                    confidence=0.95,
                    reasoning=(
                        f"Day-of: ASOS running low {running_low}F already below "
                        f"threshold {threshold}F by "
                        f"{threshold - running_low:.1f}F. Near-certain NO."
                    ),
                )

        if running_low is not None and is_day_of and forecast_low is not None:
            # Realized minimum is min(running_low, future_low).
            min_estimate = min(running_low, forecast_low)
            sigma = _sigma_for_lead(self._hours_to_close(market))
            # YES = (low_temp_realized >= threshold)
            yes = _prob_observable_at_least(min_estimate, threshold, sigma)
            return _result(
                yes=yes,
                confidence=0.85,
                reasoning=(
                    f"Day-of: running low {running_low}F, forecast min "
                    f"{forecast_low}F, threshold {threshold}F, sigma {sigma}F."
                ),
            )

        if running_low is not None and is_day_of:
            sigma = 2.0
            yes = _prob_observable_at_least(running_low, threshold, sigma)
            return _result(
                yes=yes,
                confidence=0.70,
                reasoning=(
                    f"Day-of: running low {running_low}F, no forecast, sigma {sigma}F."
                ),
            )

        if forecast_low is not None:
            sigma = _sigma_for_lead(self._hours_to_close(market))
            yes = _prob_observable_at_least(forecast_low, threshold, sigma)
            return _result(
                yes=yes,
                confidence=0.65,
                reasoning=(
                    f"Future: forecast low {forecast_low}F vs threshold "
                    f"{threshold}F, sigma {sigma}F."
                ),
            )

        return self._uncertain("no_low_temp_signal")

    # ------------------------------------------------------------------
    # Snow / rain
    # ------------------------------------------------------------------

    def _estimate_precip(self, market: Market, collected: dict) -> dict:
        info = market.climate_info
        threshold = info.threshold
        market_type = info.market_type
        is_day_of = collected.get("is_day_of_event") or market.is_day_of_event

        observed_key = "cli_snow" if market_type == "snow" else "cli_precip"
        observed = collected.get(observed_key)

        if observed is not None and is_day_of:
            if observed >= threshold:
                return _result(
                    yes=0.97,
                    confidence=0.90,
                    reasoning=(
                        f"Day-of: CLI {market_type} {observed} already exceeds "
                        f"threshold {threshold}. Near-certain YES."
                    ),
                )

        # No reliable forecast pipeline for precip yet — return uncertain so
        # DecisionEngine declines to bet. Phase 2b adds NWS quantitative
        # precipitation forecast (QPF) with empirical sigma.
        return self._uncertain(f"{market_type}_forecast_unavailable")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _forecast_peak_high(collected: dict) -> float | None:
        forecast = collected.get("forecast")
        if not forecast:
            return None
        # forecast is a list of {time, temp, conditions} from weather.py
        try:
            temps = [item["temp"] for item in forecast if item.get("temp") is not None]
            return max(temps) if temps else None
        except (TypeError, KeyError):
            return None

    @staticmethod
    def _forecast_min_low(collected: dict) -> float | None:
        forecast = collected.get("forecast")
        if not forecast:
            return None
        try:
            temps = [item["temp"] for item in forecast if item.get("temp") is not None]
            return min(temps) if temps else None
        except (TypeError, KeyError):
            return None

    @staticmethod
    def _hours_to_close(market: Market) -> float:
        from datetime import datetime, timezone

        delta = market.close_time - datetime.now(timezone.utc)
        return max(0.0, delta.total_seconds() / 3600.0)

    @staticmethod
    def _uncertain(reason: str) -> dict:
        return {
            "yes_probability": 0.5,
            "no_probability": 0.5,
            "confidence": 0.0,
            "reasoning": f"Insufficient signal for physics estimate: {reason}",
        }


def _result(*, yes: float, confidence: float, reasoning: str) -> dict:
    yes = _clip_prob(yes)
    return {
        "yes_probability": yes,
        "no_probability": _clip_prob(1 - yes),
        "confidence": float(confidence),
        "reasoning": reasoning,
    }
