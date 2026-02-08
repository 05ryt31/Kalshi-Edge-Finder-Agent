from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.settings import SettingsRepository
from src.dependencies import get_db
from src.schemas.settings import Settings, SettingsResponse, SettingsUpdate

router = APIRouter()


@router.get("", response_model=SettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    repo = SettingsRepository(db)
    row = await repo.get()
    return SettingsResponse(settings=Settings.model_validate(row))


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    repo = SettingsRepository(db)
    updates = body.model_dump(exclude_none=True)
    row = await repo.update(updates)
    return SettingsResponse(settings=Settings.model_validate(row))
