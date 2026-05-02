"""SQLAlchemy models for climate historical data and climatology stats.

historical_observations: raw daily ASOS aggregates (one row per
    (station, date)) used as the source of truth for climatology fits and
    backtesting.

climatology_stats: precomputed (mean, std, n) per
    (station, month, day, market_type), derived from a 31-day rolling window
    centered on each calendar day. Read by ClimateEstimator at scoring time.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, Integer, String, UniqueConstraint

from src.models.base import Base


class HistoricalObservation(Base):
    __tablename__ = "historical_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station = Column(String(8), nullable=False, index=True)
    obs_date = Column(Date, nullable=False, index=True)
    high_temp_f = Column(Float, nullable=True)
    low_temp_f = Column(Float, nullable=True)
    precip_in = Column(Float, nullable=True)
    snow_in = Column(Float, nullable=True)
    fetched_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("station", "obs_date", name="uq_obs_station_date"),
    )


class ClimatologyStat(Base):
    __tablename__ = "climatology_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station = Column(String(8), nullable=False, index=True)
    # Calendar month (1-12) and day (1-31) for the window center. We don't
    # use day_of_year so leap-year edge cases stay simple — Feb 29 maps to
    # the Feb 28 window.
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    market_type = Column(String(16), nullable=False)  # high_temp/low_temp/snow/rain
    n_obs = Column(Integer, nullable=False)
    mean = Column(Float, nullable=False)
    std = Column(Float, nullable=False)
    computed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "station",
            "month",
            "day",
            "market_type",
            name="uq_climo_station_day_type",
        ),
    )
