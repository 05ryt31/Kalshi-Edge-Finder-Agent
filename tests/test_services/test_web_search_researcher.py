from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from src.schemas.market import Market
from src.services.research.web_search import WebSearchResearcher


def _make_market(
    *,
    ticker: str = "NBA-LAKERS-WIN",
    title: str = "Will the Lakers win tonight?",
    category: str = "sports",
) -> Market:
    now = datetime.now(timezone.utc)
    return Market(
        ticker=ticker,
        event_ticker="TEST-EVENT",
        title=title,
        category=category,
        status="open",
        yes_ask=40,
        no_ask=60,
        yes_bid=39,
        no_bid=59,
        last_price=40,
        volume=500,
        volume_24h=100,
        close_time=now + timedelta(days=1),
        expiration_time=now + timedelta(days=2),
    )


class TestQueryBuilding:
    def setup_method(self):
        self.client = AsyncMock()
        self.researcher = WebSearchResearcher(self.client)

    def test_sports_query(self):
        market = _make_market(category="sports")
        query = self.researcher._build_query(market)
        assert "odds" in query
        assert "Lakers" in query

    def test_non_sports_query(self):
        market = _make_market(category="climate", title="NYC temperature forecast")
        query = self.researcher._build_query(market)
        assert "analysis" in query
        assert "NYC" in query


class TestWebSearchResearch:
    def setup_method(self):
        self.client = AsyncMock()
        self.researcher = WebSearchResearcher(self.client)

    @pytest.mark.asyncio
    async def test_research_returns_articles(self):
        self.client.search.return_value = {
            "answer": "The Lakers are favored to win.",
            "results": [
                {
                    "title": "Lakers Preview",
                    "url": "https://example.com/lakers",
                    "content": "The Lakers look strong this season.",
                    "score": 0.95,
                },
                {
                    "title": "NBA Odds Today",
                    "url": "https://example.com/odds",
                    "content": "Full odds breakdown for tonight's games.",
                    "score": 0.88,
                },
            ],
        }

        market = _make_market()
        result = await self.researcher.research(market)

        assert result["category"] == "sports"
        assert "Tavily Web Search" in result["data_sources"]
        assert len(result["collected_data"]["articles"]) == 2
        assert result["summary"] == "The Lakers are favored to win."

    @pytest.mark.asyncio
    async def test_research_no_answer_falls_back_to_titles(self):
        self.client.search.return_value = {
            "answer": "",
            "results": [
                {"title": "Article One", "url": "https://example.com/1", "content": "...", "score": 0.9},
            ],
        }

        market = _make_market()
        result = await self.researcher.research(market)

        assert "Article One" in result["summary"]

    @pytest.mark.asyncio
    async def test_content_truncation(self):
        long_content = "x" * 5000
        self.client.search.return_value = {
            "answer": "",
            "results": [
                {"title": "Long", "url": "https://example.com", "content": long_content, "score": 0.9},
            ],
        }

        market = _make_market()
        result = await self.researcher.research(market)

        article_content = result["collected_data"]["articles"][0]["content"]
        assert len(article_content) <= 2000

    @pytest.mark.asyncio
    async def test_research_api_error(self):
        self.client.search.side_effect = Exception("Search failed")
        market = _make_market()
        result = await self.researcher.research(market)

        assert result["data_sources"] == []
        assert "failed" in result["summary"].lower()
