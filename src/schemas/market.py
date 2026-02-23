from datetime import datetime
from typing import Literal

from pydantic import BaseModel, computed_field


class Market(BaseModel):
    ticker: str
    event_ticker: str
    title: str
    subtitle: str | None = None
    category: Literal["climate", "economics", "sports", "companies", "other"]
    status: Literal["open", "closed", "settled"]
    yes_ask: int
    no_ask: int
    yes_bid: int
    no_bid: int
    last_price: int
    volume: int
    volume_24h: int
    close_time: datetime
    expiration_time: datetime

    @computed_field
    @property
    def yes_multiplier(self) -> float:
        return round(100 / self.yes_ask, 2) if self.yes_ask > 0 else 0

    @computed_field
    @property
    def no_multiplier(self) -> float:
        return round(100 / self.no_ask, 2) if self.no_ask > 0 else 0

    model_config = {"from_attributes": True}


class MarketListResponse(BaseModel):
    markets: list[Market]
    total: int


class MarketDetailResponse(BaseModel):
    market: Market
