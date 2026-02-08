import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON

from src.models.base import Base


class RecommendationModel(Base):
    __tablename__ = "recommendations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(String, ForeignKey("scans.id"), nullable=True)
    market_ticker = Column(String(100), nullable=False)
    market_title = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False)
    market_price = Column(Integer, nullable=False)
    estimated_probability = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    edge = Column(Float, nullable=False)
    strength = Column(String(10), nullable=False)
    suggested_amount = Column(Float, nullable=False)
    reasoning = Column(Text, nullable=True)
    research_data = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
