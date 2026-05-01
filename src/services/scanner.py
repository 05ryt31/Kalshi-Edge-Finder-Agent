from collections.abc import AsyncGenerator

from src.clients.kalshi import KalshiClient
from src.schemas.market import Market
from src.utils.logger import get_logger
from src.utils.ticker_parser import parse_climate_ticker, parse_ticker_date

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
        category = self._infer_category(data)
        ticker = data.get("ticker", "")
        climate_info = None
        if category == "climate":
            climate_info = parse_climate_ticker(ticker)

        return Market(
            ticker=data["ticker"],
            event_ticker=data.get("event_ticker", ""),
            title=data.get("title", ""),
            subtitle=data.get("subtitle"),
            category=category,
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
            climate_info=climate_info,
            ticker_date=parse_ticker_date(ticker),
        )

    def _infer_category(self, data: dict) -> str:
        ticker = data.get("ticker", "").upper()
        title = data.get("title", "").lower()

        sports_keywords_ticker = [
            "NBA", "NFL", "MLB", "NHL", "UFC", "MMA", "MLS",
            "NCAAB", "NCAAF", "EPL", "FIFA", "PGA", "ATP", "WTA",
        ]
        if any(x in ticker for x in sports_keywords_ticker):
            return "sports"

        climate_keywords_ticker = ["TEMP", "WEATHER", "RAIN", "HIGH", "LOW", "SNOW", "WIND"]
        if any(x in ticker for x in climate_keywords_ticker):
            return "climate"

        econ_keywords_ticker = ["CPI", "GDP", "FED", "JOBS", "NFP", "RATE", "INFLATION"]
        if any(x in ticker for x in econ_keywords_ticker):
            return "economics"

        sports_keywords_title = [
            "basketball", "football", "baseball", "hockey", "soccer",
            "nba", "nfl", "mlb", "nhl", "ufc", "mma", "mls",
            "playoffs", "super bowl", "world series", "stanley cup",
            "march madness", "championship", "finals",
            "lakers", "celtics", "warriors", "nets", "bucks", "76ers",
            "suns", "mavericks", "heat", "nuggets", "clippers", "knicks",
            "chiefs", "eagles", "49ers", "bills", "cowboys", "ravens",
            "dolphins", "lions", "bengals", "packers", "seahawks",
            "yankees", "dodgers", "astros", "braves", "mets", "phillies",
            "padres", "red sox", "cubs", "brewers",
            "avalanche", "lightning", "panthers", "bruins", "oilers",
            "hurricanes", "maple leafs", "penguins", "golden knights",
            "game ", " vs ", " vs. ",
            "win", "score", "points", "touchdown", "home run",
        ]
        if any(x in title for x in sports_keywords_title):
            return "sports"

        if any(x in title for x in ["temperature", "weather", "rain", "snow", "degrees"]):
            return "climate"

        if any(x in title for x in ["cpi", "gdp", "unemployment", "inflation", "fed", "jobs", "nonfarm"]):
            return "economics"

        if any(x in title for x in ["company", "stock", "earnings", "revenue", "share"]):
            return "companies"

        return "other"
