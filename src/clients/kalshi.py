import asyncio
import base64
import time

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

PROD_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
DEMO_BASE_URL = "https://demo-api.kalshi.co/trade-api/v2"

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0


def _load_private_key(key_data: str):
    pem = key_data.strip()
    if not pem.startswith("-----BEGIN"):
        pem = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            + pem
            + "\n-----END RSA PRIVATE KEY-----"
        )
    return serialization.load_pem_private_key(pem.encode(), password=None)


def _create_signature(private_key, timestamp: str, method: str, path: str) -> str:
    path_without_query = path.split("?")[0]
    message = f"{timestamp}{method}{path_without_query}".encode("utf-8")
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


class KalshiClient:
    def __init__(self) -> None:
        self.base_url = DEMO_BASE_URL if settings.KALSHI_USE_DEMO else PROD_BASE_URL
        self.api_key = settings.KALSHI_API_KEY
        self._private_key = None

        if settings.KALSHI_PRIVATE_KEY:
            try:
                self._private_key = _load_private_key(settings.KALSHI_PRIVATE_KEY)
            except Exception as e:
                logger.warning("private_key_load_failed", error=str(e))

        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"Accept": "application/json"},
        )

    def _auth_headers(self, method: str, path: str) -> dict:
        if not self.api_key or not self._private_key:
            return {}

        timestamp = str(int(time.time() * 1000))
        signature = _create_signature(self._private_key, timestamp, method, path)
        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": signature,
        }

    async def _request(self, method: str, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"

        for attempt in range(MAX_RETRIES):
            headers = self._auth_headers(method.upper(), path)
            try:
                response = await self.client.request(
                    method, url, params=params, headers=headers
                )
                if response.status_code == 429:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "rate_limited",
                        attempt=attempt + 1,
                        delay=delay,
                        url=url,
                    )
                    await asyncio.sleep(delay)
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError:
                raise
            except httpx.HTTPError as e:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "request_retry",
                        attempt=attempt + 1,
                        delay=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)
                else:
                    raise

        raise httpx.HTTPError(f"Max retries ({MAX_RETRIES}) exceeded for {url}")

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
        return await self._request("GET", "/markets", params=params)

    async def get_market(self, ticker: str) -> dict:
        logger.info("fetching_market", ticker=ticker)
        return await self._request("GET", f"/markets/{ticker}")

    async def get_events(
        self,
        *,
        status: str = "open",
        with_nested_markets: bool = True,
    ) -> dict:
        return await self._request(
            "GET",
            "/events",
            params={"status": status, "with_nested_markets": with_nested_markets},
        )

    async def close(self) -> None:
        await self.client.aclose()
