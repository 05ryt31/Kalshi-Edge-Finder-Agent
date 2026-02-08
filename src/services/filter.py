from datetime import datetime, timezone

from src.schemas.market import Market
from src.schemas.settings import Settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FilterService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def filter_markets(self, markets: list[Market]) -> list[Market]:
        filtered = [m for m in markets if self._passes_filters(m)]

        filtered.sort(
            key=lambda m: max(m.yes_multiplier, m.no_multiplier),
            reverse=True,
        )

        logger.info("filter_result", total=len(markets), filtered=len(filtered))
        return filtered

    def _passes_filters(self, market: Market) -> bool:
        if market.category not in self.settings.categories:
            return False

        max_multiplier = max(market.yes_multiplier, market.no_multiplier)
        if max_multiplier < self.settings.min_multiplier:
            return False

        days_to_close = (market.close_time - datetime.now(timezone.utc)).days
        if days_to_close > self.settings.max_days_to_close:
            return False
        if days_to_close < 0:
            return False

        if market.volume < self.settings.min_volume:
            return False

        return True
