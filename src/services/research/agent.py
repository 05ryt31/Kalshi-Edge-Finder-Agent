from src.clients.nws import NWSClient
from src.clients.openweather import OpenWeatherClient
from src.schemas.market import Market
from src.services.research.weather import WeatherResearcher
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ResearchAgent:
    """Climate-only research agent.

    After the climate-focus pivot we only research weather/climate markets.
    Other categories are filtered out before reaching this agent; if one
    slips through (e.g. via a manual API call) we return an empty report
    rather than calling external APIs we no longer maintain.
    """

    def __init__(
        self,
        openweather: OpenWeatherClient,
        nws: NWSClient | None = None,
    ) -> None:
        self.weather = WeatherResearcher(openweather, nws)

    async def research(self, market: Market) -> dict:
        logger.info("researching_market", ticker=market.ticker, category=market.category)

        if market.category == "climate":
            return await self.weather.research(market)

        logger.info("non_climate_skipped", ticker=market.ticker, category=market.category)
        return {
            "category": market.category,
            "data_sources": [],
            "collected_data": {},
            "summary": "Non-climate markets are not researched in climate-focus mode.",
        }
