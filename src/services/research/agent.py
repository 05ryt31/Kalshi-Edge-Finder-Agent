from src.clients.fred import FREDClient
from src.clients.odds_api import OddsAPIClient
from src.clients.openweather import OpenWeatherClient
from src.clients.tavily import TavilyClient
from src.schemas.market import Market
from src.services.research.economics import EconomicsResearcher
from src.services.research.sports import SportsResearcher
from src.services.research.weather import WeatherResearcher
from src.services.research.web_search import WebSearchResearcher
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ResearchAgent:
    def __init__(
        self,
        openweather: OpenWeatherClient,
        fred: FREDClient,
        odds_api: OddsAPIClient | None = None,
        tavily: TavilyClient | None = None,
    ) -> None:
        self.weather = WeatherResearcher(openweather)
        self.economics = EconomicsResearcher(fred)
        self.sports = SportsResearcher(odds_api) if odds_api else None
        self.web_search = WebSearchResearcher(tavily) if tavily else None

    async def research(self, market: Market) -> dict:
        logger.info("researching_market", ticker=market.ticker, category=market.category)

        if market.category == "climate":
            return await self.weather.research(market)
        if market.category == "economics":
            return await self.economics.research(market)
        if market.category == "sports":
            return await self._research_sports(market)

        return {
            "category": market.category,
            "data_sources": [],
            "collected_data": {},
            "summary": "No research available for this category",
        }

    async def _research_sports(self, market: Market) -> dict:
        sports_data: dict | None = None
        web_data: dict | None = None

        if self.sports:
            sports_data = await self.sports.research(market)
        if self.web_search:
            web_data = await self.web_search.research(market)

        if sports_data and web_data:
            return self._merge_research(sports_data, web_data)
        if sports_data:
            return sports_data
        if web_data:
            return web_data

        return {
            "category": "sports",
            "data_sources": [],
            "collected_data": {},
            "summary": "No sports research clients configured",
        }

    def _merge_research(self, primary: dict, secondary: dict) -> dict:
        merged_sources = list(
            dict.fromkeys(primary.get("data_sources", []) + secondary.get("data_sources", []))
        )

        merged_data = {**primary.get("collected_data", {})}
        secondary_data = secondary.get("collected_data", {})
        if secondary_data:
            merged_data["web_search"] = secondary_data

        primary_summary = primary.get("summary", "")
        secondary_summary = secondary.get("summary", "")
        merged_summary = primary_summary
        if secondary_summary and secondary_summary != primary_summary:
            merged_summary = f"{primary_summary} | Web context: {secondary_summary}"

        return {
            "category": "sports",
            "data_sources": merged_sources,
            "collected_data": merged_data,
            "summary": merged_summary,
        }
