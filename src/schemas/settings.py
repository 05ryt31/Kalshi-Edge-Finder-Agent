from typing import Literal

from pydantic import BaseModel


class Settings(BaseModel):
    edge_threshold: float = 0.20
    min_multiplier: float = 2.0
    max_days_to_close: int = 7
    min_volume: int = 100
    max_bet_amount: float = 100.0
    categories: list[str] = ["climate", "economics"]
    auto_execute: bool = False
    auto_execute_strength: Literal["strong", "medium", "weak"] = "strong"
    scan_interval_hours: int = 1

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


class SettingsResponse(BaseModel):
    settings: Settings
