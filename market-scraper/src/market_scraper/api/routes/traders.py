# src/market_scraper/api/routes/traders.py

"""Trader API routes."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from market_scraper.api.dependencies import get_lifecycle
from market_scraper.orchestration.lifecycle import LifecycleManager

router = APIRouter()


# ============== Input Validation ==============

ETHEREUM_ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")


def validate_eth_address(address: str) -> str:
    """Validate Ethereum address format.

    Args:
        address: String to validate as Ethereum address

    Returns:
        Lowercase validated address

    Raises:
        HTTPException: If the address format is invalid
    """
    if not ETHEREUM_ADDRESS_PATTERN.match(address):
        raise HTTPException(
            status_code=400,
            detail="Invalid Ethereum address format: must be 0x followed by 40 hex characters",
        )
    return address.lower()


# ============== Response Models ==============


class TraderResponse(BaseModel):
    """Trader response model."""

    address: str
    display_name: str | None = None
    score: float
    tags: list[str] = []
    account_value: float = 0
    active: bool = True
    has_positions: bool = False
    position_status: str = "unknown"  # "flat", "long", "short", "unknown"
    last_position_update: datetime | None = None


class TraderListResponse(BaseModel):
    """Trader list response."""

    traders: list[TraderResponse]
    total: int
    symbol: str
    # Summary statistics
    total_with_positions: int = 0
    total_flat: int = 0
    total_unknown: int = 0


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
    # Position status fields
    position_status: str = "unknown"  # "flat", "long", "short", "mixed", "unknown"
    has_positions: bool = False
    btc_position: dict[str, Any] | None = None  # BTC-specific position if available


# ============== Routes ==============


@router.get("", response_model=TraderListResponse)
async def list_traders(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
    limit: int = Query(default=50, ge=1, le=500),
    min_score: float = Query(default=0, ge=0),
    tag: str | None = Query(default=None),
    has_positions: bool | None = Query(default=None, description="Filter by position status"),
    position_status: str | None = Query(default=None, description="Filter by: flat, long, short, unknown"),
    updated_within_hours: int | None = Query(default=None, description="Only traders updated within N hours"),
) -> dict[str, Any]:
    """List tracked traders.

    Args:
        lifecycle: Lifecycle manager
        limit: Maximum traders to return
        min_score: Minimum score filter
        tag: Filter by tag (e.g., "whale", "consistent")
        has_positions: Filter by whether trader has positions
        position_status: Filter by position status (flat, long, short, unknown)
        updated_within_hours: Only include traders updated within N hours

    Returns:
        List of tracked traders with position status information

    Note:
        Position data is only available when traders have open positions.
        Hyperliquid WebSocket only sends updates when positions exist.
        A "flat" status means the trader has no current positions on record.
        An "unknown" status means no position data has ever been received.
    """
    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    try:
        # Get traders from tracked_traders collection
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

        # Get position state for each trader
        trader_responses = []
        total_with_positions = 0
        total_flat = 0
        total_unknown = 0

        for t in traders:
            address = t.get("eth", t.get("address", "")).lower()

            # Get current position state
            state = await repository.get_trader_current_state(address)

            has_pos = False
            pos_status = "unknown"
            last_update = None

            if state:
                positions = state.get("positions", [])
                last_update = state.get("updated_at")
                has_pos = len(positions) > 0

                if has_pos:
                    total_with_positions += 1
                    # Determine position status based on BTC position
                    btc_pos = None
                    for pos in positions:
                        p = pos.get("position", pos)
                        if p.get("coin") == "BTC":
                            btc_pos = p
                            break

                    if btc_pos:
                        size = float(btc_pos.get("szi", 0))
                        if size > 0:
                            pos_status = "long"
                        elif size < 0:
                            pos_status = "short"
                        else:
                            pos_status = "flat"
                    else:
                        pos_status = "flat"  # Has positions but no BTC
                else:
                    total_flat += 1
                    pos_status = "flat"
            else:
                total_unknown += 1
                pos_status = "unknown"

            # Apply filters
            if has_positions is not None and has_pos != has_positions:
                continue
            if position_status is not None and pos_status != position_status:
                continue
            if updated_within_hours is not None and last_update:
                from datetime import datetime, timedelta, UTC
                cutoff = datetime.now(UTC) - timedelta(hours=updated_within_hours)
                if last_update < cutoff:
                    continue

            trader_responses.append(
                TraderResponse(
                    address=address,
                    display_name=t.get("name", t.get("displayName")),
                    score=t.get("score", 0),
                    tags=t.get("tags", []),
                    account_value=t.get("acct_val", t.get("accountValue", 0)),
                    active=t.get("active", True),
                    has_positions=has_pos,
                    position_status=pos_status,
                    last_position_update=last_update,
                )
            )

        return {
            "traders": trader_responses,
            "total": total,
            "symbol": lifecycle._settings.hyperliquid.symbol,
            "total_with_positions": total_with_positions,
            "total_flat": total_flat,
            "total_unknown": total_unknown,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{address}", response_model=TraderDetailResponse)
async def get_trader(
    address: str,
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, Any]:
    """Get detailed trader information.

    Args:
        address: Trader Ethereum address (0x + 40 hex characters)
        lifecycle: Lifecycle manager

    Returns:
        Detailed trader information including position status

    Note:
        Position data is only available when traders have open positions.
        Hyperliquid WebSocket only sends updates when positions exist.
        A "flat" status means the trader has no current positions on record.
        An "unknown" status means no position data has ever been received.
    """
    # Validate address format
    validated_address = validate_eth_address(address)

    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    try:
        # Get trader info using repository method
        trader = await repository.get_trader_by_address(validated_address)

        if not trader:
            raise HTTPException(status_code=404, detail="Trader not found")

        # Get current positions
        state = await repository.get_trader_current_state(validated_address)

        positions = []
        has_positions = False
        position_status = "unknown"
        btc_position = None
        last_updated = trader.get("updated_at", trader.get("updatedAt"))

        if state:
            last_updated = state.get("updated_at") or last_updated
            for pos in state.get("positions", []):
                p = pos.get("position", pos)
                pos_data = {
                    "coin": p.get("coin"),
                    "size": float(p.get("szi", 0)),
                    "entry_price": float(p.get("entryPx", 0)),
                    "mark_price": float(p.get("markPx", 0)),
                    "unrealized_pnl": float(p.get("unrealizedPnl", 0)),
                    "leverage": float(
                        p.get("leverage", {}).get("value", 1)
                        if isinstance(p.get("leverage"), dict)
                        else p.get("leverage", 1)
                    ),
                }
                positions.append(pos_data)

                # Check for BTC position
                if p.get("coin") == "BTC":
                    btc_position = pos_data

            has_positions = len(positions) > 0

            # Determine position status
            if has_positions:
                if btc_position:
                    size = btc_position.get("size", 0)
                    if size > 0:
                        position_status = "long"
                    elif size < 0:
                        position_status = "short"
                    else:
                        position_status = "flat"
                else:
                    position_status = "flat"  # Has positions but no BTC
            else:
                position_status = "flat"
        else:
            position_status = "unknown"
            has_positions = False

        return TraderDetailResponse(
            address=trader.get("eth", trader.get("address", validated_address)),
            display_name=trader.get("name", trader.get("displayName")),
            score=trader.get("score", 0),
            tags=trader.get("tags", []),
            account_value=trader.get("acct_val", trader.get("accountValue", 0)),
            active=trader.get("active", True),
            positions=positions,
            last_updated=last_updated,
            position_status=position_status,
            has_positions=has_positions,
            btc_position=btc_position,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{address}/positions")
async def get_trader_positions(
    address: str,
    lifecycle: LifecycleManager = Depends(get_lifecycle),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    """Get trader position history.

    Args:
        address: Trader Ethereum address (0x + 40 hex characters)
        lifecycle: Lifecycle manager
        hours: Hours of history to fetch
        limit: Maximum results

    Returns:
        Position history
    """
    # Validate address format
    validated_address = validate_eth_address(address)

    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    try:
        start_time = datetime.now(UTC) - timedelta(hours=hours)

        # Use repository method
        positions = await repository.get_trader_positions_history(
            address=validated_address,
            start_time=start_time,
            limit=limit,
        )

        return {
            "address": validated_address,
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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{address}/signals")
async def get_trader_signals(
    address: str,
    lifecycle: LifecycleManager = Depends(get_lifecycle),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Get trader's recent signals.

    Args:
        address: Trader Ethereum address (0x + 40 hex characters)
        lifecycle: Lifecycle manager
        hours: Hours of history
        limit: Maximum results

    Returns:
        Trader signals
    """
    # Validate address format
    validated_address = validate_eth_address(address)

    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    try:
        start_time = datetime.now(UTC) - timedelta(hours=hours)

        # Use repository method
        signals = await repository.get_trader_signals(
            address=validated_address,
            start_time=start_time,
            limit=limit,
        )

        return {
            "address": validated_address,
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
        raise HTTPException(status_code=500, detail=str(e)) from e
