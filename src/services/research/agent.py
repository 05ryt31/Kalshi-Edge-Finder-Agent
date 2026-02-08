from src.clients.fred import FREDClient
from src.clients.openweather import OpenWeatherClient
from src.schemas.market import Market
from src.services.research.economics import EconomicsResearcher
from src.services.research.weather import WeatherResearcher
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ResearchAgent:
    def __init__(self, openweather: OpenWeatherClient, fred: FREDClient) -> None:
        self.weather = WeatherResearcher(openweather)
        self.economics = EconomicsResearcher(fred)

    async def research(self, market: Market) -> dict:
        logger.info("researching_market", ticker=market.ticker, category=market.category)

        if market.category == "climate":
            return await self.weather.research(market)
        if market.category == "economics":
            return await self.economics.research(market)

        return {
            "category": market.category,
            "data_sources": [],
            "collected_data": {},
            "summary": "No research available for this category",
        }
