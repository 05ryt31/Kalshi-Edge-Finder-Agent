from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    DATABASE_URL: str = "sqlite+aiosqlite:///./data/kalshi_edge.db"

    KALSHI_API_KEY: str = ""
    KALSHI_PRIVATE_KEY: str = ""
    KALSHI_USE_DEMO: bool = True

    LLM_PROVIDER: Literal["anthropic", "openai", "gemini"] = "anthropic"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    LLM_MODEL: str = ""

    OPENWEATHER_API_KEY: str = ""

    MIN_MULTIPLIER: float = 1.5
    MAX_DAYS_TO_CLOSE: int = 7
    MIN_VOLUME: int = 100
    MAX_BET_AMOUNT: float = 50.0
    SCAN_INTERVAL_HOURS: int = 1
    AUTO_EXECUTE_STRENGTH: Literal["strong", "medium", "weak"] = "strong"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
