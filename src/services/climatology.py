"""Compute and serve climatological priors for climate markets.

Phase 2b approach:
- Pull N years of daily observations per station from IEM via NWSClient.
- For each (station, calendar_day, market_type), fit a normal prior using
  a 31-day rolling window centered on that calendar day across all years.
- Store (mean, std, n) in climatology_stats.
- ClimateEstimator queries this table to:
  1. Inflate forecast sigma when lead time is large or uncertain.
  2. Provide a fallback prior when forecast data is missing entirely.

Why a 31-day window:
- Smooths out one-off anomalies (a single 95F day in May).
- Wide enough to give n ~ 30 * years_of_data observations per cell.
- Narrow enough to capture seasonal slope (10-day windows are too noisy,
  90-day windows wash out late-spring vs early-summer differences).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.climatology import ClimatologyStat, HistoricalObservation
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Calendar-day window used for climatology computation.
WINDOW_HALF_WIDTH_DAYS = 15  # 15 + 1 + 15 = 31 days

# Minimum number of observations required to publish a stat. Below this,
# we don't trust the std and ClimateEstimator falls back to a default.
MIN_OBS_FOR_STAT = 20

# Floors to keep climatology sigma physically reasonable (and to avoid
# divide-by-zero downstream for cities with extremely consistent weather).
SIGMA_FLOOR_F = 1.5  # temperature
SIGMA_FLOOR_PRECIP_IN = 0.05  # snow / rain — distribution is heavy-tailed


@dataclass(frozen=True)
class ClimatologyValue:
    mean: float
    std: float
    n_obs: int


class ClimatologyService:
    """Read/write API over climatology_stats and historical_observations."""

    MARKET_TYPE_TO_FIELD: dict[str, str] = {
        "high_temp": "high_temp_f",
        "low_temp": "low_temp_f",
        "snow": "snow_in",
        "rain": "precip_in",
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Ingest
    # ------------------------------------------------------------------

    async def upsert_observations(
        self, observations: Iterable[HistoricalObservation]
    ) -> int:
        """Insert raw daily observations, ignoring duplicates by (station, date).

        Returns the number of rows attempted (not necessarily inserted, since
        SQLite ON CONFLICT DO NOTHING swallows dupes).
        """
        rows = [
            {
                "station": o.station,
                "obs_date": o.obs_date,
                "high_temp_f": o.high_temp_f,
                "low_temp_f": o.low_temp_f,
                "precip_in": o.precip_in,
                "snow_in": o.snow_in,
            }
            for o in observations
        ]
        if not rows:
            return 0

        stmt = sqlite_insert(HistoricalObservation).values(rows)
        # SQLite ON CONFLICT DO NOTHING — keep oldest copy, newer fetches
        # of the same date are no-ops.
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["station", "obs_date"],
        )
        await self.session.execute(stmt)
        return len(rows)

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    async def recompute_for_station(self, station: str) -> int:
        """Recompute climatology_stats for a single station, all market types.

        Returns the number of (calendar_day, market_type) cells written.
        """
        observations = await self._load_observations(station)
        if not observations:
            return 0

        cells_written = 0
        for market_type, field in self.MARKET_TYPE_TO_FIELD.items():
            samples_by_day = self._bucket_by_day_with_window(observations, field)
            for (month, day), samples in samples_by_day.items():
                if len(samples) < MIN_OBS_FOR_STAT:
                    continue
                mean = statistics.fmean(samples)
                std = statistics.pstdev(samples) if len(samples) > 1 else 0.0
                floor = (
                    SIGMA_FLOOR_F
                    if market_type in ("high_temp", "low_temp")
                    else SIGMA_FLOOR_PRECIP_IN
                )
                std = max(std, floor)
                await self._upsert_stat(
                    station=station,
                    month=month,
                    day=day,
                    market_type=market_type,
                    n_obs=len(samples),
                    mean=mean,
                    std=std,
                )
                cells_written += 1

        return cells_written

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get(
        self, station: str, target_date: date, market_type: str
    ) -> ClimatologyValue | None:
        # Map Feb 29 to Feb 28 for stable lookup.
        month = target_date.month
        day = target_date.day if not (month == 2 and target_date.day == 29) else 28

        stmt = select(ClimatologyStat).where(
            ClimatologyStat.station == station,
            ClimatologyStat.month == month,
            ClimatologyStat.day == day,
            ClimatologyStat.market_type == market_type,
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return ClimatologyValue(mean=row.mean, std=row.std, n_obs=row.n_obs)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _load_observations(self, station: str) -> list[HistoricalObservation]:
        stmt = select(HistoricalObservation).where(
            HistoricalObservation.station == station
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _bucket_by_day_with_window(
        observations: list[HistoricalObservation], field: str
    ) -> dict[tuple[int, int], list[float]]:
        """Group observations into (month, day) buckets using a 31-day window.

        Each (month, day) cell receives samples from
        [date - WINDOW_HALF_WIDTH_DAYS, date + WINDOW_HALF_WIDTH_DAYS]
        across all years.
        """
        # Pre-bucket each observation by its actual (month, day) — using day_of_year
        # would complicate leap-year handling.
        per_day: dict[tuple[int, int], list[float]] = {}
        for obs in observations:
            value = getattr(obs, field)
            if value is None:
                continue
            key = (obs.obs_date.month, obs.obs_date.day)
            per_day.setdefault(key, []).append(value)

        # For each canonical calendar day, pull samples from the surrounding
        # +/- WINDOW_HALF_WIDTH_DAYS by walking dates in 2001 (a non-leap year)
        # and aggregating.
        from calendar import monthrange

        windowed: dict[tuple[int, int], list[float]] = {}
        for month in range(1, 13):
            for day in range(1, monthrange(2001, month)[1] + 1):
                center = date(2001, month, day)
                bucket: list[float] = []
                for offset in range(
                    -WINDOW_HALF_WIDTH_DAYS, WINDOW_HALF_WIDTH_DAYS + 1
                ):
                    nb = center + timedelta(days=offset)
                    bucket.extend(per_day.get((nb.month, nb.day), []))
                if bucket:
                    windowed[(month, day)] = bucket
        return windowed

    async def _upsert_stat(
        self,
        *,
        station: str,
        month: int,
        day: int,
        market_type: str,
        n_obs: int,
        mean: float,
        std: float,
    ) -> None:
        stmt = sqlite_insert(ClimatologyStat).values(
            station=station,
            month=month,
            day=day,
            market_type=market_type,
            n_obs=n_obs,
            mean=mean,
            std=std,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["station", "month", "day", "market_type"],
            set_={
                "n_obs": stmt.excluded.n_obs,
                "mean": stmt.excluded.mean,
                "std": stmt.excluded.std,
            },
        )
        await self.session.execute(stmt)
