from fastapi import APIRouter, Depends, HTTPException, Query

from src.clients.kalshi import KalshiClient
from src.dependencies import get_kalshi_client
from src.schemas.market import Market, MarketDetailResponse, MarketListResponse
from src.services.scanner import ScannerService

router = APIRouter()


@router.get("", response_model=MarketListResponse)
async def list_markets(
    category: str | None = Query(None),
    min_multiplier: float = Query(2.0),
    max_days_to_close: int = Query(7),
    status: str = Query("open"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    kalshi: KalshiClient = Depends(get_kalshi_client),
) -> MarketListResponse:
    try:
        scanner = ScannerService(kalshi)
        markets: list[Market] = []

        async for market in scanner.scan_all_markets():
            markets.append(market)

        if category:
            markets = [m for m in markets if m.category == category]

        markets = [
            m
            for m in markets
            if max(m.yes_multiplier, m.no_multiplier) >= min_multiplier
        ]

        total = len(markets)
        markets = markets[offset : offset + limit]

        return MarketListResponse(markets=markets, total=total)
    finally:
        await kalshi.close()


@router.get("/{ticker}", response_model=MarketDetailResponse)
async def get_market(
    ticker: str,
    kalshi: KalshiClient = Depends(get_kalshi_client),
) -> MarketDetailResponse:
    try:
        data = await kalshi.get_market(ticker)
        market_data = data.get("market", data)
        scanner = ScannerService(kalshi)
        market = scanner._parse_market(market_data)
        return MarketDetailResponse(market=market)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Market not found: {e}") from e
    finally:
        await kalshi.close()
