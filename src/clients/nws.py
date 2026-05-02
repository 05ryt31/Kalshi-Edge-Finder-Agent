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


@dataclass(frozen=True)
class DailySummary:
    """Daily aggregated weather observation from IEM daily.py.

    Used for bulk historical fetches to compute climatology. Unlike
    DailyCLI (NWS Climatological Report — official, may be delayed),
    this is computed from raw ASOS observations and is available
    immediately for any station.
    """

    station: str
    obs_date: date
    high_temp_f: float | None
    low_temp_f: float | None
    precip_in: float | None
    snow_in: float | None


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
    IEM_DAILY_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py"
    NWS_API_URL = "https://api.weather.gov"

    # IEM `daily.py` requires both the station's 3-letter local id (no 'K')
    # and the state-level ASOS network id. Mapping from our 4-letter ICAO
    # (KNYC, KLAX, ...) to (local_id, network).
    _DAILY_NETWORK_MAP: dict[str, tuple[str, str]] = {
        "KNYC": ("NYC", "NY_ASOS"),
        "KLAX": ("LAX", "CA_ASOS"),
        "KORD": ("ORD", "IL_ASOS"),
        "KAUS": ("AUS", "TX_ASOS"),
        "KIAH": ("IAH", "TX_ASOS"),
        "KMIA": ("MIA", "FL_ASOS"),
        "KPHX": ("PHX", "AZ_ASOS"),
        "KDEN": ("DEN", "CO_ASOS"),
        "KSEA": ("SEA", "WA_ASOS"),
        "KATL": ("ATL", "GA_ASOS"),
        "KBOS": ("BOS", "MA_ASOS"),
        "KDFW": ("DFW", "TX_ASOS"),
        "KPHL": ("PHL", "PA_ASOS"),
        "KDCA": ("DCA", "VA_ASOS"),
        "KMSP": ("MSP", "MN_ASOS"),
        "KDTW": ("DTW", "MI_ASOS"),
        "KSAN": ("SAN", "CA_ASOS"),
        "KSAT": ("SAT", "TX_ASOS"),
        "KSFO": ("SFO", "CA_ASOS"),
    }

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

    async def get_daily_summaries(
        self, station: str, start: date, end: date
    ) -> list[DailySummary]:
        """Fetch daily aggregated observations from IEM's daily.py.

        Used for bulk historical climatology fetches. Pass start/end inclusive.
        Station must be one of the 4-letter ICAO codes in _DAILY_NETWORK_MAP.

        Returns rows in chronological order. Empty list on error or unknown
        station — never raises so bootstrap scripts can keep going.
        """
        local_network = self._DAILY_NETWORK_MAP.get(station)
        if local_network is None:
            logger.warning("daily_summary_unknown_station", station=station)
            return []

        local_id, network = local_network
        logger.info(
            "fetching_daily_summaries",
            station=station,
            network=network,
            start=str(start),
            end=str(end),
        )
        try:
            response = await self.client.get(
                self.IEM_DAILY_URL,
                params={
                    "station": local_id,
                    "network": network,
                    "year1": str(start.year),
                    "month1": str(start.month),
                    "day1": str(start.day),
                    "year2": str(end.year),
                    "month2": str(end.month),
                    "day2": str(end.day),
                    "format": "comma",
                    # Default response includes max/min temp, precip_in, snow_in,
                    # plus climatology columns. Adding 'var' filters drops the
                    # extra fields, so we leave the default and parse what we
                    # need from the CSV header.
                },
            )
            response.raise_for_status()
            return self._parse_daily_csv(response.text, station)
        except Exception as e:
            logger.error(
                "daily_summary_fetch_error",
                station=station,
                error=str(e),
            )
            return []

    @staticmethod
    def _parse_daily_csv(text: str, station: str) -> list[DailySummary]:
        rows: list[DailySummary] = []
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            day_str = row.get("day", "").strip()
            if not day_str:
                continue
            try:
                obs_date = date.fromisoformat(day_str)
            except ValueError:
                continue
            rows.append(
                DailySummary(
                    station=station,
                    obs_date=obs_date,
                    high_temp_f=_parse_float(row.get("max_temp_f", "")),
                    low_temp_f=_parse_float(row.get("min_temp_f", "")),
                    precip_in=_parse_float(row.get("precip_in", "")),
                    snow_in=_parse_float(row.get("snow_in", "")),
                )
            )
        # Sort by obs_date so callers can rely on chronological ordering
        # (IEM normally returns data in order, but don't depend on it).
        rows.sort(key=lambda r: r.obs_date)
        return rows

    @staticmethod
    def _c_to_f(celsius: float | None) -> float | None:
        if celsius is None:
            return None
        return round(celsius * 9 / 5 + 32, 1)

    async def close(self) -> None:
        await self.client.aclose()
