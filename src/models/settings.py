from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.dialects.sqlite import JSON

from src.models.base import Base


class SettingsModel(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, default=1)
    edge_threshold = Column(Float, nullable=False, default=0.20)
    min_multiplier = Column(Float, nullable=False, default=2.0)
    max_days_to_close = Column(Integer, nullable=False, default=7)
    min_volume = Column(Integer, nullable=False, default=100)
    max_bet_amount = Column(Float, nullable=False, default=100.0)
    categories = Column(JSON, nullable=False, default=lambda: ["climate", "economics"])
    auto_execute = Column(Boolean, nullable=False, default=False)
    auto_execute_strength = Column(String(10), nullable=False, default="strong")
    scan_interval_hours = Column(Integer, nullable=False, default=1)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
