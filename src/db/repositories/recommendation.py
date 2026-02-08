from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.recommendation import RecommendationModel


class RecommendationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> RecommendationModel:
        rec = RecommendationModel(**data)
        self.session.add(rec)
        await self.session.flush()
        return rec

    async def get(self, rec_id: str) -> RecommendationModel | None:
        return await self.session.get(RecommendationModel, rec_id)

    async def list(
        self,
        *,
        status: str | None = None,
        strength: str | None = None,
        min_edge: float | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[RecommendationModel], int]:
        query = select(RecommendationModel)

        if status:
            query = query.where(RecommendationModel.status == status)
        if strength:
            query = query.where(RecommendationModel.strength == strength)
        if min_edge is not None:
            query = query.where(RecommendationModel.edge >= min_edge)

        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        result = await self.session.execute(
            query.order_by(RecommendationModel.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_by_scan(self, scan_id: str) -> list[RecommendationModel]:
        result = await self.session.execute(
            select(RecommendationModel)
            .where(RecommendationModel.scan_id == scan_id)
            .order_by(RecommendationModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_category(
        self,
        category: str,
        *,
        limit: int = 5,
        exclude_scan_id: str | None = None,
    ) -> list[RecommendationModel]:
        query = select(RecommendationModel).where(RecommendationModel.category == category)
        if exclude_scan_id:
            query = query.where(RecommendationModel.scan_id != exclude_scan_id)
        result = await self.session.execute(
            query.order_by(RecommendationModel.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(self, rec_id: str, status: str) -> RecommendationModel | None:
        rec = await self.get(rec_id)
        if rec is None:
            return None
        rec.status = status
        rec.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return rec
