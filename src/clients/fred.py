import httpx

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FREDClient:
    BASE_URL = "https://api.stlouisfed.org/fred"

    def __init__(self) -> None:
        self.api_key = settings.FRED_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_series(self, series_id: str, *, limit: int = 10) -> dict:
        logger.info("fetching_fred_series", series_id=series_id)
        response = await self.client.get(
            f"{self.BASE_URL}/series/observations",
            params={
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_series_info(self, series_id: str) -> dict:
        logger.info("fetching_fred_series_info", series_id=series_id)
        response = await self.client.get(
            f"{self.BASE_URL}/series",
            params={
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
            },
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self.client.aclose()
