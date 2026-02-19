# src/market_scraper/api/routes/markets.py

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from market_scraper.api.dependencies import get_lifecycle
from market_scraper.orchestration.lifecycle import LifecycleManager

router = APIRouter()


class MarketListItem(BaseModel):
    """Market list item."""

    symbol: str
    status: str = "active"


class MarketDataResponse(BaseModel):
    """Market data response."""

    symbol: str
    latest_candle: dict[str, Any] | None = None


class MarketHistoryResponse(BaseModel):
    """Market history response."""

    symbol: str
    timeframe: str
    candles: list[dict[str, Any]]
    count: int


@router.get("", response_model=list[MarketListItem])
async def list_markets(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> list[dict[str, Any]]:
    """List available markets.

    Returns a list of all available market symbols from all connectors.
    """
    markets = await lifecycle.get_markets()
    return markets


@router.get("/{symbol}", response_model=MarketDataResponse)
async def get_market(
    symbol: str,
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, Any]:
    """Get market data for a specific symbol.

    Returns the latest market data for the specified symbol.
    """
    data = await lifecycle.get_market_data(symbol)
    if not data:
        raise HTTPException(status_code=404, detail=f"Market {symbol} not found")
    return data


@router.get("/{symbol}/history", response_model=MarketHistoryResponse)
async def get_market_history(
    symbol: str,
    timeframe: str = Query("1h", description="Timeframe (1m, 5m, 15m, 1h, 4h, 1d)"),
    start_time: datetime | None = Query(None, description="Start time (inclusive)"),
    end_time: datetime | None = Query(None, description="End time (inclusive)"),
    limit: int = Query(100, ge=1, le=10000, description="Max results"),
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, Any]:
    """Get historical OHLCV candle data.

    Returns candlestick data for the specified symbol and timeframe.

    Candle fields:
    - t: Candle start timestamp
    - o: Open price
    - h: High price
    - l: Low price
    - c: Close price
    - v: Volume
    """
    candles = await lifecycle.get_market_history(
        symbol=symbol,
        timeframe=timeframe,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": candles,
        "count": len(candles),
    }
