from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.recommendation import RecommendationRepository
from src.services.historical_context import HistoricalContextService


def _rec_data(*, category: str = "climate", ticker: str = "TEMP-NYC", scan_id: str = "scan-1"):
    return {
        "id": f"rec-{ticker}-{scan_id}",
        "scan_id": scan_id,
        "market_ticker": ticker,
        "market_title": f"Market for {ticker}",
        "category": category,
        "side": "yes",
        "market_price": 30,
        "estimated_probability": 0.65,
        "confidence": 0.80,
        "edge": 0.35,
        "strength": "strong",
        "suggested_amount": 80.0,
        "reasoning": "Test reasoning for the market",
        "research_data": {"summary": "Test research summary"},
        "status": "pending",
        "expires_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
        "created_at": datetime(2026, 2, 8, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 2, 8, tzinfo=timezone.utc),
    }


class TestHistoricalContextService:
    @pytest.mark.asyncio
    async def test_empty_history(self, db_session: AsyncSession):
        repo = RecommendationRepository(db_session)
        service = HistoricalContextService(repo)

        result = await service.get_context_for_category("climate")
        assert "No prior analyses" in result

    @pytest.mark.asyncio
    async def test_returns_same_category(self, db_session: AsyncSession):
        repo = RecommendationRepository(db_session)

        await repo.create(_rec_data(category="climate", ticker="TEMP-1"))
        await repo.create(_rec_data(category="economics", ticker="CPI-1"))
        await db_session.flush()

        service = HistoricalContextService(repo)
        result = await service.get_context_for_category("climate")

        assert "TEMP-1" in result
        assert "CPI-1" not in result

    @pytest.mark.asyncio
    async def test_excludes_current_scan(self, db_session: AsyncSession):
        repo = RecommendationRepository(db_session)

        await repo.create(_rec_data(ticker="OLD", scan_id="scan-old"))
        await repo.create(_rec_data(ticker="CURRENT", scan_id="scan-current"))
        await db_session.flush()

        service = HistoricalContextService(repo)
        result = await service.get_context_for_category(
            "climate", exclude_scan_id="scan-current"
        )

        assert "OLD" in result
        assert "CURRENT" not in result

    @pytest.mark.asyncio
    async def test_limits_results(self, db_session: AsyncSession):
        repo = RecommendationRepository(db_session)

        for i in range(10):
            await repo.create(_rec_data(ticker=f"MKT-{i}", scan_id=f"scan-{i}"))
        await db_session.flush()

        service = HistoricalContextService(repo)
        result = await service.get_context_for_category("climate", limit=3)

        # Should only contain 3 entries
        assert result.count("### Past Analysis") == 3

    @pytest.mark.asyncio
    async def test_format_contains_key_fields(self, db_session: AsyncSession):
        repo = RecommendationRepository(db_session)
        await repo.create(_rec_data())
        await db_session.flush()

        service = HistoricalContextService(repo)
        result = await service.get_context_for_category("climate")

        assert "Ticker: TEMP-NYC" in result
        assert "Side: yes" in result
        assert "Edge:" in result
        assert "Confidence:" in result
        assert "Research Summary:" in result
