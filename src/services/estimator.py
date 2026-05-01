from src.clients.llm import LLMClient, get_llm_client
from src.schemas.market import Market
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ProbabilityEstimator:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or get_llm_client()

    async def estimate(
        self, market: Market, research_data: dict, *, historical_context: str = ""
    ) -> dict:
        logger.info("estimating_probability", ticker=market.ticker)

        # Safety net: concluded event with no official data → confidence 0
        collected = research_data.get("collected_data", {})
        if collected.get("event_concluded") and collected.get("official_data_missing"):
            logger.info("concluded_no_data", ticker=market.ticker)
            return {
                "yes_probability": 0.5,
                "no_probability": 0.5,
                "confidence": 0.0,
                "reasoning": "Concluded event with no official CLI data available.",
            }

        resolution_criteria = self._build_resolution_criteria(market, research_data)

        use_climate = market.climate_info is not None

        result = await self.llm.estimate_probability(
            market_title=market.title,
            market_description=market.subtitle or "",
            research_data=research_data,
            resolution_criteria=resolution_criteria,
            historical_context=historical_context,
            use_climate_prompt=use_climate,
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
