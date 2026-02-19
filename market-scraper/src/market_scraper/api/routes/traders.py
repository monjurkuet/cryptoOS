# src/market_scraper/api/routes/traders.py

"""Trader API routes."""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from market_scraper.api.dependencies import get_lifecycle
from market_scraper.orchestration.lifecycle import LifecycleManager

router = APIRouter()


class TraderResponse(BaseModel):
    """Trader response model."""

    address: str
    display_name: str | None = None
    score: float
    tags: list[str] = []
    account_value: float = 0
    active: bool = True


class TraderListResponse(BaseModel):
    """Trader list response."""

    traders: list[TraderResponse]
    total: int
    symbol: str


class TraderPositionResponse(BaseModel):
    """Trader position response."""

    address: str
    symbol: str
    size: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: float
    timestamp: datetime


class TraderDetailResponse(BaseModel):
    """Detailed trader response."""

    address: str
    display_name: str | None = None
    score: float
    tags: list[str] = []
    account_value: float = 0
    active: bool = True
    positions: list[dict[str, Any]] = []
    last_updated: datetime | None = None


@router.get("", response_model=TraderListResponse)
async def list_traders(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
    limit: int = Query(default=50, ge=1, le=500),
    min_score: float = Query(default=0, ge=0),
    tag: str | None = Query(default=None),
) -> dict[str, Any]:
    """List tracked traders.

    Args:
        lifecycle: Lifecycle manager
        limit: Maximum traders to return
        min_score: Minimum score filter
        tag: Filter by tag (e.g., "whale", "consistent")

    Returns:
        List of tracked traders
    """
    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    try:
        # Use repository methods instead of direct DB access
        traders = await repository.get_tracked_traders(
            min_score=min_score,
            tag=tag,
            active_only=True,
            limit=limit,
        )
        total = await repository.count_tracked_traders(
            min_score=min_score,
            tag=tag,
            active_only=True,
        )

        return {
            "traders": [
                TraderResponse(
                    address=t.get("eth", t.get("address", "")),
                    display_name=t.get("name", t.get("displayName")),
                    score=t.get("score", 0),
                    tags=t.get("tags", []),
                    account_value=t.get("acct_val", t.get("accountValue", 0)),
                    active=t.get("active", True),
                )
                for t in traders
            ],
            "total": total,
            "symbol": lifecycle._settings.hyperliquid.symbol,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{address}", response_model=TraderDetailResponse)
async def get_trader(
    address: str,
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, Any]:
    """Get detailed trader information.

    Args:
        address: Trader Ethereum address
        lifecycle: Lifecycle manager

    Returns:
        Detailed trader information
    """
    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    try:
        # Get trader info using repository method
        trader = await repository.get_trader_by_address(address)

        if not trader:
            raise HTTPException(status_code=404, detail="Trader not found")

        # Get current positions
        state = await repository.get_trader_current_state(address)

        positions = []
        if state:
            for pos in state.get("positions", []):
                p = pos.get("position", pos)
                positions.append({
                    "coin": p.get("coin"),
                    "size": float(p.get("szi", 0)),
                    "entry_price": float(p.get("entryPx", 0)),
                    "mark_price": float(p.get("markPx", 0)),
                    "unrealized_pnl": float(p.get("unrealizedPnl", 0)),
                    "leverage": float(p.get("leverage", {}).get("value", 1) if isinstance(p.get("leverage"), dict) else p.get("leverage", 1)),
                })

        return TraderDetailResponse(
            address=trader.get("eth", trader.get("address", address)),
            display_name=trader.get("name", trader.get("displayName")),
            score=trader.get("score", 0),
            tags=trader.get("tags", []),
            account_value=trader.get("acct_val", trader.get("accountValue", 0)),
            active=trader.get("active", True),
            positions=positions,
            last_updated=trader.get("updated_at", trader.get("updatedAt")),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{address}/positions")
async def get_trader_positions(
    address: str,
    lifecycle: LifecycleManager = Depends(get_lifecycle),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    """Get trader position history.

    Args:
        address: Trader Ethereum address
        lifecycle: Lifecycle manager
        hours: Hours of history to fetch
        limit: Maximum results

    Returns:
        Position history
    """
    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    try:
        start_time = datetime.utcnow() - timedelta(hours=hours)

        # Use repository method
        positions = await repository.get_trader_positions_history(
            address=address,
            start_time=start_time,
            limit=limit,
        )

        return {
            "address": address,
            "symbol": lifecycle._settings.hyperliquid.symbol,
            "positions": [
                {
                    "timestamp": p.get("t"),
                    "coin": p.get("coin"),
                    "size": p.get("sz"),
                    "entry_price": p.get("ep"),
                    "mark_price": p.get("mp"),
                    "unrealized_pnl": p.get("upnl"),
                    "leverage": p.get("lev"),
                }
                for p in positions
            ],
            "count": len(positions),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{address}/signals")
async def get_trader_signals(
    address: str,
    lifecycle: LifecycleManager = Depends(get_lifecycle),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Get trader's recent signals.

    Args:
        address: Trader Ethereum address
        lifecycle: Lifecycle manager
        hours: Hours of history
        limit: Maximum results

    Returns:
        Trader signals
    """
    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    try:
        start_time = datetime.utcnow() - timedelta(hours=hours)

        # Use repository method
        signals = await repository.get_trader_signals(
            address=address,
            start_time=start_time,
            limit=limit,
        )

        return {
            "address": address,
            "signals": [
                {
                    "timestamp": s.get("t"),
                    "symbol": s.get("symbol"),
                    "action": s.get("action"),
                    "direction": s.get("dir"),
                    "size": s.get("sz"),
                    "confidence": s.get("conf"),
                }
                for s in signals
            ],
            "count": len(signals),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
