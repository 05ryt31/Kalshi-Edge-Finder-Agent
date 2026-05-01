from datetime import datetime

from pydantic import BaseModel


class ScanReportMetadata(BaseModel):
    scan_id: str
    timestamp: datetime
    markets_scanned: int
    markets_filtered: int
    recommendations_count: int
    categories_scanned: list[str]

    model_config = {"frozen": True}
