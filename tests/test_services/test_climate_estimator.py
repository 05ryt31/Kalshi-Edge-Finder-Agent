from datetime import date, datetime, timedelta, timezone

import pytest

from src.schemas.market import Market
from src.services.climate_estimator import (
    ClimateEstimator,
    _norm_cdf,
    _prob_observable_at_least,
    _sigma_for_lead,
)
from src.utils.ticker_parser import ClimateTickerInfo


def _make_market(
    *,
    market_type: str = "high_temp",
    threshold: float = 75.0,
    event_date: date | None = None,
    bracket_type: str = "above_equal",
    days_to_close: int = 0,
) -> Market:
    now = datetime.now(timezone.utc)
    info = ClimateTickerInfo(
        market_type=market_type,  # type: ignore[arg-type]
        city_code="NYC",
        event_date=event_date or date.today(),
        threshold=threshold,
        bracket_type=bracket_type,  # type: ignore[arg-type]
    )
    return Market(
        ticker="KXNYCHIGH-TEST",
        event_ticker="EVT",
        title=f"Test {market_type} threshold {threshold}",
        category="climate",
        status="open",
        yes_ask=50,
        no_ask=50,
        yes_bid=49,
        no_bid=49,
        last_price=50,
        volume=500,
        volume_24h=100,
        close_time=now + timedelta(hours=max(1, days_to_close * 24)),
        expiration_time=now + timedelta(hours=max(2, days_to_close * 24 + 1)),
        climate_info=info,
        ticker_date=event_date,
    )


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------


class TestNumericHelpers:
    def test_norm_cdf_at_zero(self):
        assert abs(_norm_cdf(0.0) - 0.5) < 1e-6

    def test_norm_cdf_symmetry(self):
        for z in (0.5, 1.0, 1.96, 2.5):
            assert abs(_norm_cdf(z) + _norm_cdf(-z) - 1.0) < 1e-6

    def test_prob_observable_at_least_above(self):
        # Forecast 80, threshold 75, sigma 3 → very likely above
        p = _prob_observable_at_least(80.0, 75.0, 3.0)
        assert p > 0.9

    def test_prob_observable_at_least_below(self):
        p = _prob_observable_at_least(70.0, 75.0, 3.0)
        assert p < 0.1

    def test_prob_observable_at_least_equal(self):
        # At threshold, prob = 0.5 by symmetry
        p = _prob_observable_at_least(75.0, 75.0, 3.0)
        assert abs(p - 0.5) < 1e-6

    def test_sigma_grows_with_lead(self):
        sigmas = [_sigma_for_lead(h) for h in (1, 5, 10, 24, 36, 100)]
        assert sigmas == sorted(sigmas)


# ---------------------------------------------------------------------------
# High temperature
# ---------------------------------------------------------------------------


class TestHighTempEstimation:
    def setup_method(self):
        self.estimator = ClimateEstimator()

    def test_day_of_running_high_already_exceeds_threshold(self):
        market = _make_market(threshold=75.0, days_to_close=0)
        research = {
            "collected_data": {
                "running_daily_high_f": 80.0,
                "is_day_of_event": True,
            }
        }
        result = self.estimator.estimate(market, research)
        assert result["yes_probability"] >= 0.95
        assert result["confidence"] >= 0.9
        assert "exceeds threshold" in result["reasoning"]

    def test_day_of_running_high_far_below_threshold(self):
        # Running high 60F vs threshold 80F, no forecast → should be near 0.
        market = _make_market(threshold=80.0, days_to_close=0)
        research = {
            "collected_data": {
                "running_daily_high_f": 60.0,
                "is_day_of_event": True,
            }
        }
        result = self.estimator.estimate(market, research)
        assert result["yes_probability"] < 0.1

    def test_day_of_with_forecast_combines_running_and_peak(self):
        market = _make_market(threshold=78.0, days_to_close=0)
        research = {
            "collected_data": {
                "running_daily_high_f": 76.0,
                "is_day_of_event": True,
                "forecast": [
                    {"time": "now", "temp": 79.0, "conditions": "sunny"},
                    {"time": "+3h", "temp": 80.0, "conditions": "sunny"},
                ],
            }
        }
        result = self.estimator.estimate(market, research)
        # Peak estimate = max(76, 80) = 80 vs threshold 78 → > 0.5
        assert result["yes_probability"] > 0.5
        assert result["confidence"] > 0.5

    def test_future_event_uses_forecast_only(self):
        market = _make_market(threshold=75.0, days_to_close=2)
        research = {
            "collected_data": {
                "is_day_of_event": False,
                "forecast": [
                    {"time": "+24h", "temp": 76.0, "conditions": "sunny"},
                    {"time": "+48h", "temp": 78.0, "conditions": "sunny"},
                ],
            }
        }
        result = self.estimator.estimate(market, research)
        # Forecast peak 78 vs threshold 75, sigma ~3.5F → yes prob > 0.5 but not certain
        assert 0.5 < result["yes_probability"] < 0.95

    def test_no_signal_returns_uncertain(self):
        market = _make_market(threshold=75.0, days_to_close=0)
        research = {"collected_data": {"is_day_of_event": True}}
        result = self.estimator.estimate(market, research)
        assert result["confidence"] == 0.0
        assert result["yes_probability"] == 0.5


# ---------------------------------------------------------------------------
# Low temperature
# ---------------------------------------------------------------------------


class TestLowTempEstimation:
    def setup_method(self):
        self.estimator = ClimateEstimator()

    def test_day_of_running_low_already_below_threshold(self):
        # Threshold 40F (low must stay >=40 for YES); running low 30F → already failed.
        market = _make_market(market_type="low_temp", threshold=40.0)
        research = {
            "collected_data": {
                "running_daily_low_f": 30.0,
                "is_day_of_event": True,
            }
        }
        result = self.estimator.estimate(market, research)
        assert result["yes_probability"] <= 0.1
        assert result["confidence"] >= 0.9

    def test_day_of_running_low_above_threshold_with_forecast(self):
        market = _make_market(market_type="low_temp", threshold=40.0)
        research = {
            "collected_data": {
                "running_daily_low_f": 45.0,
                "is_day_of_event": True,
                "forecast": [
                    {"time": "+3h", "temp": 50.0},
                    {"time": "+6h", "temp": 48.0},
                ],
            }
        }
        result = self.estimator.estimate(market, research)
        # min(running_low=45, forecast_min=48) = 45 vs threshold 40 → high YES
        assert result["yes_probability"] > 0.7


# ---------------------------------------------------------------------------
# Concluded
# ---------------------------------------------------------------------------


class TestConcludedEstimation:
    def setup_method(self):
        self.estimator = ClimateEstimator()

    def test_concluded_high_temp_yes(self):
        market = _make_market(threshold=75.0, event_date=date(2026, 1, 1))
        research = {
            "collected_data": {
                "event_concluded": True,
                "official_data_missing": False,
                "cli_high": 80.0,
            }
        }
        result = self.estimator.estimate(market, research)
        assert result["yes_probability"] >= 0.95
        assert result["confidence"] >= 0.95

    def test_concluded_high_temp_no(self):
        market = _make_market(threshold=75.0, event_date=date(2026, 1, 1))
        research = {
            "collected_data": {
                "event_concluded": True,
                "official_data_missing": False,
                "cli_high": 70.0,
            }
        }
        result = self.estimator.estimate(market, research)
        assert result["yes_probability"] <= 0.05

    def test_concluded_missing_data_returns_uncertain(self):
        market = _make_market(threshold=75.0, event_date=date(2026, 1, 1))
        research = {
            "collected_data": {
                "event_concluded": True,
                "official_data_missing": True,
            }
        }
        result = self.estimator.estimate(market, research)
        assert result["confidence"] == 0.0


# ---------------------------------------------------------------------------
# Snow / rain
# ---------------------------------------------------------------------------


class TestPrecipEstimation:
    def setup_method(self):
        self.estimator = ClimateEstimator()

    def test_day_of_snow_already_exceeded(self):
        market = _make_market(market_type="snow", threshold=2.0)
        research = {
            "collected_data": {
                "is_day_of_event": True,
                "cli_snow": 3.5,
            }
        }
        result = self.estimator.estimate(market, research)
        assert result["yes_probability"] >= 0.95

    def test_precip_without_signal_returns_uncertain(self):
        market = _make_market(market_type="rain", threshold=0.5)
        research = {"collected_data": {"is_day_of_event": False}}
        result = self.estimator.estimate(market, research)
        assert result["confidence"] == 0.0


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


class TestRouterIntegration:
    @pytest.mark.asyncio
    async def test_estimator_routes_climate_market_to_physics(self):
        from src.services.estimator import ProbabilityEstimator

        # Crash if it tries to call an LLM.
        class ExplodingLLM:
            async def estimate_probability(self, *args, **kwargs):
                raise RuntimeError("LLM should not be called for climate markets")

        estimator = ProbabilityEstimator(llm_client=ExplodingLLM())  # type: ignore[arg-type]
        market = _make_market(threshold=75.0, days_to_close=0)
        research = {
            "collected_data": {
                "running_daily_high_f": 80.0,
                "is_day_of_event": True,
            }
        }
        result = await estimator.estimate(market, research)
        assert result["yes_probability"] >= 0.95
        assert "exceeds threshold" in result["reasoning"]
