from __future__ import annotations

from datetime import date

from src.clients.nws import NWSClient
from src.clients.openweather import OpenWeatherClient
from src.schemas.market import Market
from src.utils.logger import get_logger
from src.utils.ticker_parser import get_city_display_name, get_cli_station, get_nws_station, get_wfo_code

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
        "San Francisco": "San Francisco,US",
        "SF": "San Francisco,US",
    }

    def __init__(self, openweather: OpenWeatherClient, nws: NWSClient | None = None) -> None:
        self.openweather = openweather
        self.nws = nws

    async def research(self, market: Market) -> dict:
        if market.climate_info and self.nws:
            return await self._nws_grounded_research(market)
        return await self._legacy_research(market)

    async def _nws_grounded_research(self, market: Market) -> dict:
        climate_info = market.climate_info
        station = get_nws_station(climate_info.city_code)
        city_name = get_city_display_name(climate_info.city_code) or climate_info.city_code

        # Concluded events: CLI-only path to avoid echo chamber
        if market.is_past_event:
            return await self._concluded_event_research(market, climate_info, station, city_name)

        is_day_of = market.is_day_of_event

        collected: dict = {
            "city": city_name,
            "nws_station": station,
            "market_type": climate_info.market_type,
            "threshold": climate_info.threshold,
            "bracket_type": climate_info.bracket_type,
            "event_date": str(climate_info.event_date) if climate_info.event_date else None,
            "is_day_of_event": is_day_of,
            "market_close_time": str(market.close_time),
        }

        data_sources = []

        # Fetch ASOS observations
        if station:
            observations = await self.nws.get_observations(station, hours=24)
            if observations:
                data_sources.append("NWS ASOS")
                temps = [o.temp_f for o in observations if o.temp_f is not None]
                collected["asos_observation_count"] = len(observations)
                if temps:
                    collected["running_daily_high_f"] = max(temps)
                    collected["running_daily_low_f"] = min(temps)
                    collected["latest_temp_f"] = temps[-1]
                collected["asos_observations"] = [
                    {"time": o.valid_time, "temp_f": o.temp_f}
                    for o in observations[-12:]
                ]

        # Day-of: also try CLI report
        if is_day_of and station:
            cli = await self.nws.get_daily_cli(station, date.today())
            if cli:
                data_sources.append("NWS CLI Report")
                collected["cli_high"] = cli.high_temp
                collected["cli_low"] = cli.low_temp
                collected["cli_precip"] = cli.precip
                collected["cli_snow"] = cli.snow

        # Future events: supplement with OpenWeather forecast
        if not is_day_of:
            openweather_city = self._resolve_openweather_city(city_name)
            if openweather_city:
                try:
                    forecast = await self.openweather.get_forecast(openweather_city)
                    data_sources.append("OpenWeatherMap")
                    collected["forecast"] = self._summarize_forecast(forecast)
                except Exception as e:
                    logger.warning("openweather_fallback_error", error=str(e))

        # NWS latest observation as fallback
        if station and "running_daily_high_f" not in collected:
            latest = await self.nws.get_nws_latest_observation(station)
            if latest:
                data_sources.append("NWS Latest Observation")
                collected["nws_latest"] = latest

        # Build resolution criteria string
        collected["resolution_criteria"] = self._build_resolution_criteria(market, climate_info, station)

        summary = self._build_nws_summary(collected)

        return {
            "category": "climate",
            "data_sources": data_sources,
            "collected_data": collected,
            "summary": summary,
        }

    async def _concluded_event_research(
        self, market: Market, climate_info, station: str | None, city_name: str
    ) -> dict:
        """CLI-only research for concluded events. No ASOS, no OpenWeather."""
        cli_station = get_cli_station(climate_info.city_code)
        event_date = climate_info.event_date

        collected: dict = {
            "city": city_name,
            "nws_station": station,
            "market_type": climate_info.market_type,
            "threshold": climate_info.threshold,
            "bracket_type": climate_info.bracket_type,
            "event_date": str(event_date) if event_date else None,
            "event_concluded": True,
            "market_close_time": str(market.close_time),
        }

        data_sources = []
        official_data_missing = True

        if cli_station and event_date:
            cli = await self.nws.get_daily_cli(cli_station, event_date)
            if cli:
                data_sources.append("NWS CLI Report")
                collected["cli_high"] = cli.high_temp
                collected["cli_low"] = cli.low_temp
                collected["cli_precip"] = cli.precip
                collected["cli_snow"] = cli.snow
                official_data_missing = False

        collected["official_data_missing"] = official_data_missing
        collected["resolution_criteria"] = self._build_resolution_criteria(market, climate_info, station)

        summary_parts = [f"CONCLUDED EVENT ({event_date})"]
        if official_data_missing:
            summary_parts.append("Official CLI data MISSING")
        else:
            if collected.get("cli_high") is not None:
                summary_parts.append(f"CLI high: {collected['cli_high']}F")
            if collected.get("cli_low") is not None:
                summary_parts.append(f"CLI low: {collected['cli_low']}F")

        return {
            "category": "climate",
            "data_sources": data_sources,
            "collected_data": collected,
            "summary": " | ".join(summary_parts),
        }

    async def _legacy_research(self, market: Market) -> dict:
        city = self._extract_city(market.title)
        if not city:
            return self._empty_report("Could not extract city from title")

        try:
            forecast = await self.openweather.get_forecast(city)
            current = await self.openweather.get_current(city)

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

    def _build_resolution_criteria(self, market: Market, climate_info, station: str | None) -> str:
        cli_station = get_cli_station(climate_info.city_code)
        wfo = get_wfo_code(climate_info.city_code)
        city_name = get_city_display_name(climate_info.city_code) or climate_info.city_code

        type_desc = {
            "high_temp": "official daily high temperature",
            "low_temp": "official daily low temperature",
            "snow": "official snowfall total",
            "rain": "official precipitation total",
        }
        desc = type_desc.get(climate_info.market_type, "weather measurement")

        cli_ref = ""
        if cli_station and wfo:
            cli_ref = (
                f" Resolution data: NWS Climatological Report ({cli_station})."
                f" Source: https://www.weather.gov/wrh/Climate?wfo={wfo}"
            )

        # IMPORTANT: Do NOT assert "resolves YES if..." from ticker parsing alone.
        # The market title is the authoritative description of what YES means.
        # Ticker parsing may conflict with the title (e.g., T40 vs ">40°").
        return (
            f"Market question (from title): \"{market.title}\"\n"
            f"Measurement: {desc} for {city_name}.\n"
            f"Parsed threshold from ticker: {climate_info.threshold} "
            f"({'inches' if climate_info.market_type in ('snow', 'rain') else 'degrees F'}).\n"
            f"WARNING: The market title is the authoritative source for what YES/NO means. "
            f"Do NOT assume from the ticker alone.{cli_ref}"
        )

    def _build_nws_summary(self, collected: dict) -> str:
        parts = []
        station = collected.get("nws_station", "unknown")
        parts.append(f"NWS Station: {station}")

        if "running_daily_high_f" in collected:
            parts.append(f"Running high: {collected['running_daily_high_f']}F")
        if "running_daily_low_f" in collected:
            parts.append(f"Running low: {collected['running_daily_low_f']}F")
        if "latest_temp_f" in collected:
            parts.append(f"Latest: {collected['latest_temp_f']}F")
        if collected.get("cli_high") is not None:
            parts.append(f"CLI high: {collected['cli_high']}F")
        if collected.get("is_day_of_event"):
            parts.append("DAY-OF EVENT")

        return " | ".join(parts)

    def _resolve_openweather_city(self, city_name: str) -> str | None:
        for pattern, owm_city in self.CITY_PATTERNS.items():
            if pattern.lower() in city_name.lower():
                return owm_city
        return f"{city_name},US"

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
