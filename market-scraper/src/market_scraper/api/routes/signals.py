# src/market_scraper/api/routes/signals.py

"""Signal API routes."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from market_scraper.api.dependencies import get_lifecycle
from market_scraper.orchestration.lifecycle import LifecycleManager

router = APIRouter()


# ============== Input Validation ==============

OBJECT_ID_PATTERN = re.compile(r"^[a-fA-F0-9]{24}$")


def validate_object_id(object_id: str) -> str:
    """Validate MongoDB ObjectId format.

    Args:
        object_id: String to validate as ObjectId

    Returns:
        Validated ObjectId string

    Raises:
        HTTPException: If the ID format is invalid
    """
    if not OBJECT_ID_PATTERN.match(object_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid signal ID format: must be a 24-character hex string",
        )
    try:
        ObjectId(object_id)
        return object_id
    except InvalidId as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid signal ID: {str(e)}",
        ) from e


# ============== Response Models ==============


class SignalResponse(BaseModel):
    """Signal response model."""

    timestamp: datetime
    symbol: str
    recommendation: str
    confidence: float
    long_bias: float
    short_bias: float
    net_exposure: float
    traders_long: int
    traders_short: int
    traders_flat: int
    price: float


class SignalListResponse(BaseModel):
    """Signal list response."""

    signals: list[SignalResponse]
    total: int
    symbol: str


class AggregatedSignalResponse(BaseModel):
    """Current aggregated signal."""

    symbol: str
    recommendation: str
    confidence: float
    long_bias: float
    short_bias: float
    net_exposure: float
    traders_long: int
    traders_short: int
    traders_flat: int
    price: float
    timestamp: datetime | None = None


class SignalStatsResponse(BaseModel):
    """Signal statistics."""

    symbol: str
    period_hours: int
    total_signals: int
    buy_signals: int
    sell_signals: int
    neutral_signals: int
    avg_confidence: float
    current_bias: float


# ============== Routes ==============


@router.get("", response_model=SignalListResponse)
async def list_signals(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=500),
    recommendation: str | None = Query(default=None, pattern="^(BUY|SELL|NEUTRAL)$"),
) -> dict[str, Any]:
    """List historical signals.

    Args:
        lifecycle: Lifecycle manager
        hours: Hours of history
        limit: Maximum results
        recommendation: Filter by recommendation

    Returns:
        List of signals
    """
    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    try:
        symbol = lifecycle._settings.hyperliquid.symbol
        start_time = datetime.now(UTC) - timedelta(hours=hours)

        # Use repository method
        signals = await repository.get_signals(
            symbol=symbol,
            start_time=start_time,
            recommendation=recommendation,
            limit=limit,
        )

        # Count total (approximate since we filtered by recommendation)
        # For accurate count, we'd need a separate count method with the same filters
        total = len(signals)  # Simplified for now

        return {
            "signals": [
                SignalResponse(
                    timestamp=s.get("t"),
                    symbol=s.get("symbol"),
                    recommendation=s.get("rec"),
                    confidence=s.get("conf", 0),
                    long_bias=s.get("long_bias", 0),
                    short_bias=s.get("short_bias", 0),
                    net_exposure=s.get("net_exp", 0),
                    traders_long=s.get("t_long", 0),
                    traders_short=s.get("t_short", 0),
                    traders_flat=s.get("t_flat", 0),
                    price=s.get("price", 0),
                )
                for s in signals
            ],
            "total": total,
            "symbol": symbol,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/current", response_model=AggregatedSignalResponse)
async def get_current_signal(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, Any]:
    """Get current aggregated signal.

    Args:
        lifecycle: Lifecycle manager

    Returns:
        Current signal
    """
    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    try:
        symbol = lifecycle._settings.hyperliquid.symbol

        # Use repository method
        signal = await repository.get_current_signal(symbol)

        if signal:
            return AggregatedSignalResponse(
                symbol=signal.get("symbol"),
                recommendation=signal.get("rec", "NEUTRAL"),
                confidence=signal.get("conf", 0),
                long_bias=signal.get("long_bias", 0),
                short_bias=signal.get("short_bias", 0),
                net_exposure=signal.get("net_exp", 0),
                traders_long=signal.get("t_long", 0),
                traders_short=signal.get("t_short", 0),
                traders_flat=signal.get("t_flat", 0),
                price=signal.get("price", 0),
                timestamp=signal.get("t"),
            )

        # Return neutral signal if no data
        return AggregatedSignalResponse(
            symbol=symbol,
            recommendation="NEUTRAL",
            confidence=0,
            long_bias=0,
            short_bias=0,
            net_exposure=0,
            traders_long=0,
            traders_short=0,
            traders_flat=0,
            price=0,
            timestamp=None,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/stats", response_model=SignalStatsResponse)
async def get_signal_stats(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
    hours: int = Query(default=24, ge=1, le=168),
) -> dict[str, Any]:
    """Get signal statistics.

    Args:
        lifecycle: Lifecycle manager
        hours: Period for statistics

    Returns:
        Signal statistics
    """
    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    try:
        symbol = lifecycle._settings.hyperliquid.symbol
        start_time = datetime.now(UTC) - timedelta(hours=hours)

        # Use repository method
        stats = await repository.get_signal_stats(symbol, start_time)

        return {
            "symbol": symbol,
            "period_hours": hours,
            "total_signals": stats.get("total", 0),
            "buy_signals": stats.get("buy", 0),
            "sell_signals": stats.get("sell", 0),
            "neutral_signals": stats.get("neutral", 0),
            "avg_confidence": stats.get("avg_confidence", 0),
            "current_bias": stats.get("avg_long_bias", 0),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{signal_id}")
async def get_signal(
    signal_id: str,
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, Any]:
    """Get a specific signal by ID.

    Args:
        signal_id: Signal ID (24-character hex string)
        lifecycle: Lifecycle manager

    Returns:
        Signal details
    """
    # Validate signal_id format
    validate_object_id(signal_id)

    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    try:
        # Use repository method
        signal = await repository.get_signal_by_id(signal_id)

        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found")

        return {
            "id": signal.get("id", signal_id),
            "timestamp": signal.get("t"),
            "symbol": signal.get("symbol"),
            "recommendation": signal.get("rec"),
            "confidence": signal.get("conf"),
            "long_bias": signal.get("long_bias"),
            "short_bias": signal.get("short_bias"),
            "net_exposure": signal.get("net_exp"),
            "traders_long": signal.get("t_long"),
            "traders_short": signal.get("t_short"),
            "traders_flat": signal.get("t_flat"),
            "price": signal.get("price"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
