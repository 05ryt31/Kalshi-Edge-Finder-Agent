from src.db.repositories.recommendation import RecommendationRepository
from src.models.recommendation import RecommendationModel
from src.utils.logger import get_logger

logger = get_logger(__name__)

MAX_REASONING_LENGTH = 200


class HistoricalContextService:
    def __init__(self, recommendation_repo: RecommendationRepository) -> None:
        self.repo = recommendation_repo

    async def get_context_for_category(
        self,
        category: str,
        *,
        limit: int = 5,
        exclude_scan_id: str | None = None,
    ) -> str:
        past_recs = await self.repo.list_by_category(
            category,
            limit=limit,
            exclude_scan_id=exclude_scan_id,
        )

        if not past_recs:
            return "No prior analyses available for this category."

        entries = [self._format_entry(rec) for rec in past_recs]

        logger.info("historical_context_loaded", category=category, entries=len(entries))

        return (
            f'The following are past analyses from the "{category}" category. '
            "Use these for calibration only - each market is unique.\n\n"
            + "\n\n".join(entries)
        )

    def _format_entry(self, rec: RecommendationModel) -> str:
        research_summary = self._extract_research_summary(rec.research_data)
        reasoning = self._truncate(rec.reasoning or "", MAX_REASONING_LENGTH)
        created = rec.created_at.strftime("%Y-%m-%d %H:%M") if rec.created_at else "unknown"

        return (
            f"### Past Analysis: {rec.market_title} ({created})\n"
            f"- Ticker: {rec.market_ticker}\n"
            f"- Side: {rec.side} | Market Price: {rec.market_price}c "
            f"| Estimated Prob: {rec.estimated_probability:.0%}\n"
            f"- Edge: {rec.edge:.1%} | Confidence: {rec.confidence:.0%} "
            f"| Strength: {rec.strength}\n"
            f"- Research Summary: {research_summary}\n"
            f"- Reasoning: {reasoning}"
        )

    def _extract_research_summary(self, research_data: dict | None) -> str:
        if not research_data:
            return "N/A"
        return research_data.get("summary", "N/A")

    def _truncate(self, text: str, max_length: int) -> str:
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."
