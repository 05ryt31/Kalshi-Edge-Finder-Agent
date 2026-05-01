from datetime import datetime, timedelta, timezone

from src.schemas.market import Market
from src.schemas.settings import Settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FilterService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def filter_markets(self, markets: list[Market]) -> list[Market]:
        filtered = [m for m in markets if self._passes_filters(m)]

        # Sort by 24h volume (descending). Highest-liquidity markets first
        # so we research the markets where price is most informative and
        # we can actually fill an order without moving the book.
        filtered.sort(
            key=lambda m: (m.volume_24h, m.volume),
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

        time_to_close = market.close_time - datetime.now(timezone.utc)
        if time_to_close.total_seconds() < 0:
            return False
        if time_to_close > timedelta(days=self.settings.max_days_to_close):
            return False

        if market.volume < self.settings.min_volume:
            return False

        return True
