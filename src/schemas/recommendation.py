from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from src.schemas.market import Market


class Recommendation(BaseModel):
    id: str
    scan_id: str | None = None
    market_ticker: str
    market_title: str
    category: str
    side: Literal["yes", "no"]
    market_price: int
    estimated_probability: float
    confidence: float
    edge: float
    strength: Literal["strong", "medium", "weak"]
    suggested_amount: float
    status: Literal["pending", "executed", "skipped", "expired"]
    created_at: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}


class RecommendationDetail(Recommendation):
    research_data: dict | None = None
    reasoning: str | None = None

    model_config = {"from_attributes": True}


class RecommendationUpdateRequest(BaseModel):
    status: Literal["executed", "skipped"]


class RecommendationListResponse(BaseModel):
    recommendations: list[Recommendation]
    total: int


class RecommendationDetailResponse(BaseModel):
    recommendation: RecommendationDetail
