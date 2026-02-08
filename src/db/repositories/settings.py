from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.settings import SettingsModel


class SettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self) -> SettingsModel:
        result = await self.session.execute(select(SettingsModel).where(SettingsModel.id == 1))
        row = result.scalar_one_or_none()
        if row is None:
            row = SettingsModel(id=1)
            self.session.add(row)
            await self.session.flush()
        return row

    async def update(self, updates: dict) -> SettingsModel:
        row = await self.get()
        for key, value in updates.items():
            if value is not None and hasattr(row, key):
                setattr(row, key, value)
        row.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return row
