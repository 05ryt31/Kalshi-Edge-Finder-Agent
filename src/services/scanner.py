from collections.abc import AsyncGenerator

from src.clients.kalshi import KalshiClient
from src.schemas.market import Market
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ScannerService:
    def __init__(self, kalshi_client: KalshiClient) -> None:
        self.kalshi = kalshi_client

    async def scan_all_markets(self) -> AsyncGenerator[Market, None]:
        cursor = None

        while True:
            data = await self.kalshi.get_markets(status="open", limit=100, cursor=cursor)

            for market_data in data.get("markets", []):
                try:
                    yield self._parse_market(market_data)
                except Exception as e:
                    logger.warning("market_parse_error", ticker=market_data.get("ticker"), error=str(e))

            cursor = data.get("cursor")
            if not cursor:
                break

    def _parse_market(self, data: dict) -> Market:
        return Market(
            ticker=data["ticker"],
            event_ticker=data.get("event_ticker", ""),
            title=data.get("title", ""),
            subtitle=data.get("subtitle"),
            category=self._infer_category(data),
            status=data.get("status", "open"),
            yes_ask=data.get("yes_ask", 0),
            no_ask=data.get("no_ask", 0),
            yes_bid=data.get("yes_bid", 0),
            no_bid=data.get("no_bid", 0),
            last_price=data.get("last_price", 0),
            volume=data.get("volume", 0),
            volume_24h=data.get("volume_24h", 0),
            close_time=data["close_time"],
            expiration_time=data.get("expiration_time", data["close_time"]),
        )

    def _infer_category(self, data: dict) -> str:
        ticker = data.get("ticker", "").upper()
        title = data.get("title", "").lower()

        climate_keywords_ticker = ["TEMP", "WEATHER", "RAIN", "HIGH", "LOW", "SNOW", "WIND"]
        if any(x in ticker for x in climate_keywords_ticker):
            return "climate"

        econ_keywords_ticker = ["CPI", "GDP", "FED", "JOBS", "NFP", "RATE", "INFLATION"]
        if any(x in ticker for x in econ_keywords_ticker):
            return "economics"

        if any(x in title for x in ["temperature", "weather", "rain", "snow", "degrees"]):
            return "climate"

        if any(x in title for x in ["cpi", "gdp", "unemployment", "inflation", "fed", "jobs", "nonfarm"]):
            return "economics"

        if any(x in title for x in ["company", "stock", "earnings", "revenue", "share"]):
            return "companies"

        if any(x in title for x in ["game", "match", "score", "team", "player"]):
            return "sports"

        return "other"
