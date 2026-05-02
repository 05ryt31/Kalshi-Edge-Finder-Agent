from src.clients.llm import LLMClient, get_llm_client
from src.schemas.market import Market
from src.services.climate_estimator import ClimateEstimator
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ProbabilityEstimator:
    """Routes probability estimation to the appropriate engine.

    Climate markets → ClimateEstimator (physics + statistics, no LLM).
    Other categories → LLM fallback. Note: filter rejects non-climate
    categories by default after the climate-focus pivot, so the LLM path
    is essentially dead code retained for hand-driven debugging only.
    """

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        climate_estimator: ClimateEstimator | None = None,
    ) -> None:
        self.llm = llm_client
        self.climate = climate_estimator or ClimateEstimator()

    async def estimate(
        self, market: Market, research_data: dict, *, historical_context: str = ""
    ) -> dict:
        logger.info("estimating_probability", ticker=market.ticker, category=market.category)

        # Route by category, not by climate_info presence: a market labeled
        # 'climate' but missing parsed climate_info should return uncertain
        # via ClimateEstimator (which short-circuits to confidence=0), not
        # silently fall through to the LLM and require an API key.
        if market.category == "climate":
            result = await self.climate.estimate(market, research_data)
            logger.info(
                "climate_estimate",
                ticker=market.ticker,
                yes_prob=f"{result['yes_probability']:.3f}",
                confidence=f"{result['confidence']:.2f}",
            )
            return result

        # Non-climate fallback (LLM). Lazy-init so climate-only setups
        # don't require an API key.
        return await self._estimate_with_llm(
            market, research_data, historical_context=historical_context
        )

    async def _estimate_with_llm(
        self, market: Market, research_data: dict, *, historical_context: str
    ) -> dict:
        # Safety net: concluded event with no official data → confidence 0
        collected = research_data.get("collected_data", {})
        if collected.get("event_concluded") and collected.get("official_data_missing"):
            logger.info("concluded_no_data", ticker=market.ticker)
            return {
                "yes_probability": 0.5,
                "no_probability": 0.5,
                "confidence": 0.0,
                "reasoning": "Concluded event with no official data available.",
            }

        if self.llm is None:
            self.llm = get_llm_client()

        resolution_criteria = self._build_resolution_criteria(market, research_data)

        result = await self.llm.estimate_probability(
            market_title=market.title,
            market_description=market.subtitle or "",
            research_data=research_data,
            resolution_criteria=resolution_criteria,
            historical_context=historical_context,
        )

        yes_prob = float(result["yes_probability"])
        return {
            "yes_probability": yes_prob,
            "no_probability": 1 - yes_prob,
            "confidence": float(result["confidence"]),
            "reasoning": result["reasoning"],
        }

    def _build_resolution_criteria(self, market: Market, research_data: dict) -> str:
        collected = research_data.get("collected_data", {})
        if "resolution_criteria" in collected:
            return collected["resolution_criteria"]
        return f"Market closes at {market.close_time}"
