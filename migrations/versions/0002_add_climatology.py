"""climate phase 2b: historical observations + climatology stats

Revision ID: 0002_climatology
Revises: 0001_climate_phase1
Create Date: 2026-05-01
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_climatology"
down_revision = "0001_climate_phase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "historical_observations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station", sa.String(length=8), nullable=False),
        sa.Column("obs_date", sa.Date(), nullable=False),
        sa.Column("high_temp_f", sa.Float(), nullable=True),
        sa.Column("low_temp_f", sa.Float(), nullable=True),
        sa.Column("precip_in", sa.Float(), nullable=True),
        sa.Column("snow_in", sa.Float(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("station", "obs_date", name="uq_obs_station_date"),
    )
    op.create_index(
        "ix_historical_observations_station",
        "historical_observations",
        ["station"],
    )
    op.create_index(
        "ix_historical_observations_obs_date",
        "historical_observations",
        ["obs_date"],
    )

    op.create_table(
        "climatology_stats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station", sa.String(length=8), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("day", sa.Integer(), nullable=False),
        sa.Column("market_type", sa.String(length=16), nullable=False),
        sa.Column("n_obs", sa.Integer(), nullable=False),
        sa.Column("mean", sa.Float(), nullable=False),
        sa.Column("std", sa.Float(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "station",
            "month",
            "day",
            "market_type",
            name="uq_climo_station_day_type",
        ),
    )
    op.create_index(
        "ix_climatology_stats_station",
        "climatology_stats",
        ["station"],
    )


def downgrade() -> None:
    op.drop_index("ix_climatology_stats_station", table_name="climatology_stats")
    op.drop_table("climatology_stats")
    op.drop_index(
        "ix_historical_observations_obs_date",
        table_name="historical_observations",
    )
    op.drop_index(
        "ix_historical_observations_station",
        table_name="historical_observations",
    )
    op.drop_table("historical_observations")
