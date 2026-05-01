import json
from abc import ABC, abstractmethod

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient(ABC):
    @abstractmethod
    async def estimate_probability(
        self,
        market_title: str,
        market_description: str,
        research_data: dict,
        resolution_criteria: str,
        historical_context: str = "",
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

## Response Format
Respond with ONLY a JSON object in this format:
{{
    "yes_probability": 0.XX,
    "confidence": 0.XX,
    "reasoning": "Brief explanation of your estimate"
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
    ) -> dict:
        prompt = ESTIMATION_PROMPT.format(
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
        return json.loads(response.content[0].text)


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
    ) -> dict:
        prompt = ESTIMATION_PROMPT.format(
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


def get_llm_client() -> LLMClient:
    if settings.LLM_PROVIDER == "anthropic":
        return ClaudeClient()
    if settings.LLM_PROVIDER == "openai":
        return OpenAIClient()
    raise ValueError(f"Unknown LLM provider: {settings.LLM_PROVIDER}")
