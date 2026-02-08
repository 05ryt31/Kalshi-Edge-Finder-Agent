import httpx

from src.utils.logger import get_logger

logger = get_logger(__name__)


class KalshiClient:
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"Accept": "application/json"},
        )

    async def get_markets(
        self,
        *,
        status: str = "open",
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict:
        params: dict = {"status": status, "limit": limit}
        if cursor:
            params["cursor"] = cursor

        logger.info("fetching_markets", status=status, limit=limit, cursor=cursor)
        response = await self.client.get(f"{self.BASE_URL}/markets", params=params)
        response.raise_for_status()
        return response.json()

    async def get_market(self, ticker: str) -> dict:
        logger.info("fetching_market", ticker=ticker)
        response = await self.client.get(f"{self.BASE_URL}/markets/{ticker}")
        response.raise_for_status()
        return response.json()

    async def get_events(
        self,
        *,
        status: str = "open",
        with_nested_markets: bool = True,
    ) -> dict:
        response = await self.client.get(
            f"{self.BASE_URL}/events",
            params={"status": status, "with_nested_markets": with_nested_markets},
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self.client.aclose()
