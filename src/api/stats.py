from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_db
from src.models.recommendation import RecommendationModel
from src.schemas.stats import StatsSummary, StatsSummaryResponse

router = APIRouter()


@router.get("/summary", response_model=StatsSummaryResponse)
async def get_stats_summary(
    db: AsyncSession = Depends(get_db),
) -> StatsSummaryResponse:
    result = await db.execute(select(RecommendationModel))
    recs = result.scalars().all()

    total = len(recs)
    executed = [r for r in recs if r.status == "executed"]
    executed_count = len(executed)

    # Placeholder: win/loss tracking requires settlement data (Phase 2)
    win_count = 0
    loss_count = 0
    win_rate = 0.0
    total_profit = 0.0
    avg_edge = sum(r.edge for r in recs) / total if total > 0 else 0.0

    return StatsSummaryResponse(
        summary=StatsSummary(
            total_recommendations=total,
            executed_count=executed_count,
            win_count=win_count,
            loss_count=loss_count,
            win_rate=win_rate,
            total_profit=total_profit,
            avg_edge=round(avg_edge, 4),
        )
    )
