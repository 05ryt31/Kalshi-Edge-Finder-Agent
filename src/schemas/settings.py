from typing import Literal

from pydantic import BaseModel


class Settings(BaseModel):
    edge_threshold: float = 0.05
    min_multiplier: float = 1.5
    max_days_to_close: int = 7
    min_volume: int = 100
    max_bet_amount: float = 25.0
    categories: list[str] = ["climate"]
    auto_execute: bool = False
    auto_execute_strength: Literal["strong", "medium", "weak"] = "strong"
    scan_interval_hours: int = 1
    # Paper trading: when True, recommendations are logged but never executed.
    # Always overrides auto_execute. Default True until calibration is proven.
    paper_trading: bool = True

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    edge_threshold: float | None = None
    min_multiplier: float | None = None
    max_days_to_close: int | None = None
    min_volume: int | None = None
    max_bet_amount: float | None = None
    categories: list[str] | None = None
    auto_execute: bool | None = None
    auto_execute_strength: Literal["strong", "medium", "weak"] | None = None
    scan_interval_hours: int | None = None
    paper_trading: bool | None = None


class SettingsResponse(BaseModel):
    settings: Settings
