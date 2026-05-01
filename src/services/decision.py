import uuid
from datetime import datetime, timezone
from typing import Literal

from src.schemas.market import Market
from src.schemas.recommendation import Recommendation
from src.schemas.settings import Settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Kalshi trading fee: round(0.07 * contracts * price * (1 - price)) per fill.
# Per-contract effective rate = 0.07 * p * (1 - p), expressed in dollars
# (since price is in [0,1] and a contract pays $1).
KALSHI_FEE_RATE = 0.07


def kalshi_fee_per_contract(price: float) -> float:
    """Kalshi fee per contract, in dollars. price is yes_ask/100 in [0,1]."""
    p = max(0.0, min(1.0, price))
    return KALSHI_FEE_RATE * p * (1 - p)


class DecisionEngine:
    # Climate-focused thresholds: with physics/stats-based estimation we expect
    # smaller real edges. Trade looser edge bars for stricter confidence bars,
    # so only well-grounded calls pass through.
    STRENGTH_THRESHOLDS: dict[str, dict[str, float]] = {
        "strong": {"edge": 0.05, "confidence": 0.85, "probability": 0.55},
        "medium": {"edge": 0.03, "confidence": 0.75, "probability": 0.50},
        "weak":   {"edge": 0.02, "confidence": 0.70, "probability": 0.45},
    }

    # Fractional Kelly multiplier — 1/4 Kelly to absorb estimation error.
    KELLY_FRACTION = 0.25

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate(
        self,
        market: Market,
        estimate: dict,
        research_data: dict,
        scan_id: str | None = None,
    ) -> Recommendation | None:
        if self._should_block_extreme_price(market, research_data):
            logger.info(
                "extreme_price_blocked",
                ticker=market.ticker,
                yes_ask=market.yes_ask,
            )
            return None

        yes_implied = market.yes_ask / 100
        no_implied = market.no_ask / 100

        # Fees reduce realized edge — one fee paid on entry per contract.
        # We approximate exit fee as 0 (hold-to-resolution); paper trading
        # results will calibrate this assumption.
        yes_fee = kalshi_fee_per_contract(yes_implied)
        no_fee = kalshi_fee_per_contract(no_implied)

        yes_edge = estimate["yes_probability"] - yes_implied - yes_fee
        no_edge = estimate["no_probability"] - no_implied - no_fee

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
            estimated_prob=estimated_prob,
            market_price=market_price,
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
        estimated_prob: float,
        market_price: float,
    ) -> float:
        """Fractional Kelly sizing.

        For a binary contract priced at p (in cents), a YES fill at price p
        cents costs $p/100 per contract and pays $1 if YES resolves.
        Net odds b = (1 - p) / p where p is in [0, 1].
        Full Kelly fraction f* = (prob * (1 + b) - 1) / b
                             = (prob / p) - 1   ... after simplification.
        We apply KELLY_FRACTION (1/4) for safety against estimation error,
        then cap by settings.max_bet_amount.
        """
        price = max(market_price / 100.0, 0.01)
        # Edge is already net of fees; require it positive.
        if edge <= 0 or estimated_prob <= price:
            return 0.0

        # Net odds for a YES-style contract (works for either side after the
        # caller has flipped probability/price into the chosen side's frame).
        b = (1 - price) / price
        kelly = (estimated_prob * (1 + b) - 1) / b
        if kelly <= 0:
            return 0.0

        # Confidence shrinks Kelly further — low confidence → smaller bet.
        confidence_factor = max(0.0, min(1.0, confidence))
        fraction = kelly * self.KELLY_FRACTION * confidence_factor

        # Cap at configured max bet (acts as proxy for bankroll * max position).
        bankroll_proxy = self.settings.max_bet_amount
        amount = bankroll_proxy * fraction

        # Hard cap and round; minimum $1 if any positive size to avoid noise.
        amount = min(amount, bankroll_proxy)
        if amount < 1.0:
            return 0.0
        return round(amount, 2)

    def _should_block_extreme_price(self, market: Market, research_data: dict) -> bool:
        # Universal: block past events with extreme prices (any category)
        if market.is_past_event and market.is_extreme_price:
            return True

        # Climate-specific day-of logic requires climate_info
        if market.climate_info is None:
            return False

        if not market.is_day_of_event:
            return False
        if not market.is_extreme_price:
            return False

        collected = research_data.get("collected_data", {})
        running_high = collected.get("running_daily_high_f")
        running_low = collected.get("running_daily_low_f")

        # No NWS data → block (refuse to bet blind on extreme-priced day-of)
        if running_high is None and running_low is None:
            return True

        # Check if NWS data explicitly contradicts the market price
        threshold = market.climate_info.threshold
        market_type = market.climate_info.market_type

        if market_type == "high_temp" and running_high is not None:
            if market.yes_ask >= 95 and running_high < threshold - 5:
                # Market says 95c YES but running high is far below threshold → allow bet
                return False
            if market.yes_ask <= 5 and running_high > threshold + 2:
                # Market says 5c YES but running high already exceeds threshold → allow bet
                return False

        if market_type == "low_temp" and running_low is not None:
            if market.yes_ask >= 95 and running_low > threshold + 5:
                return False
            if market.yes_ask <= 5 and running_low < threshold - 2:
                return False

        # Default: block (assume market resolved correctly at extreme prices)
        return True
