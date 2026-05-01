from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class ClimateTickerInfo(BaseModel, frozen=True):
    market_type: Literal["high_temp", "low_temp", "snow", "rain"]
    city_code: str
    event_date: date | None = None
    threshold: float
    bracket_type: Literal["between", "under", "above_equal"]


# NWS ASOS station IDs keyed by Kalshi city codes
_STATION_MAP: dict[str, str] = {
    "NY": "KNYC",
    "NYC": "KNYC",
    "LAX": "KLAX",
    "LA": "KLAX",
    "CHI": "KORD",
    "AUS": "KAUS",
    "IAH": "KIAH",
    "HOU": "KIAH",
    "MIA": "KMIA",
    "PHX": "KPHX",
    "DEN": "KDEN",
    "SEA": "KSEA",
    "ATL": "KATL",
    "BOS": "KBOS",
    "DFW": "KDFW",
    "DAL": "KDFW",
    "PHL": "KPHL",
    "DCA": "KDCA",
    "DC": "KDCA",
    "MSP": "KMSP",
    "DTW": "KDTW",
    "SAN": "KSAN",
    "SAT": "KSAT",
}

_CITY_DISPLAY: dict[str, str] = {
    "NY": "New York",
    "NYC": "New York",
    "LAX": "Los Angeles",
    "LA": "Los Angeles",
    "CHI": "Chicago",
    "AUS": "Austin",
    "IAH": "Houston",
    "HOU": "Houston",
    "MIA": "Miami",
    "PHX": "Phoenix",
    "DEN": "Denver",
    "SEA": "Seattle",
    "ATL": "Atlanta",
    "BOS": "Boston",
    "DFW": "Dallas",
    "DAL": "Dallas",
    "PHL": "Philadelphia",
    "DCA": "Washington DC",
    "DC": "Washington DC",
    "MSP": "Minneapolis",
    "DTW": "Detroit",
    "SAN": "San Diego",
    "SAT": "San Antonio",
}

# Known city codes sorted longest-first so "NYC" matches before "NY"
_CITY_CODES_BY_LENGTH = sorted(_STATION_MAP.keys(), key=len, reverse=True)

# Regex for date portion: e.g., 26FEB22, 26FEB2026
_DATE_RE = re.compile(r"(\d{1,2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{2,4})")


def _parse_date(ticker: str) -> date | None:
    m = _DATE_RE.search(ticker)
    if not m:
        return None
    first = int(m.group(1))
    month_str = m.group(2)
    third_raw = m.group(3)
    third = int(third_raw)
    month_map = {
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
    }
    if len(third_raw) >= 4:
        # DDMMMYYYY (e.g., 22FEB2026): first=day, third=full year
        day, year = first, third
    else:
        # YYMMMDD (e.g., 26FEB22): first=2-digit year, third=day
        year, day = 2000 + first, third
    try:
        return date(year, month_map[month_str], day)
    except ValueError:
        return None


def parse_ticker_date(ticker: str) -> date | None:
    """Extract a date from any Kalshi ticker string."""
    return _parse_date(ticker)


def _extract_city_code(ticker: str) -> str | None:
    upper = ticker.upper()
    for code in _CITY_CODES_BY_LENGTH:
        if code in upper:
            return code
    return None


def _extract_threshold_and_bracket(
    ticker: str, market_type: str | None = None
) -> tuple[float, Literal["between", "under", "above_equal"]] | None:
    # Look for bracket prefix + number: -B38.5, -T38, -A40
    m = re.search(r"-([BTA])(\d+\.?\d*)\s*$", ticker.upper())
    if m:
        bracket_char = m.group(1)
        value = float(m.group(2))
        bracket_map: dict[str, Literal["between", "under", "above_equal"]] = {
            "B": "between",
            "T": "under",
            "A": "above_equal",
        }
        return value, bracket_map[bracket_char]

    # Trailing number without B/T/A prefix (e.g., KXNYCSNOWM-26FEB-25.0)
    # Snow/rain markets without prefix are directional: "above X inches"
    # Temperature markets without prefix default to "above_equal"
    m = re.search(r"-(\d+\.?\d*)\s*$", ticker)
    if m:
        value = float(m.group(1))
        if market_type in ("snow", "rain"):
            return value, "above_equal"
        return value, "above_equal"

    return None


def _detect_market_type(ticker: str) -> Literal["high_temp", "low_temp", "snow", "rain"] | None:
    upper = ticker.upper()
    if "HIGH" in upper:
        return "high_temp"
    if "LOW" in upper:
        return "low_temp"
    if "SNOW" in upper:
        return "snow"
    if "RAIN" in upper or "PRECIP" in upper:
        return "rain"
    return None


def parse_climate_ticker(ticker: str) -> ClimateTickerInfo | None:
    if not ticker:
        return None

    market_type = _detect_market_type(ticker)
    if market_type is None:
        return None

    city_code = _extract_city_code(ticker)
    if city_code is None:
        return None

    result = _extract_threshold_and_bracket(ticker, market_type)
    if result is None:
        return None

    threshold, bracket_type = result
    event_date = _parse_date(ticker)

    return ClimateTickerInfo(
        market_type=market_type,
        city_code=city_code,
        event_date=event_date,
        threshold=threshold,
        bracket_type=bracket_type,
    )


# NWS WFO codes for CLI report lookups
_WFO_MAP: dict[str, str] = {
    "NY": "okx",
    "NYC": "okx",
    "LAX": "lox",
    "LA": "lox",
    "CHI": "lot",
    "AUS": "ewx",
    "IAH": "hgx",
    "HOU": "hgx",
    "MIA": "mfl",
    "PHX": "psr",
    "DEN": "bou",
    "SEA": "sew",
    "ATL": "ffc",
    "BOS": "box",
    "DFW": "fwd",
    "DAL": "fwd",
    "PHL": "phi",
    "DCA": "lwx",
    "DC": "lwx",
    "MSP": "mpx",
    "DTW": "dtx",
    "SAN": "sgx",
    "SAT": "ewx",
}

# CLI station names used in NWS daily climate reports
_CLI_STATION_MAP: dict[str, str] = {
    "NY": "CLINYC",
    "NYC": "CLINYC",
    "LAX": "CLILAX",
    "LA": "CLILAX",
    "CHI": "CLIORD",
    "AUS": "CLIAUS",
    "IAH": "CLIIAH",
    "HOU": "CLIIAH",
    "MIA": "CLIMIA",
    "PHX": "CLIPHX",
    "DEN": "CLIDEN",
    "SEA": "CLISEA",
    "ATL": "CLIATL",
    "BOS": "CLIBOS",
    "DFW": "CLIDFW",
    "DAL": "CLIDFW",
    "PHL": "CLIPHL",
    "DCA": "CLIDCA",
    "DC": "CLIDCA",
    "MSP": "CLIMSP",
    "DTW": "CLIDTW",
    "SAN": "CLISAN",
    "SAT": "CLISAT",
}


def get_nws_station(city_code: str) -> str | None:
    return _STATION_MAP.get(city_code.upper())


def get_cli_station(city_code: str) -> str | None:
    return _CLI_STATION_MAP.get(city_code.upper())


def get_wfo_code(city_code: str) -> str | None:
    return _WFO_MAP.get(city_code.upper())


def get_city_display_name(city_code: str) -> str | None:
    return _CITY_DISPLAY.get(city_code.upper())
