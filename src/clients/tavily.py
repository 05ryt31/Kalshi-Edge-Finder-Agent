import httpx

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TavilyClient:
    BASE_URL = "https://api.tavily.com"

    def __init__(self) -> None:
        self.api_key = settings.TAVILY_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)

    async def search(self, query: str, *, max_results: int = 5) -> dict:
        logger.info("tavily_search", query=query)
        response = await self.client.post(
            f"{self.BASE_URL}/search",
            json={
                "api_key": self.api_key,
                "query": query,
                "topic": "news",
                "time_range": "week",
                "max_results": max_results,
                "include_answer": True,
            },
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self.client.aclose()
