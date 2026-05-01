import httpx

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OddsAPIClient:
    BASE_URL = "https://api.the-odds-api.com/v4"

    def __init__(self) -> None:
        self.api_key = settings.ODDS_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_sports(self) -> list[dict]:
        logger.info("fetching_sports_list")
        response = await self.client.get(
            f"{self.BASE_URL}/sports",
            params={"apiKey": self.api_key},
        )
        response.raise_for_status()
        self._log_quota(response)
        return response.json()

    async def get_odds(
        self, sport_key: str, *, regions: str = "us", markets: str = "h2h,spreads,totals"
    ) -> list[dict]:
        logger.info("fetching_odds", sport_key=sport_key)
        response = await self.client.get(
            f"{self.BASE_URL}/sports/{sport_key}/odds",
            params={
                "apiKey": self.api_key,
                "regions": regions,
                "markets": markets,
            },
        )
        response.raise_for_status()
        self._log_quota(response)
        return response.json()

    async def get_scores(self, sport_key: str, *, days_from: int = 3) -> list[dict]:
        logger.info("fetching_scores", sport_key=sport_key)
        response = await self.client.get(
            f"{self.BASE_URL}/sports/{sport_key}/scores",
            params={
                "apiKey": self.api_key,
                "daysFrom": days_from,
            },
        )
        response.raise_for_status()
        self._log_quota(response)
        return response.json()

    def _log_quota(self, response: httpx.Response) -> None:
        remaining = response.headers.get("x-requests-remaining")
        used = response.headers.get("x-requests-used")
        if remaining is not None:
            logger.info("odds_api_quota", remaining=remaining, used=used)

    async def close(self) -> None:
        await self.client.aclose()
