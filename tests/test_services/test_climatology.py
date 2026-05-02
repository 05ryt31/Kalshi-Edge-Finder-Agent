"""Tests for ClimatologyService — historical observation upsert,
window-based climatology computation, and read API.
"""
from __future__ import annotations

from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models.base import Base
from src.models.climatology import HistoricalObservation
from src.services.climatology import (
    MIN_OBS_FOR_STAT,
    SIGMA_FLOOR_F,
    ClimatologyService,
)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _obs(station: str, d: date, *, high: float, low: float, snow=0.0, precip=0.0):
    return HistoricalObservation(
        station=station,
        obs_date=d,
        high_temp_f=high,
        low_temp_f=low,
        snow_in=snow,
        precip_in=precip,
    )


class TestUpsertObservations:
    @pytest.mark.asyncio
    async def test_inserts_rows(self, session):
        service = ClimatologyService(session)
        observations = [_obs("KNYC", date(2020, 7, 15), high=85, low=70)]
        await service.upsert_observations(observations)
        await session.commit()

        loaded = await service._load_observations("KNYC")
        assert len(loaded) == 1
        assert loaded[0].high_temp_f == 85

    @pytest.mark.asyncio
    async def test_upsert_is_idempotent(self, session):
        service = ClimatologyService(session)
        d = date(2020, 7, 15)
        await service.upsert_observations([_obs("KNYC", d, high=85, low=70)])
        await service.upsert_observations([_obs("KNYC", d, high=99, low=99)])
        await session.commit()

        loaded = await service._load_observations("KNYC")
        # ON CONFLICT DO NOTHING — keeps original row.
        assert len(loaded) == 1
        assert loaded[0].high_temp_f == 85


class TestRecomputeForStation:
    def _generate_july_data(self, years: int) -> list[HistoricalObservation]:
        """Synthetic July high temperatures: mean 85, std 4."""
        import random

        random.seed(42)
        rows = []
        for year in range(2020 - years + 1, 2020 + 1):
            for day in range(1, 32):
                rows.append(
                    _obs(
                        "KNYC",
                        date(year, 7, day),
                        high=85 + random.gauss(0, 4),
                        low=70 + random.gauss(0, 3),
                    )
                )
        return rows

    @pytest.mark.asyncio
    async def test_recompute_writes_cells(self, session):
        service = ClimatologyService(session)
        rows = self._generate_july_data(years=5)
        await service.upsert_observations(rows)
        await session.commit()

        cells = await service.recompute_for_station("KNYC")
        await session.commit()

        # 4 market types × ~31 calendar days that have enough samples.
        assert cells > 60
        # high_temp lookup near mid-July should be ~85F with std ~4F.
        result = await service.get("KNYC", date(2026, 7, 15), "high_temp")
        assert result is not None
        assert 82 < result.mean < 88
        assert 2.5 < result.std < 6.0
        assert result.n_obs >= MIN_OBS_FOR_STAT

    @pytest.mark.asyncio
    async def test_recompute_skips_underpopulated_cells(self, session):
        service = ClimatologyService(session)
        # Only 5 observations on a single day — below MIN_OBS_FOR_STAT.
        rows = [_obs("KNYC", date(2020, 7, day), high=85, low=70) for day in range(1, 6)]
        await service.upsert_observations(rows)
        await session.commit()

        cells = await service.recompute_for_station("KNYC")
        # Even with the 31-day window, only 5 days * 4 market_types
        # contribute samples — still under MIN_OBS_FOR_STAT for std.
        assert cells == 0

    @pytest.mark.asyncio
    async def test_sigma_floor_enforced(self, session):
        """Constant data → std=0; floor must clip up to SIGMA_FLOOR_F."""
        service = ClimatologyService(session)
        rows = []
        # Many years of identical July data — std would be 0 without floor.
        for year in range(2010, 2025):
            for day in range(1, 32):
                rows.append(_obs("KNYC", date(year, 7, day), high=85.0, low=70.0))
        await service.upsert_observations(rows)
        await session.commit()

        await service.recompute_for_station("KNYC")
        await session.commit()

        result = await service.get("KNYC", date(2026, 7, 15), "high_temp")
        assert result is not None
        assert result.std >= SIGMA_FLOOR_F


class TestLeapDayHandling:
    @pytest.mark.asyncio
    async def test_feb_29_maps_to_feb_28(self, session):
        service = ClimatologyService(session)
        # 30 years of late Feb data so the 31-day window has enough samples.
        rows = []
        for year in range(1995, 2025):
            for day in range(15, 29):
                rows.append(_obs("KNYC", date(year, 2, day), high=40, low=30))
        await service.upsert_observations(rows)
        await session.commit()

        await service.recompute_for_station("KNYC")
        await session.commit()

        # Feb 29 query should not return None.
        result = await service.get("KNYC", date(2024, 2, 29), "high_temp")
        assert result is not None
