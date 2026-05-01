import json
import re
from abc import ABC, abstractmethod

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip markdown code fences
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1).strip())
    # Try to find first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise json.JSONDecodeError("No JSON found in response", text, 0)


def _select_prompt(use_climate: bool) -> str:
    return CLIMATE_ESTIMATION_PROMPT if use_climate else ESTIMATION_PROMPT


class LLMClient(ABC):
    @abstractmethod
    async def estimate_probability(
        self,
        market_title: str,
        market_description: str,
        research_data: dict,
        resolution_criteria: str,
        historical_context: str = "",
        *,
        use_climate_prompt: bool = False,
    ) -> dict:
        pass


ESTIMATION_PROMPT = """You are a prediction market analyst. Estimate the probability that the following market resolves YES.

## Market
Title: {title}
Description: {description}
Resolution Criteria: {resolution_criteria}

## Collected Data
{research_data}

## Historical Analysis (Same Category)
{historical_context}

## Key Rules
- NEVER use a previous prediction as evidence for a current estimate.
  Each estimate must be derived independently from current data.

## Response Format
Respond with ONLY a JSON object in this format:
{{
    "yes_probability": 0.XX,
    "confidence": 0.XX,
    "reasoning": "Brief explanation of your estimate"
}}

Output ONLY the JSON, no other text."""


CLIMATE_ESTIMATION_PROMPT = """You are a prediction market analyst specializing in climate/weather markets.
Estimate the probability that the following market resolves YES.

## Market
Title: {title}
Description: {description}

## Official Resolution Criteria
{resolution_criteria}

## NWS Station Data
{research_data}

## Key Rules
- For DAY-OF markets: weight ASOS observations and CLI reports HEAVILY over forecasts.
  The running daily high/low from ASOS is near-authoritative if close to market close.
- NWS calendar-day highs run 00:00-23:59 LST. Cold fronts can push the daily high to midnight.
- For future events: NWS observations provide current baseline; forecasts fill the gap.
- If running_daily_high_f already exceeds the threshold and market is day-of, probability is near 1.0.
- If running_daily_high_f is far below threshold late in the day, probability drops sharply.
- For CONCLUDED events (event_concluded: true):
  ONLY use official CLI report data. Do NOT reference forecasts or previous analyses.
  If official_data_missing is true, respond with confidence: 0.

## Historical Analysis (Same Category)
{historical_context}

## Response Format
Respond with ONLY a JSON object in this format:
{{
    "yes_probability": 0.XX,
    "confidence": 0.XX,
    "reasoning": "Brief explanation referencing specific NWS data points"
}}

Output ONLY the JSON, no other text."""


class ClaudeClient(LLMClient):
    def __init__(self) -> None:
        from anthropic import AsyncAnthropic

        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.LLM_MODEL or "claude-sonnet-4-20250514"

    async def estimate_probability(
        self,
        market_title: str,
        market_description: str,
        research_data: dict,
        resolution_criteria: str,
        historical_context: str = "",
        *,
        use_climate_prompt: bool = False,
    ) -> dict:
        template = _select_prompt(use_climate_prompt)
        prompt = template.format(
            title=market_title,
            description=market_description,
            resolution_criteria=resolution_criteria,
            research_data=json.dumps(research_data, indent=2),
            historical_context=historical_context or "No prior analyses available.",
        )

        logger.info("llm_estimate", model=self.model, market=market_title)
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return _extract_json(response.content[0].text)


class OpenAIClient(LLMClient):
    def __init__(self) -> None:
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.LLM_MODEL or "gpt-4o"

    async def estimate_probability(
        self,
        market_title: str,
        market_description: str,
        research_data: dict,
        resolution_criteria: str,
        historical_context: str = "",
        *,
        use_climate_prompt: bool = False,
    ) -> dict:
        template = _select_prompt(use_climate_prompt)
        prompt = template.format(
            title=market_title,
            description=market_description,
            resolution_criteria=resolution_criteria,
            research_data=json.dumps(research_data, indent=2),
            historical_context=historical_context or "No prior analyses available.",
        )

        logger.info("llm_estimate", model=self.model, market=market_title)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)


class GeminiClient(LLMClient):
    def __init__(self) -> None:
        from google import genai

        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.LLM_MODEL or "gemini-2.5-flash"

    async def estimate_probability(
        self,
        market_title: str,
        market_description: str,
        research_data: dict,
        resolution_criteria: str,
        historical_context: str = "",
        *,
        use_climate_prompt: bool = False,
    ) -> dict:
        template = _select_prompt(use_climate_prompt)
        prompt = template.format(
            title=market_title,
            description=market_description,
            resolution_criteria=resolution_criteria,
            research_data=json.dumps(research_data, indent=2),
            historical_context=historical_context or "No prior analyses available.",
        )

        logger.info("llm_estimate", model=self.model, market=market_title)
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        return _extract_json(response.text)


def get_llm_client() -> LLMClient:
    if settings.LLM_PROVIDER == "anthropic":
        return ClaudeClient()
    if settings.LLM_PROVIDER == "openai":
        return OpenAIClient()
    if settings.LLM_PROVIDER == "gemini":
        return GeminiClient()
    raise ValueError(f"Unknown LLM provider: {settings.LLM_PROVIDER}")
