import httpx

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OpenWeatherClient:
    BASE_URL = "https://api.openweathermap.org/data/2.5"

    def __init__(self) -> None:
        self.api_key = settings.OPENWEATHER_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_forecast(self, city: str) -> dict:
        logger.info("fetching_forecast", city=city)
        response = await self.client.get(
            f"{self.BASE_URL}/forecast",
            params={"q": city, "appid": self.api_key, "units": "imperial"},
        )
        response.raise_for_status()
        return response.json()

    async def get_current(self, city: str) -> dict:
        logger.info("fetching_current_weather", city=city)
        response = await self.client.get(
            f"{self.BASE_URL}/weather",
            params={"q": city, "appid": self.api_key, "units": "imperial"},
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self.client.aclose()
