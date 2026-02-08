from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.kalshi import KalshiClient
from src.db.session import get_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


def get_kalshi_client() -> KalshiClient:
    return KalshiClient()
