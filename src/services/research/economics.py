from src.clients.fred import FREDClient
from src.schemas.market import Market
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EconomicsResearcher:
    SERIES_PATTERNS: dict[str, list[str]] = {
        "cpi": ["CPIAUCSL", "CPILFESL"],
        "inflation": ["CPIAUCSL", "PCEPI"],
        "unemployment": ["UNRATE"],
        "jobs": ["PAYEMS", "UNRATE"],
        "nonfarm": ["PAYEMS"],
        "gdp": ["GDP", "GDPC1"],
        "fed": ["FEDFUNDS", "DFEDTARU"],
        "interest rate": ["FEDFUNDS"],
    }

    def __init__(self, client: FREDClient) -> None:
        self.client = client

    async def research(self, market: Market) -> dict:
        series_ids = self._find_relevant_series(market.title)
        if not series_ids:
            return self._empty_report("Could not identify relevant economic indicators")

        try:
            collected_data: dict = {}
            for series_id in series_ids:
                data = await self.client.get_series(series_id, limit=12)
                info = await self.client.get_series_info(series_id)

                observations = data.get("observations", [])
                seriess = info.get("seriess", [{}])

                if not observations:
                    continue

                collected_data[series_id] = {
                    "name": seriess[0].get("title", series_id),
                    "latest_value": observations[0]["value"],
                    "latest_date": observations[0]["date"],
                    "recent_values": [
                        {"date": obs["date"], "value": obs["value"]}
                        for obs in observations[:6]
                    ],
                }

            return {
                "category": "economics",
                "data_sources": ["FRED"],
                "collected_data": collected_data,
                "summary": self._generate_summary(collected_data),
            }
        except Exception as e:
            logger.error("economics_research_error", error=str(e))
            return self._empty_report(f"Error fetching economic data: {e}")

    def _find_relevant_series(self, title: str) -> list[str]:
        title_lower = title.lower()
        series: list[str] = []
        for keyword, series_ids in self.SERIES_PATTERNS.items():
            if keyword in title_lower:
                series.extend(series_ids)
        unique = list(dict.fromkeys(series))
        return unique[:3]

    def _generate_summary(self, data: dict) -> str:
        parts = [
            f"{info['name']}: {info['latest_value']} ({info['latest_date']})"
            for info in data.values()
        ]
        return "; ".join(parts) if parts else "No data collected"

    def _empty_report(self, reason: str) -> dict:
        return {
            "category": "economics",
            "data_sources": [],
            "collected_data": {},
            "summary": reason,
        }
