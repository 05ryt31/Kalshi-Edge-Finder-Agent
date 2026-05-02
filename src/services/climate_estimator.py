"""Physics + statistics-based probability estimation for climate markets.

Replaces LLM-based estimation for climate/weather markets, where the
underlying random variable is a physical observable with known measurement
infrastructure (NWS ASOS / CLI) and characterizable forecast error.

Phase 2b additions:
- Optional ClimatologyService injection for empirically-derived sigmas.
- Combined sigma blends short-term forecast skill with long-term
  climatological variability:
      effective_sigma = sqrt(forecast_sigma**2 + (alpha * climo_std)**2)
  where alpha shrinks toward 0 as we get closer to the event (forecast
  becomes more informative) and toward 1 far out (climatology dominates).
- Climatological prior fallback when forecast data is missing entirely.
"""

from __future__ import annotations

from datetime import date as date_t, datetime, timezone
from math import erf, sqrt
from typing import Any, Protocol

from src.schemas.market import Market
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Forecast error standard deviations (degrees F) by lead time bucket.
# Rough NWS gridpoint forecast verification numbers — will be refined per
# (city, lead) by paper-trade calibration in 2c.
FORECAST_SIGMA_BY_LEAD_HOURS: list[tuple[float, float]] = [
    (3.0, 1.5),     # within 3 hours
    (6.0, 2.0),     # within 6 hours
    (12.0, 2.5),    # within 12 hours
    (24.0, 3.0),    # within 1 day
    (48.0, 3.5),    # within 2 days
]
DEFAULT_FAR_SIGMA = 4.5  # > 2 days out


class ClimatologyProvider(Protocol):
    """Sync-friendly view of ClimatologyService used by the estimator.

    Returns (mean, std) for the (station, calendar_day, market_type) cell,
    or None if no climatology is available.
    """

    async def get(
        self, station: str, target_date: date_t, market_type: str
    ) -> Any | None: ...


def _sigma_for_lead(hours_to_event: float) -> float:
    for boundary, sigma in FORECAST_SIGMA_BY_LEAD_HOURS:
        if hours_to_event <= boundary:
            return sigma
    return DEFAULT_FAR_SIGMA


def _climo_alpha(hours_to_event: float) -> float:
    """How much weight to put on climatological variance.

    0 at the event itself (NWS in-day observations dominate), grows to 1.0
    when we're > 5 days out. Linear ramp from 0 → 1 over 0-120h.
    """
    if hours_to_event <= 0:
        return 0.0
    if hours_to_event >= 120.0:
        return 1.0
    return hours_to_event / 120.0


def _norm_cdf(z: float) -> float:
    """Standard normal CDF using erf (no scipy dependency)."""
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))


def _prob_observable_at_least(
    forecast_value: float, threshold: float, sigma: float
) -> float:
    """P(X >= threshold) for X ~ Normal(forecast_value, sigma)."""
    if sigma <= 0:
        return 1.0 if forecast_value >= threshold else 0.0
    z = (threshold - forecast_value) / sigma
    return 1.0 - _norm_cdf(z)


def _clip_prob(p: float) -> float:
    """Avoid 0 / 1 outputs to keep downstream Kelly math stable."""
    return max(0.005, min(0.995, p))


def _combined_sigma(forecast_sigma: float, climo_std: float | None, alpha: float) -> float:
    """Blend forecast and climatological variance.

    sigma_eff = sqrt(forecast_sigma^2 + (alpha * climo_std)^2)

    Climatology *adds* uncertainty rather than replacing it: even with a
    point forecast, real outcomes wander around its mean by at least the
    weather variability characteristic of that calendar day.
    """
    if climo_std is None or climo_std <= 0 or alpha <= 0:
        return forecast_sigma
    return sqrt(forecast_sigma * forecast_sigma + (alpha * climo_std) * (alpha * climo_std))


class ClimateEstimator:
    """Physics-based estimator for climate markets.

    Async because climatology lookups hit the DB. estimate() returns the
    same dict shape as the LLM-based ProbabilityEstimator for drop-in
    compatibility:
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

    def __init__(self, climatology: ClimatologyProvider | None = None) -> None:
        self.climatology = climatology

    async def estimate(self, market: Market, research_data: dict[str, Any]) -> dict:
        info = market.climate_info
        if info is None:
            return self._uncertain("no_climate_info")

        # Phase 2a only handles 'above_equal' bracket semantics.
        if info.bracket_type != "above_equal":
            return self._uncertain(f"unsupported_bracket:{info.bracket_type}")

        collected = research_data.get("collected_data", {})

        if collected.get("event_concluded"):
            return self._estimate_concluded(market, collected)

        market_type = info.market_type
        climo = await self._lookup_climatology(market, market_type)

        if market_type == "high_temp":
            return self._estimate_high_temp(market, collected, climo)
        if market_type == "low_temp":
            return self._estimate_low_temp(market, collected, climo)
        if market_type in ("snow", "rain"):
            return self._estimate_precip(market, collected, climo)

        return self._uncertain(f"unsupported_market_type:{market_type}")

    # ------------------------------------------------------------------
    # Climatology lookup
    # ------------------------------------------------------------------

    async def _lookup_climatology(
        self, market: Market, market_type: str
    ) -> Any | None:
        if self.climatology is None:
            return None
        info = market.climate_info
        target = info.event_date or market.close_time.date()
        from src.utils.ticker_parser import get_nws_station

        station = get_nws_station(info.city_code)
        if station is None:
            return None
        try:
            return await self.climatology.get(station, target, market_type)
        except Exception as e:
            logger.warning(
                "climatology_lookup_failed",
                station=station,
                market_type=market_type,
                error=str(e),
            )
            return None

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
        return _result(
            yes=yes,
            confidence=0.99,
            reasoning=(
                f"Concluded event. CLI observed {market_type}={observed} vs "
                f"threshold {threshold}. Resolution effectively known."
            ),
        )

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
        return 0.99 if observed >= threshold else 0.01

    # ------------------------------------------------------------------
    # High temperature
    # ------------------------------------------------------------------

    def _estimate_high_temp(
        self, market: Market, collected: dict, climo: Any
    ) -> dict:
        info = market.climate_info
        threshold = info.threshold
        running_high = collected.get("running_daily_high_f")
        forecast_high = self._forecast_peak_high(collected)
        is_day_of = collected.get("is_day_of_event") or market.is_day_of_event
        hours_left = self._hours_to_close(market)
        climo_std = climo.std if climo is not None else None

        # Day-of decisive
        if running_high is not None and is_day_of:
            margin = running_high - threshold
            if margin >= self.ASOS_DECISIVE_MARGIN_F:
                return _result(
                    yes=0.97,
                    confidence=0.95,
                    reasoning=(
                        f"Day-of: ASOS running high {running_high}F exceeds "
                        f"threshold {threshold}F by {margin:.1f}F."
                    ),
                )

        # Day-of with forecast
        if running_high is not None and is_day_of and forecast_high is not None:
            peak_estimate = max(running_high, forecast_high)
            base_sigma = _sigma_for_lead(hours_left)
            sigma = _combined_sigma(base_sigma, climo_std, _climo_alpha(hours_left))
            yes = _prob_observable_at_least(peak_estimate, threshold, sigma)
            return _result(
                yes=yes,
                confidence=0.85,
                reasoning=(
                    f"Day-of: running high {running_high}F, forecast peak "
                    f"{forecast_high}F, threshold {threshold}F, "
                    f"sigma {sigma:.2f}F (climo_std={climo_std})."
                ),
            )

        # Day-of without forecast
        if running_high is not None and is_day_of:
            sigma = _combined_sigma(2.0, climo_std, _climo_alpha(hours_left))
            yes = _prob_observable_at_least(running_high, threshold, sigma)
            return _result(
                yes=yes,
                confidence=0.70,
                reasoning=(
                    f"Day-of: running high {running_high}F, no forecast, "
                    f"sigma {sigma:.2f}F (heuristic+climo)."
                ),
            )

        # Future event with forecast
        if forecast_high is not None:
            base_sigma = _sigma_for_lead(hours_left)
            sigma = _combined_sigma(base_sigma, climo_std, _climo_alpha(hours_left))
            yes = _prob_observable_at_least(forecast_high, threshold, sigma)
            return _result(
                yes=yes,
                confidence=0.65,
                reasoning=(
                    f"Future: forecast high {forecast_high}F vs threshold "
                    f"{threshold}F, sigma {sigma:.2f}F (climo_std={climo_std})."
                ),
            )

        # Climatological-only fallback (no forecast, no running high).
        # Confidence is intentionally low so DecisionEngine declines unless
        # the threshold is far from the climo mean.
        if climo is not None:
            yes = _prob_observable_at_least(climo.mean, threshold, climo.std)
            return _result(
                yes=yes,
                confidence=0.45,
                reasoning=(
                    f"Climatology-only: 30y mean high {climo.mean:.1f}F, "
                    f"std {climo.std:.2f}F, threshold {threshold}F."
                ),
            )

        return self._uncertain("no_high_temp_signal")

    # ------------------------------------------------------------------
    # Low temperature
    # ------------------------------------------------------------------

    def _estimate_low_temp(
        self, market: Market, collected: dict, climo: Any
    ) -> dict:
        info = market.climate_info
        threshold = info.threshold
        running_low = collected.get("running_daily_low_f")
        forecast_low = self._forecast_min_low(collected)
        is_day_of = collected.get("is_day_of_event") or market.is_day_of_event
        hours_left = self._hours_to_close(market)
        climo_std = climo.std if climo is not None else None

        if running_low is not None and is_day_of:
            if threshold - running_low >= self.ASOS_DECISIVE_MARGIN_F:
                return _result(
                    yes=0.03,
                    confidence=0.95,
                    reasoning=(
                        f"Day-of: ASOS running low {running_low}F below "
                        f"threshold {threshold}F by "
                        f"{threshold - running_low:.1f}F."
                    ),
                )

        if running_low is not None and is_day_of and forecast_low is not None:
            min_estimate = min(running_low, forecast_low)
            base_sigma = _sigma_for_lead(hours_left)
            sigma = _combined_sigma(base_sigma, climo_std, _climo_alpha(hours_left))
            yes = _prob_observable_at_least(min_estimate, threshold, sigma)
            return _result(
                yes=yes,
                confidence=0.85,
                reasoning=(
                    f"Day-of: running low {running_low}F, forecast min "
                    f"{forecast_low}F, threshold {threshold}F, sigma {sigma:.2f}F."
                ),
            )

        if running_low is not None and is_day_of:
            sigma = _combined_sigma(2.0, climo_std, _climo_alpha(hours_left))
            yes = _prob_observable_at_least(running_low, threshold, sigma)
            return _result(
                yes=yes,
                confidence=0.70,
                reasoning=(
                    f"Day-of: running low {running_low}F, no forecast, "
                    f"sigma {sigma:.2f}F."
                ),
            )

        if forecast_low is not None:
            base_sigma = _sigma_for_lead(hours_left)
            sigma = _combined_sigma(base_sigma, climo_std, _climo_alpha(hours_left))
            yes = _prob_observable_at_least(forecast_low, threshold, sigma)
            return _result(
                yes=yes,
                confidence=0.65,
                reasoning=(
                    f"Future: forecast low {forecast_low}F vs threshold "
                    f"{threshold}F, sigma {sigma:.2f}F."
                ),
            )

        if climo is not None:
            yes = _prob_observable_at_least(climo.mean, threshold, climo.std)
            return _result(
                yes=yes,
                confidence=0.45,
                reasoning=(
                    f"Climatology-only: 30y mean low {climo.mean:.1f}F, "
                    f"std {climo.std:.2f}F, threshold {threshold}F."
                ),
            )

        return self._uncertain("no_low_temp_signal")

    # ------------------------------------------------------------------
    # Snow / rain
    # ------------------------------------------------------------------

    def _estimate_precip(
        self, market: Market, collected: dict, climo: Any
    ) -> dict:
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
                        f"Day-of: CLI {market_type} {observed} exceeds "
                        f"threshold {threshold}."
                    ),
                )

        # Climatological prior — precip distribution is heavy-tailed, so
        # confidence stays low. DecisionEngine will only act if threshold
        # is far in the tail relative to climo mean.
        if climo is not None and climo.std > 0:
            yes = _prob_observable_at_least(climo.mean, threshold, climo.std)
            return _result(
                yes=yes,
                confidence=0.40,
                reasoning=(
                    f"Climatology-only ({market_type}): mean {climo.mean:.2f}, "
                    f"std {climo.std:.2f}, threshold {threshold}."
                ),
            )

        return self._uncertain(f"{market_type}_no_signal")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _forecast_peak_high(collected: dict) -> float | None:
        forecast = collected.get("forecast")
        if not forecast:
            return None
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
