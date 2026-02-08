import uuid
from datetime import datetime, timezone
from typing import Literal

from src.schemas.market import Market
from src.schemas.recommendation import Recommendation
from src.schemas.settings import Settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DecisionEngine:
    STRENGTH_THRESHOLDS: dict[str, dict[str, float]] = {
        "strong": {"edge": 0.30, "confidence": 0.80, "probability": 0.60},
        "medium": {"edge": 0.20, "confidence": 0.60, "probability": 0.50},
        "weak": {"edge": 0.15, "confidence": 0.50, "probability": 0.40},
    }

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate(
        self,
        market: Market,
        estimate: dict,
        research_data: dict,
        scan_id: str | None = None,
    ) -> Recommendation | None:
        yes_implied = market.yes_ask / 100
        no_implied = market.no_ask / 100

        yes_edge = estimate["yes_probability"] - yes_implied
        no_edge = estimate["no_probability"] - no_implied

        if yes_edge > no_edge:
            side: Literal["yes", "no"] = "yes"
            edge = yes_edge
            market_price = market.yes_ask
            estimated_prob = estimate["yes_probability"]
        else:
            side = "no"
            edge = no_edge
            market_price = market.no_ask
            estimated_prob = estimate["no_probability"]

        strength = self._determine_strength(
            edge=edge,
            confidence=estimate["confidence"],
            probability=estimated_prob,
        )

        if strength is None:
            logger.debug(
                "no_recommendation",
                ticker=market.ticker,
                edge=edge,
                confidence=estimate["confidence"],
            )
            return None

        suggested_amount = self._calculate_position_size(
            edge=edge,
            confidence=estimate["confidence"],
            strength=strength,
        )

        logger.info(
            "recommendation_generated",
            ticker=market.ticker,
            side=side,
            strength=strength,
            edge=f"{edge:.1%}",
        )

        return Recommendation(
            id=str(uuid.uuid4()),
            scan_id=scan_id,
            market_ticker=market.ticker,
            market_title=market.title,
            category=market.category,
            side=side,
            market_price=market_price,
            estimated_probability=estimated_prob,
            confidence=estimate["confidence"],
            edge=edge,
            strength=strength,
            suggested_amount=suggested_amount,
            status="pending",
            created_at=datetime.now(timezone.utc),
            expires_at=market.close_time,
        )

    def _determine_strength(
        self,
        edge: float,
        confidence: float,
        probability: float,
    ) -> Literal["strong", "medium", "weak"] | None:
        for strength in ("strong", "medium", "weak"):
            thresholds = self.STRENGTH_THRESHOLDS[strength]
            if (
                edge >= thresholds["edge"]
                and confidence >= thresholds["confidence"]
                and probability >= thresholds["probability"]
            ):
                return strength  # type: ignore[return-value]
        return None

    def _calculate_position_size(
        self,
        edge: float,
        confidence: float,
        strength: str,
    ) -> float:
        base_multipliers = {
            "strong": (0.80, 1.00),
            "medium": (0.40, 0.60),
            "weak": (0.10, 0.30),
        }

        min_mult, max_mult = base_multipliers[strength]
        score = (edge + confidence) / 2
        multiplier = min_mult + (max_mult - min_mult) * min(score, 1.0)
        amount = self.settings.max_bet_amount * multiplier

        return max(5.0, round(amount, 2))
