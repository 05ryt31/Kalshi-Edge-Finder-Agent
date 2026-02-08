from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.recommendation import RecommendationRepository
from src.dependencies import get_db
from src.schemas.recommendation import (
    Recommendation,
    RecommendationDetail,
    RecommendationDetailResponse,
    RecommendationListResponse,
    RecommendationUpdateRequest,
)

router = APIRouter()


@router.get("", response_model=RecommendationListResponse)
async def list_recommendations(
    status: str | None = Query(None),
    strength: str | None = Query(None),
    min_edge: float | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> RecommendationListResponse:
    repo = RecommendationRepository(db)
    recs, total = await repo.list(
        status=status,
        strength=strength,
        min_edge=min_edge,
        limit=limit,
        offset=offset,
    )
    return RecommendationListResponse(
        recommendations=[Recommendation.model_validate(r) for r in recs],
        total=total,
    )


@router.get("/{rec_id}", response_model=RecommendationDetailResponse)
async def get_recommendation(
    rec_id: str,
    db: AsyncSession = Depends(get_db),
) -> RecommendationDetailResponse:
    repo = RecommendationRepository(db)
    rec = await repo.get(rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return RecommendationDetailResponse(
        recommendation=RecommendationDetail.model_validate(rec),
    )


@router.patch("/{rec_id}", response_model=dict)
async def update_recommendation(
    rec_id: str,
    body: RecommendationUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    repo = RecommendationRepository(db)
    rec = await repo.update_status(rec_id, body.status)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return {"recommendation": Recommendation.model_validate(rec).model_dump()}
