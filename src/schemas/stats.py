from pydantic import BaseModel


class StatsSummary(BaseModel):
    total_recommendations: int
    executed_count: int
    win_count: int
    loss_count: int
    win_rate: float
    total_profit: float
    avg_edge: float


class DailyStats(BaseModel):
    date: str
    recommendations: int
    executed: int
    wins: int
    losses: int
    profit: float


class StatsSummaryResponse(BaseModel):
    summary: StatsSummary


class StatsHistoryResponse(BaseModel):
    history: list[DailyStats]
