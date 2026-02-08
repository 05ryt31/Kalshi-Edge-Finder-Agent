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

        result = await self.llm.estimate_probability(
            market_title=market.title,
            market_description=market.subtitle or "",
            research_data=research_data,
            resolution_criteria=f"Market closes at {market.close_time}",
            historical_context=historical_context,
        )

        yes_prob = float(result["yes_probability"])
        return {
            "yes_probability": yes_prob,
            "no_probability": 1 - yes_prob,
            "confidence": float(result["confidence"]),
            "reasoning": result["reasoning"],
        }
