from datetime import datetime, timedelta, timezone

import pytest

from src.schemas.market import Market
from src.schemas.settings import Settings
from src.services.filter import FilterService


def _make_market(
    *,
    ticker: str = "TEST-MARKET",
    category: str = "climate",
    yes_ask: int = 20,
    no_ask: int = 80,
    volume: int = 500,
    days_to_close: int = 3,
) -> Market:
    now = datetime.now(timezone.utc)
    return Market(
        ticker=ticker,
        event_ticker="TEST-EVENT",
        title="Test Market",
        category=category,
        status="open",
        yes_ask=yes_ask,
        no_ask=no_ask,
        yes_bid=yes_ask - 1,
        no_bid=no_ask - 1,
        last_price=yes_ask,
        volume=volume,
        volume_24h=100,
        close_time=now + timedelta(days=days_to_close),
        expiration_time=now + timedelta(days=days_to_close + 1),
    )


class TestFilterService:
    def test_passes_matching_market(self):
        settings = Settings()
        service = FilterService(settings)
        market = _make_market()
        result = service.filter_markets([market])
        assert len(result) == 1

    def test_rejects_wrong_category(self):
        settings = Settings(categories=["climate"])
        service = FilterService(settings)
        market = _make_market(category="sports")
        result = service.filter_markets([market])
        assert len(result) == 0

    def test_rejects_low_multiplier(self):
        settings = Settings(min_multiplier=3.0)
        service = FilterService(settings)
        market = _make_market(yes_ask=50, no_ask=50)
        result = service.filter_markets([market])
        assert len(result) == 0

    def test_rejects_too_far_close(self):
        settings = Settings(max_days_to_close=3)
        service = FilterService(settings)
        market = _make_market(days_to_close=10)
        result = service.filter_markets([market])
        assert len(result) == 0

    def test_rejects_low_volume(self):
        settings = Settings(min_volume=1000)
        service = FilterService(settings)
        market = _make_market(volume=50)
        result = service.filter_markets([market])
        assert len(result) == 0

    def test_sorts_by_multiplier(self):
        settings = Settings()
        service = FilterService(settings)
        m1 = _make_market(ticker="LOW", yes_ask=30, no_ask=70)
        m2 = _make_market(ticker="HIGH", yes_ask=10, no_ask=90)
        result = service.filter_markets([m1, m2])
        assert result[0].ticker == "HIGH"
