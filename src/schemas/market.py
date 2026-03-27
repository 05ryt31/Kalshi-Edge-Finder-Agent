from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, computed_field

from src.utils.ticker_parser import ClimateTickerInfo


class Market(BaseModel):
    ticker: str
    event_ticker: str
    title: str
    subtitle: str | None = None
    category: Literal["climate", "economics", "sports", "companies", "other"]
    status: Literal["open", "active", "closed", "settled"]
    yes_ask: int
    no_ask: int
    yes_bid: int
    no_bid: int
    last_price: int
    volume: int
    volume_24h: int
    close_time: datetime
    expiration_time: datetime
    climate_info: ClimateTickerInfo | None = None

    @computed_field
    @property
    def yes_multiplier(self) -> float:
        return round(100 / self.yes_ask, 2) if self.yes_ask > 0 else 0

    @computed_field
    @property
    def no_multiplier(self) -> float:
        return round(100 / self.no_ask, 2) if self.no_ask > 0 else 0

    @computed_field
    @property
    def is_day_of_event(self) -> bool:
        if self.climate_info is None or self.climate_info.event_date is None:
            return False
        return self.climate_info.event_date == date.today()

    @computed_field
    @property
    def is_past_event(self) -> bool:
        if self.climate_info is None or self.climate_info.event_date is None:
            return False
        return self.climate_info.event_date < date.today()

    @computed_field
    @property
    def is_extreme_price(self) -> bool:
        return self.yes_ask >= 95 or self.yes_ask <= 5

    model_config = {"from_attributes": True}


class MarketListResponse(BaseModel):
    markets: list[Market]
    total: int


class MarketDetailResponse(BaseModel):
    market: Market
