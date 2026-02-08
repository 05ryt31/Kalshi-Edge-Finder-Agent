from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.recommendation import RecommendationRepository
from src.db.repositories.scan import ScanRepository
from src.db.session import async_session_factory
from src.dependencies import get_db
from src.schemas.scan import (
    Scan,
    ScanDetail,
    ScanDetailResponse,
    ScanListResponse,
    ScanStartResponse,
)
from src.utils.logger import get_logger
from src.worker.tasks import run_scan_task

logger = get_logger(__name__)

router = APIRouter()


@router.post("", response_model=ScanStartResponse)
async def start_scan(background_tasks: BackgroundTasks) -> ScanStartResponse:
    async with async_session_factory() as session:
        repo = ScanRepository(session)
        scan = await repo.create()
        scan_id = scan.id
        await session.commit()

    background_tasks.add_task(_run_scan_background, scan_id)
    return ScanStartResponse(scan_id=scan_id, status="started")


async def _run_scan_background(scan_id: str) -> None:
    try:
        await run_scan_task(scan_id=scan_id)
    except Exception as e:
        logger.error("background_scan_failed", scan_id=scan_id, error=str(e))


@router.get("", response_model=ScanListResponse)
async def list_scans(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ScanListResponse:
    repo = ScanRepository(db)
    scans, total = await repo.list(limit=limit, offset=offset)
    return ScanListResponse(
        scans=[Scan.model_validate(s) for s in scans],
        total=total,
    )


@router.get("/{scan_id}", response_model=ScanDetailResponse)
async def get_scan(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
) -> ScanDetailResponse:
    repo = ScanRepository(db)
    scan = await repo.get(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    scan_detail = ScanDetail(
        id=scan.id,
        status=scan.status,
        started_at=scan.started_at,
        completed_at=scan.completed_at,
        markets_scanned=scan.markets_scanned,
        markets_filtered=scan.markets_filtered,
        recommendations_generated=scan.recommendations_generated,
        errors=[scan.error_message] if scan.error_message else [],
    )
    return ScanDetailResponse(scan=scan_detail)
