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
    has_open_orders: bool = False
    open_order_count: int = 0
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
    btc_open_orders: list[dict[str, Any]] = []


class TraderClosedTradeResponse(BaseModel):
    """Closed-trade response row."""

    trade_id: str
    direction: str
    opened_at: datetime
    closed_at: datetime
    entry_price: float
    close_reference_price: float
    max_abs_size: float
    final_abs_size: float
    last_unrealized_pnl: float
    close_reason: str


class TraderClosedTradesListResponse(BaseModel):
    """Closed-trade list response."""

    address: str
    symbol: str
    closed_trades: list[TraderClosedTradeResponse] = []
    count: int = 0


# ============== Routes ==============


@router.get("", response_model=TraderListResponse)
async def list_traders(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
    limit: int = Query(default=50, ge=1, le=500),
    min_score: float = Query(default=0, ge=0),
    tag: str | None = Query(default=None),
    has_positions: bool | None = Query(default=None, description="Filter by position status"),
    has_open_orders: bool | None = Query(default=None, description="Filter by open-order availability"),
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
        has_open_orders: Filter by whether trader has open orders
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

        addresses = [str(t.get("eth", t.get("address", ""))).lower() for t in traders]
        states_by_address = await repository.get_trader_current_states(
            addresses=addresses,
            symbol=lifecycle._settings.hyperliquid.symbol,
        )

        # Get position state for each trader
        trader_responses = []
        total_with_positions = 0
        total_flat = 0
        total_unknown = 0

        for t in traders:
            address = str(t.get("eth", t.get("address", ""))).lower()
            state = states_by_address.get(address)
            if not isinstance(state, dict):
                state = None

            has_pos = False
            has_orders = False
            order_count = 0
            pos_status = "unknown"
            last_update = None

            if state:
                positions = state.get("positions", [])
                open_orders = state.get("open_orders", [])
                if not isinstance(positions, list):
                    positions = []
                if not isinstance(open_orders, list):
                    open_orders = []
                last_update = state.get("updated_at")
                has_pos = len(positions) > 0
                has_orders = len(open_orders) > 0
                order_count = len(open_orders)

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
            if has_open_orders is not None and has_orders != has_open_orders:
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
                    has_open_orders=has_orders,
                    open_order_count=order_count,
                    position_status=pos_status,
                    last_position_update=last_update,
                )
            )

        filtered_query_applied = any(
            value is not None
            for value in (has_positions, has_open_orders, position_status, updated_within_hours)
        )
        response_total = len(trader_responses) if filtered_query_applied else total

        return {
            "traders": trader_responses,
            "total": response_total,
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
        if not isinstance(state, dict):
            state = None

        positions = []
        has_positions = False
        position_status = "unknown"
        btc_position = None
        btc_open_orders: list[dict[str, Any]] = []
        last_updated = trader.get("updated_at", trader.get("updatedAt"))

        if state:
            last_updated = state.get("updated_at") or last_updated
            state_positions = state.get("positions", [])
            if not isinstance(state_positions, list):
                state_positions = []
            for pos in state_positions:
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
            state_open_orders = state.get("open_orders", [])
            if not isinstance(state_open_orders, list):
                state_open_orders = []
            btc_open_orders = [order for order in state_open_orders if isinstance(order, dict)]

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
            btc_open_orders=btc_open_orders,
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


@router.get("/{address}/orders")
async def get_trader_orders(
    address: str,
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, Any]:
    """Get trader current active open orders for configured symbol."""
    validated_address = validate_eth_address(address)

    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    try:
        state = await repository.get_trader_current_state(validated_address)
        if not isinstance(state, dict):
            state = None

        open_orders = []
        last_updated = None
        if state:
            state_open_orders = state.get("open_orders", [])
            if isinstance(state_open_orders, list):
                open_orders = [order for order in state_open_orders if isinstance(order, dict)]
            last_updated = state.get("updated_at")

        return {
            "address": validated_address,
            "symbol": lifecycle._settings.hyperliquid.symbol,
            "open_orders": open_orders,
            "count": len(open_orders),
            "last_updated": last_updated,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{address}/closed-trades", response_model=TraderClosedTradesListResponse)
async def get_trader_closed_trades(
    address: str,
    lifecycle: LifecycleManager = Depends(get_lifecycle),
    hours: int = Query(default=168, ge=1, le=2160),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    """Get closed BTC trades for a tracked trader."""
    validated_address = validate_eth_address(address)

    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    try:
        trader = await repository.get_trader_by_address(validated_address)
        if not trader:
            raise HTTPException(status_code=404, detail="Trader not found")

        start_time = datetime.now(UTC) - timedelta(hours=hours)
        trades = await repository.get_trader_closed_trades(
            address=validated_address,
            start_time=start_time,
            limit=limit,
        )

        return {
            "address": validated_address,
            "symbol": lifecycle._settings.hyperliquid.symbol,
            "closed_trades": [
                TraderClosedTradeResponse(
                    trade_id=str(trade.get("trade_id", "")),
                    direction=str(trade.get("dir", "")),
                    opened_at=trade.get("opened_at"),
                    closed_at=trade.get("closed_at"),
                    entry_price=float(trade.get("entry_price", 0) or 0),
                    close_reference_price=float(trade.get("close_reference_price", 0) or 0),
                    max_abs_size=float(trade.get("max_abs_size", 0) or 0),
                    final_abs_size=float(trade.get("final_abs_size", 0) or 0),
                    last_unrealized_pnl=float(trade.get("last_unrealized_pnl", 0) or 0),
                    close_reason=str(trade.get("close_reason", "")),
                )
                for trade in trades
            ],
            "count": len(trades),
        }
    except HTTPException:
        raise
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
