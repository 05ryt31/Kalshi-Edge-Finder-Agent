from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from src.schemas.market import Market
from src.services.research.sports import SportsResearcher


def _make_market(
    *,
    ticker: str = "NBA-LAKERS-WIN",
    title: str = "Will the Lakers win tonight?",
) -> Market:
    now = datetime.now(timezone.utc)
    return Market(
        ticker=ticker,
        event_ticker="NBA-EVENT",
        title=title,
        category="sports",
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


class TestSportKeyExtraction:
    def setup_method(self):
        self.client = AsyncMock()
        self.researcher = SportsResearcher(self.client)

    def test_extract_from_ticker_nba(self):
        market = _make_market(ticker="NBA-LAKERS-WIN")
        assert self.researcher._extract_sport_key(market) == "basketball_nba"

    def test_extract_from_ticker_nfl(self):
        market = _make_market(ticker="NFL-CHIEFS-SB")
        assert self.researcher._extract_sport_key(market) == "americanfootball_nfl"

    def test_extract_from_ticker_mlb(self):
        market = _make_market(ticker="MLB-NYY-WS")
        assert self.researcher._extract_sport_key(market) == "baseball_mlb"

    def test_extract_from_ticker_nhl(self):
        market = _make_market(ticker="NHL-AVS-WIN")
        assert self.researcher._extract_sport_key(market) == "icehockey_nhl"

    def test_extract_from_ticker_ufc(self):
        market = _make_market(ticker="UFC-300-MAIN")
        assert self.researcher._extract_sport_key(market) == "mma_mixed_martial_arts"

    def test_extract_from_title_keyword(self):
        market = _make_market(ticker="SPORT-123", title="Who wins the super bowl?")
        assert self.researcher._extract_sport_key(market) == "americanfootball_nfl"

    def test_extract_from_title_team_name(self):
        market = _make_market(ticker="SPORT-123", title="Will the Celtics beat the Heat?")
        assert self.researcher._extract_sport_key(market) == "basketball_nba"

    def test_extract_none_when_unknown(self):
        market = _make_market(ticker="CRYPTO-BTC", title="Will Bitcoin reach 100k?")
        assert self.researcher._extract_sport_key(market) is None


class TestTeamExtraction:
    def setup_method(self):
        self.client = AsyncMock()
        self.researcher = SportsResearcher(self.client)

    def test_extract_single_team(self):
        teams = self.researcher._extract_teams("Will the Lakers win tonight?")
        assert "Lakers" in teams

    def test_extract_multiple_teams(self):
        teams = self.researcher._extract_teams("Lakers vs Celtics game")
        assert "Lakers" in teams
        assert "Celtics" in teams

    def test_extract_vs_pattern_fallback(self):
        teams = self.researcher._extract_teams("Team Alpha vs. Team Beta")
        assert len(teams) == 2


class TestSportsResearch:
    def setup_method(self):
        self.client = AsyncMock()
        self.researcher = SportsResearcher(self.client)

    @pytest.mark.asyncio
    async def test_research_returns_data(self):
        self.client.get_odds.return_value = [
            {
                "home_team": "Los Angeles Lakers",
                "away_team": "Boston Celtics",
                "commence_time": "2026-02-22T00:00:00Z",
                "bookmakers": [
                    {
                        "key": "fanduel",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Los Angeles Lakers", "price": 1.5},
                                    {"name": "Boston Celtics", "price": 2.8},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        self.client.get_scores.return_value = []

        market = _make_market()
        result = await self.researcher.research(market)

        assert result["category"] == "sports"
        assert "The Odds API" in result["data_sources"]
        assert result["collected_data"]["sport"] == "basketball_nba"

    @pytest.mark.asyncio
    async def test_research_unknown_sport(self):
        market = _make_market(ticker="CRYPTO-BTC", title="Will Bitcoin moon?")
        result = await self.researcher.research(market)

        assert result["category"] == "sports"
        assert result["data_sources"] == []
        assert "Could not determine" in result["summary"]

    @pytest.mark.asyncio
    async def test_research_api_error(self):
        self.client.get_odds.side_effect = Exception("API down")
        market = _make_market()
        result = await self.researcher.research(market)

        assert result["category"] == "sports"
        assert result["data_sources"] == []
        assert "Error" in result["summary"]
