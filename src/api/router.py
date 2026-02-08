from fastapi import APIRouter

from src.api.markets import router as markets_router
from src.api.recommendations import router as recommendations_router
from src.api.scans import router as scans_router
from src.api.settings import router as settings_router
from src.api.stats import router as stats_router

api_router = APIRouter()

api_router.include_router(markets_router, prefix="/markets", tags=["markets"])
api_router.include_router(scans_router, prefix="/scans", tags=["scans"])
api_router.include_router(recommendations_router, prefix="/recommendations", tags=["recommendations"])
api_router.include_router(settings_router, prefix="/settings", tags=["settings"])
api_router.include_router(stats_router, prefix="/stats", tags=["stats"])
