from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Scan(BaseModel):
    id: str
    status: Literal["running", "completed", "failed"]
    started_at: datetime
    completed_at: datetime | None = None
    markets_scanned: int
    markets_filtered: int
    recommendations_generated: int

    model_config = {"from_attributes": True}


class ScanDetail(Scan):
    errors: list[str] = []

    model_config = {"from_attributes": True}


class ScanStartResponse(BaseModel):
    scan_id: str
    status: str = "started"


class ScanListResponse(BaseModel):
    scans: list[Scan]
    total: int


class ScanDetailResponse(BaseModel):
    scan: ScanDetail
