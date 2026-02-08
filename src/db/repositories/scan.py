from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.scan import ScanModel


class ScanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self) -> ScanModel:
        scan = ScanModel()
        self.session.add(scan)
        await self.session.flush()
        return scan

    async def get(self, scan_id: str) -> ScanModel | None:
        return await self.session.get(ScanModel, scan_id)

    async def list(self, limit: int = 20, offset: int = 0) -> tuple[list[ScanModel], int]:
        count_result = await self.session.execute(
            select(ScanModel).order_by(ScanModel.created_at.desc())
        )
        total = len(count_result.scalars().all())

        result = await self.session.execute(
            select(ScanModel)
            .order_by(ScanModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(
        self,
        scan: ScanModel,
        *,
        status: str | None = None,
        markets_scanned: int | None = None,
        markets_filtered: int | None = None,
        recommendations_generated: int | None = None,
        error_message: str | None = None,
    ) -> ScanModel:
        if status is not None:
            scan.status = status
        if markets_scanned is not None:
            scan.markets_scanned = markets_scanned
        if markets_filtered is not None:
            scan.markets_filtered = markets_filtered
        if recommendations_generated is not None:
            scan.recommendations_generated = recommendations_generated
        if error_message is not None:
            scan.error_message = error_message
        if status == "completed" or status == "failed":
            scan.completed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return scan
