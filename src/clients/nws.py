from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date

import httpx

from src.utils.logger import get_logger

logger = get_logger(__name__)

_USER_AGENT = "KalshiEdgeFinder/1.0 (weather-research)"


@dataclass(frozen=True)
class ASOSObservation:
    station: str
    valid_time: str
    temp_f: float | None
    dwpf: float | None
    sknt: float | None
    precip_in: float | None


@dataclass(frozen=True)
class DailyCLI:
    station: str
    report_date: date
    high_temp: float | None
    low_temp: float | None
    precip: float | None
    snow: float | None


def _parse_float(value: str) -> float | None:
    if not value or value.strip() in ("M", "T", ""):
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


class NWSClient:
    IEM_ASOS_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
    IEM_CLI_URL = "https://mesonet.agron.iastate.edu/json/cli.py"
    NWS_API_URL = "https://api.weather.gov"

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": _USER_AGENT},
        )

    async def get_observations(self, station: str, hours: int = 24) -> list[ASOSObservation]:
        logger.info("fetching_asos", station=station, hours=hours)
        try:
            response = await self.client.get(
                self.IEM_ASOS_URL,
                params={
                    "station": station,
                    "data": "tmpf",
                    "data": "dwpf",
                    "tz": "UTC",
                    "format": "onlycomma",
                    "hours": str(hours),
                },
            )
            response.raise_for_status()
            return self._parse_asos_csv(response.text, station)
        except Exception as e:
            logger.error("asos_fetch_error", station=station, error=str(e))
            return []

    async def get_daily_cli(self, station: str, report_date: date) -> DailyCLI | None:
        logger.info("fetching_cli", station=station, date=str(report_date))
        try:
            response = await self.client.get(
                self.IEM_CLI_URL,
                params={
                    "station": station,
                    "year": str(report_date.year),
                    "month": str(report_date.month),
                    "day": str(report_date.day),
                },
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            if not results:
                return None
            entry = results[0]
            return DailyCLI(
                station=station,
                report_date=report_date,
                high_temp=_parse_float(str(entry.get("high", "M"))),
                low_temp=_parse_float(str(entry.get("low", "M"))),
                precip=_parse_float(str(entry.get("precip", "M"))),
                snow=_parse_float(str(entry.get("snow", "M"))),
            )
        except Exception as e:
            logger.error("cli_fetch_error", station=station, error=str(e))
            return None

    async def get_nws_latest_observation(self, station: str) -> dict | None:
        logger.info("fetching_nws_latest", station=station)
        try:
            response = await self.client.get(
                f"{self.NWS_API_URL}/stations/{station}/observations/latest",
                headers={"Accept": "application/geo+json"},
            )
            response.raise_for_status()
            data = response.json()
            props = data.get("properties", {})
            return {
                "temperature_c": props.get("temperature", {}).get("value"),
                "temperature_f": self._c_to_f(props.get("temperature", {}).get("value")),
                "wind_speed_kmh": props.get("windSpeed", {}).get("value"),
                "description": props.get("textDescription"),
                "timestamp": props.get("timestamp"),
            }
        except Exception as e:
            logger.error("nws_latest_error", station=station, error=str(e))
            return None

    def _parse_asos_csv(self, text: str, station: str) -> list[ASOSObservation]:
        observations: list[ASOSObservation] = []
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            observations.append(
                ASOSObservation(
                    station=station,
                    valid_time=row.get("valid", ""),
                    temp_f=_parse_float(row.get("tmpf", "")),
                    dwpf=_parse_float(row.get("dwpf", "")),
                    sknt=_parse_float(row.get("sknt", "")),
                    precip_in=_parse_float(row.get("p01i", "")),
                )
            )
        return observations

    @staticmethod
    def _c_to_f(celsius: float | None) -> float | None:
        if celsius is None:
            return None
        return round(celsius * 9 / 5 + 32, 1)

    async def close(self) -> None:
        await self.client.aclose()
