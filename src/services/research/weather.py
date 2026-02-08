from src.clients.openweather import OpenWeatherClient
from src.schemas.market import Market
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WeatherResearcher:
    CITY_PATTERNS: dict[str, str] = {
        "NYC": "New York,US",
        "New York": "New York,US",
        "LA": "Los Angeles,US",
        "Los Angeles": "Los Angeles,US",
        "Chicago": "Chicago,US",
        "Miami": "Miami,US",
        "Houston": "Houston,US",
        "Phoenix": "Phoenix,US",
        "Philadelphia": "Philadelphia,US",
        "San Antonio": "San Antonio,US",
        "San Diego": "San Diego,US",
        "Dallas": "Dallas,US",
        "Austin": "Austin,US",
        "Denver": "Denver,US",
        "Washington": "Washington,US",
        "DC": "Washington,US",
        "Boston": "Boston,US",
        "Seattle": "Seattle,US",
        "Atlanta": "Atlanta,US",
        "Minneapolis": "Minneapolis,US",
        "Detroit": "Detroit,US",
    }

    def __init__(self, client: OpenWeatherClient) -> None:
        self.client = client

    async def research(self, market: Market) -> dict:
        city = self._extract_city(market.title)
        if not city:
            return self._empty_report("Could not extract city from title")

        try:
            forecast = await self.client.get_forecast(city)
            current = await self.client.get_current(city)

            return {
                "category": "climate",
                "data_sources": ["OpenWeatherMap"],
                "collected_data": {
                    "city": city,
                    "current_temp": current["main"]["temp"],
                    "current_conditions": current["weather"][0]["description"],
                    "forecast": self._summarize_forecast(forecast),
                    "market_close_time": str(market.close_time),
                },
                "summary": self._generate_summary(current, forecast),
            }
        except Exception as e:
            logger.error("weather_research_error", city=city, error=str(e))
            return self._empty_report(f"Error fetching weather data: {e}")

    def _extract_city(self, title: str) -> str | None:
        for pattern, city in self.CITY_PATTERNS.items():
            if pattern.lower() in title.lower():
                return city
        return None

    def _summarize_forecast(self, forecast: dict) -> list[dict]:
        return [
            {
                "time": item["dt_txt"],
                "temp": item["main"]["temp"],
                "conditions": item["weather"][0]["description"],
            }
            for item in forecast["list"][:8]
        ]

    def _generate_summary(self, current: dict, forecast: dict) -> str:
        temps = [item["main"]["temp"] for item in forecast["list"][:8]]
        max_temp = max(temps)
        min_temp = min(temps)
        return (
            f"Current: {current['main']['temp']}F. "
            f"Next 24h: High {max_temp}F, Low {min_temp}F."
        )

    def _empty_report(self, reason: str) -> dict:
        return {
            "category": "climate",
            "data_sources": [],
            "collected_data": {},
            "summary": reason,
        }
