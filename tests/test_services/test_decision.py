from datetime import datetime, timedelta, timezone

from src.schemas.market import Market
from src.schemas.settings import Settings
from src.services.decision import DecisionEngine


def _make_market(*, yes_ask: int = 30, no_ask: int = 70) -> Market:
    now = datetime.now(timezone.utc)
    return Market(
        ticker="TEST-MKT",
        event_ticker="TEST-EVT",
        title="Test Market",
        category="climate",
        status="open",
        yes_ask=yes_ask,
        no_ask=no_ask,
        yes_bid=yes_ask - 1,
        no_bid=no_ask - 1,
        last_price=yes_ask,
        volume=500,
        volume_24h=100,
        close_time=now + timedelta(days=3),
        expiration_time=now + timedelta(days=4),
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
