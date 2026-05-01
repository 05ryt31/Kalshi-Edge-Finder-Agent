from datetime import date, datetime, timedelta, timezone

from src.schemas.market import Market
from src.schemas.settings import Settings
from src.services.decision import DecisionEngine
from src.utils.ticker_parser import ClimateTickerInfo


def _make_market(
    *,
    yes_ask: int = 30,
    no_ask: int = 70,
    climate_info: ClimateTickerInfo | None = None,
    ticker_date: date | None = None,
    category: str = "climate",
) -> Market:
    now = datetime.now(timezone.utc)
    return Market(
        ticker="TEST-MKT",
        event_ticker="TEST-EVT",
        title="Test Market",
        category=category,
        status="open",
        yes_ask=yes_ask,
        no_ask=no_ask,
        yes_bid=max(yes_ask - 1, 0),
        no_bid=max(no_ask - 1, 0),
        last_price=yes_ask,
        volume=500,
        volume_24h=100,
        close_time=now + timedelta(days=3),
        expiration_time=now + timedelta(days=4),
        climate_info=climate_info,
        ticker_date=ticker_date,
    )


class TestDecisionEngine:
    def setup_method(self):
        self.settings = Settings()
        self.engine = DecisionEngine(self.settings)

    def test_strong_recommendation(self):
        market = _make_market(yes_ask=30, no_ask=70)
        estimate = {
            "yes_probability": 0.70,
            "no_probability": 0.30,
            "confidence": 0.85,
            "reasoning": "Strong signal",
        }
        rec = self.engine.evaluate(market, estimate, {})
        assert rec is not None
        assert rec.strength == "strong"
        assert rec.side == "yes"
        assert rec.edge >= 0.30

    def test_medium_recommendation(self):
        market = _make_market(yes_ask=30, no_ask=70)
        estimate = {
            "yes_probability": 0.55,
            "no_probability": 0.45,
            "confidence": 0.65,
            "reasoning": "Moderate signal",
        }
        rec = self.engine.evaluate(market, estimate, {})
        assert rec is not None
        assert rec.strength == "medium"

    def test_weak_recommendation(self):
        market = _make_market(yes_ask=30, no_ask=70)
        estimate = {
            "yes_probability": 0.50,
            "no_probability": 0.50,
            "confidence": 0.55,
            "reasoning": "Weak signal",
        }
        rec = self.engine.evaluate(market, estimate, {})
        assert rec is not None
        assert rec.strength == "weak"

    def test_no_recommendation_low_edge(self):
        market = _make_market(yes_ask=50, no_ask=50)
        estimate = {
            "yes_probability": 0.55,
            "no_probability": 0.45,
            "confidence": 0.50,
            "reasoning": "Low edge",
        }
        rec = self.engine.evaluate(market, estimate, {})
        assert rec is None

    def test_selects_no_side_when_better(self):
        market = _make_market(yes_ask=80, no_ask=20)
        estimate = {
            "yes_probability": 0.15,
            "no_probability": 0.85,
            "confidence": 0.85,
            "reasoning": "NO is better",
        }
        rec = self.engine.evaluate(market, estimate, {})
        assert rec is not None
        assert rec.side == "no"

    def test_position_size_scales_with_strength(self):
        market = _make_market(yes_ask=20, no_ask=80)

        strong_estimate = {
            "yes_probability": 0.70,
            "no_probability": 0.30,
            "confidence": 0.90,
            "reasoning": "Strong",
        }
        weak_estimate = {
            "yes_probability": 0.42,
            "no_probability": 0.58,
            "confidence": 0.52,
            "reasoning": "Weak",
        }

        strong_rec = self.engine.evaluate(market, strong_estimate, {})
        weak_rec = self.engine.evaluate(market, weak_estimate, {})

        assert strong_rec is not None
        assert weak_rec is not None
        assert strong_rec.suggested_amount > weak_rec.suggested_amount


class TestExtremePriceBlock:
    """Test _should_block_extreme_price directly since extreme prices
    have tiny edges that won't produce recommendations regardless."""

    def setup_method(self):
        self.settings = Settings()
        self.engine = DecisionEngine(self.settings)

    def _make_climate_info(self, event_date=None, threshold=38.5, market_type="high_temp"):
        return ClimateTickerInfo(
            market_type=market_type,
            city_code="NY",
            event_date=event_date or date.today(),
            threshold=threshold,
            bracket_type="between",
        )

    def test_blocks_extreme_price_day_of_no_nws_data(self):
        climate_info = self._make_climate_info()
        market = _make_market(yes_ask=96, no_ask=4, climate_info=climate_info)
        assert self.engine._should_block_extreme_price(market, {"collected_data": {}}) is True

    def test_blocks_extreme_low_price_day_of_no_nws_data(self):
        climate_info = self._make_climate_info()
        market = _make_market(yes_ask=4, no_ask=96, climate_info=climate_info)
        assert self.engine._should_block_extreme_price(market, {"collected_data": {}}) is True

    def test_allows_when_nws_contradicts_high_price(self):
        climate_info = self._make_climate_info(threshold=50.0)
        market = _make_market(yes_ask=96, no_ask=4, climate_info=climate_info)
        research_data = {
            "collected_data": {"running_daily_high_f": 38.0, "running_daily_low_f": 30.0}
        }
        # running_high (38) is far below threshold (50) - 5 = 45 → contradicts → don't block
        assert self.engine._should_block_extreme_price(market, research_data) is False

    def test_allows_when_nws_contradicts_low_price(self):
        climate_info = self._make_climate_info(threshold=35.0)
        market = _make_market(yes_ask=4, no_ask=96, climate_info=climate_info)
        research_data = {
            "collected_data": {"running_daily_high_f": 45.0, "running_daily_low_f": 30.0}
        }
        # running_high (45) > threshold (35) + 2 → contradicts → don't block
        assert self.engine._should_block_extreme_price(market, research_data) is False

    def test_no_block_for_non_climate(self):
        market = _make_market(yes_ask=96, no_ask=4, climate_info=None)
        assert self.engine._should_block_extreme_price(market, {}) is False

    def test_no_block_for_future_event(self):
        climate_info = self._make_climate_info(event_date=date(2099, 1, 1))
        market = _make_market(yes_ask=96, no_ask=4, climate_info=climate_info)
        assert self.engine._should_block_extreme_price(market, {"collected_data": {}}) is False

    def test_blocks_past_event_extreme_price(self):
        climate_info = self._make_climate_info(event_date=date(2020, 1, 1))
        market = _make_market(yes_ask=96, no_ask=4, climate_info=climate_info)
        assert self.engine._should_block_extreme_price(market, {"collected_data": {}}) is True

    def test_blocks_past_event_low_extreme_price(self):
        climate_info = self._make_climate_info(event_date=date(2020, 1, 1))
        market = _make_market(yes_ask=3, no_ask=97, climate_info=climate_info)
        assert self.engine._should_block_extreme_price(market, {"collected_data": {}}) is True

    def test_no_block_past_event_normal_price(self):
        climate_info = self._make_climate_info(event_date=date(2020, 1, 1))
        market = _make_market(yes_ask=50, no_ask=50, climate_info=climate_info)
        assert self.engine._should_block_extreme_price(market, {"collected_data": {}}) is False

    def test_no_block_for_normal_price(self):
        climate_info = self._make_climate_info()
        market = _make_market(yes_ask=50, no_ask=50, climate_info=climate_info)
        assert self.engine._should_block_extreme_price(market, {"collected_data": {}}) is False

    def test_blocks_when_nws_agrees_with_extreme_high(self):
        climate_info = self._make_climate_info(threshold=38.5)
        market = _make_market(yes_ask=96, no_ask=4, climate_info=climate_info)
        research_data = {
            "collected_data": {"running_daily_high_f": 40.0, "running_daily_low_f": 30.0}
        }
        # running_high (40) is close to threshold (38.5) → market is probably right → block
        assert self.engine._should_block_extreme_price(market, research_data) is True

    def test_blocks_non_climate_past_extreme(self):
        """Non-climate ticker with past date and extreme price should be blocked."""
        market = _make_market(
            yes_ask=99,
            no_ask=1,
            climate_info=None,
            ticker_date=date(2020, 1, 1),
            category="sports",
        )
        assert self.engine._should_block_extreme_price(market, {}) is True

    def test_allows_non_climate_future_extreme(self):
        """Non-climate ticker with future date and extreme price should NOT be blocked."""
        market = _make_market(
            yes_ask=99,
            no_ask=1,
            climate_info=None,
            ticker_date=date(2099, 1, 1),
            category="sports",
        )
        assert self.engine._should_block_extreme_price(market, {}) is False

    def test_allows_non_climate_no_date_extreme(self):
        """Non-climate ticker with no date and extreme price should NOT be blocked."""
        market = _make_market(
            yes_ask=99,
            no_ask=1,
            climate_info=None,
            ticker_date=None,
            category="other",
        )
        assert self.engine._should_block_extreme_price(market, {}) is False
