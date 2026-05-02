"""Bootstrap historical climatology from IEM.

Usage:
    python -m scripts.bootstrap_climatology
    python -m scripts.bootstrap_climatology --years 10 --stations KNYC,KSFO

Fetches N years of daily observations for the configured ASOS stations,
upserts them into historical_observations, and recomputes climatology_stats.

Idempotent — safe to re-run; existing rows are skipped (observations) or
updated (climatology_stats).
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import date, timedelta

from src.clients.nws import NWSClient
from src.db.session import async_session_factory, create_tables
from src.models.climatology import HistoricalObservation
from src.services.climatology import ClimatologyService
from src.utils.logger import get_logger

logger = get_logger(__name__)


# Default station set — same cities ClimateEstimator routes traffic to.
DEFAULT_STATIONS = [
    "KNYC", "KLAX", "KORD", "KMIA", "KSFO",
    "KIAH", "KDFW", "KAUS",
]


@dataclass
class BootstrapResult:
    station: str
    days_fetched: int
    cells_written: int


async def bootstrap_one(
    nws: NWSClient,
    station: str,
    years: int,
) -> BootstrapResult:
    today = date.today()
    # Use complete calendar years to avoid partial-year warm-month bias.
    start = date(today.year - years, 1, 1)
    # Cap end at yesterday to ensure data is settled.
    end = today - timedelta(days=1)

    summaries = await nws.get_daily_summaries(station, start, end)
    if not summaries:
        logger.warning("bootstrap_no_data", station=station)
        return BootstrapResult(station=station, days_fetched=0, cells_written=0)

    async with async_session_factory() as session:
        service = ClimatologyService(session)
        observations = [
            HistoricalObservation(
                station=s.station,
                obs_date=s.obs_date,
                high_temp_f=s.high_temp_f,
                low_temp_f=s.low_temp_f,
                precip_in=s.precip_in,
                snow_in=s.snow_in,
            )
            for s in summaries
        ]
        await service.upsert_observations(observations)
        await session.commit()

    async with async_session_factory() as session:
        service = ClimatologyService(session)
        cells = await service.recompute_for_station(station)
        await session.commit()

    logger.info(
        "bootstrap_station_done",
        station=station,
        days=len(summaries),
        cells=cells,
    )
    return BootstrapResult(
        station=station,
        days_fetched=len(summaries),
        cells_written=cells,
    )


async def main(years: int, stations: list[str]) -> None:
    await create_tables()

    nws = NWSClient()
    try:
        for station in stations:
            try:
                result = await bootstrap_one(nws, station, years)
                print(
                    f"{result.station}: fetched {result.days_fetched} days, "
                    f"wrote {result.cells_written} climo cells"
                )
            except Exception as exc:
                logger.error(
                    "bootstrap_station_failed", station=station, error=str(exc)
                )
                print(f"{station}: FAILED ({exc})")
    finally:
        await nws.close()


def cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--years", type=int, default=10, help="Number of years of history"
    )
    parser.add_argument(
        "--stations",
        type=str,
        default=",".join(DEFAULT_STATIONS),
        help="Comma-separated 4-letter ICAO codes",
    )
    args = parser.parse_args()
    stations = [s.strip().upper() for s in args.stations.split(",") if s.strip()]
    asyncio.run(main(args.years, stations))


if __name__ == "__main__":
    cli()
