# src/market_scraper/api/routes/traders.py

"""Trader API routes."""

import asyncio
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel

from market_scraper.api.dependencies import get_lifecycle
from market_scraper.orchestration.lifecycle import LifecycleManager

router = APIRouter()
_TRADERS_ROUTE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_TRADERS_CACHE_TTL_SECONDS = 30.0
_TRADERS_HARD_TIMEOUT_SECONDS = 4.0


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
    metrics: dict[str, Any] | None = None


class TraderListResponse(BaseModel):
    """Trader list response."""

    traders: list[TraderResponse]
    total: int
    symbol: str
    # Summary statistics
    total_with_positions: int = 0
    total_flat: int = 0
    total_unknown: int = 0
    matched_total: int | None = None
    returned_count: int = 0
    has_more: bool = False
    applied_filters: dict[str, Any] = {}


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


class TraderBatchRequest(BaseModel):
    """Batch trader request payload."""

    addresses: list[str]
    include_inactive: bool = False


class TraderBatchResponse(BaseModel):
    """Batch trader response payload."""

    traders: list[dict[str, Any]]
    requested: int
    found: int


# ============== Routes ==============


def _parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_position(position_like: Any) -> dict[str, Any]:
    position = position_like.get("position", position_like) if isinstance(position_like, dict) else {}
    size = _parse_float(position.get("szi", position.get("size", 0)), 0.0)
    entry_price = _parse_float(position.get("entryPx", position.get("entry_price", 0)), 0.0)
    mark_price = _parse_float(position.get("markPx", position.get("mark_price", 0)), 0.0)
    leverage_raw = position.get("leverage", 1)
    if isinstance(leverage_raw, dict):
        leverage = _parse_float(leverage_raw.get("value", 1), 1.0)
    else:
        leverage = _parse_float(leverage_raw, 1.0)

    liquidation_price_raw = (
        position.get("liquidationPx")
        if position.get("liquidationPx") is not None
        else position.get("liqPx")
    )
    if liquidation_price_raw is None:
        liquidation_price_raw = position.get("liq")
    liquidation_price = (
        _parse_float(liquidation_price_raw, 0.0)
        if liquidation_price_raw not in (None, "")
        else None
    )
    notional = abs(size) * (mark_price if mark_price > 0 else entry_price)
    direction = "long" if size > 0 else "short" if size < 0 else "flat"

    return {
        "coin": position.get("coin"),
        "size": size,
        "entry_price": entry_price,
        "mark_price": mark_price,
        "unrealized_pnl": _parse_float(position.get("unrealizedPnl", position.get("upnl", 0)), 0.0),
        "leverage": leverage,
        "liquidation_price": liquidation_price,
        "position_value": notional,
        "notional": notional,
        "direction": direction,
    }


def _extract_trader_state_summary(
    state: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, bool]:
    if not isinstance(state, dict):
        return [], [], "unknown", False

    raw_positions = state.get("positions", [])
    if not isinstance(raw_positions, list):
        raw_positions = []
    positions = [_normalize_position(pos) for pos in raw_positions]
    positions = [p for p in positions if abs(_parse_float(p.get("size"), 0.0)) > 0]

    open_orders = state.get("open_orders", [])
    if not isinstance(open_orders, list):
        open_orders = []
    normalized_orders = [order for order in open_orders if isinstance(order, dict)]

    position_status = "flat"
    has_positions = len(positions) > 0
    if has_positions:
        has_long = any(_parse_float(position.get("size"), 0.0) > 0 for position in positions)
        has_short = any(_parse_float(position.get("size"), 0.0) < 0 for position in positions)
        if has_long and has_short:
            position_status = "mixed"
        elif has_long:
            position_status = "long"
        elif has_short:
            position_status = "short"
        else:
            position_status = "flat"

    return positions, normalized_orders, position_status, has_positions


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
    address_contains: str | None = Query(default=None),
    display_name_contains: str | None = Query(default=None),
    max_score: float | None = Query(default=None, ge=0),
    account_value_min: float | None = Query(default=None, ge=0),
    account_value_max: float | None = Query(default=None, ge=0),
    tags_any: str | None = Query(default=None, description="Comma-separated tags"),
    tags_all: str | None = Query(default=None, description="Comma-separated tags"),
    tags_exclude: str | None = Query(default=None, description="Comma-separated tags"),
    roi_day_min: float | None = Query(default=None),
    roi_day_max: float | None = Query(default=None),
    roi_week_min: float | None = Query(default=None),
    roi_week_max: float | None = Query(default=None),
    roi_month_min: float | None = Query(default=None),
    roi_month_max: float | None = Query(default=None),
    roi_all_time_min: float | None = Query(default=None),
    roi_all_time_max: float | None = Query(default=None),
    volume_day_min: float | None = Query(default=None, ge=0),
    volume_day_max: float | None = Query(default=None, ge=0),
    volume_week_min: float | None = Query(default=None, ge=0),
    volume_week_max: float | None = Query(default=None, ge=0),
    volume_month_min: float | None = Query(default=None, ge=0),
    volume_month_max: float | None = Query(default=None, ge=0),
    profitable_windows: str | None = Query(default=None, description="Comma-separated: day,week,month,all_time"),
    sort_by: str = Query(default="score", description="score,account_value,last_position_update,address"),
    sort_dir: str = Query(default="desc", description="asc or desc"),
    offset: int = Query(default=0, ge=0),
    include_total_mode: str | None = Query(default=None, alias="include_total_mode"),
    include_metrics: bool = Query(default=False, description="Include ROI/volume/pnl metrics in trader rows"),
    include_total: bool = Query(
        default=False,
        description="When true, run an exact tracked-trader count (adds DB cost).",
    ),
    addresses: str | None = Query(
        default=None,
        description="Comma-separated exact addresses to include",
    ),
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

    request_cache_key = repr(
        (
            limit,
            min_score,
            tag,
            has_positions,
            has_open_orders,
            position_status,
            updated_within_hours,
            address_contains,
            display_name_contains,
            max_score,
            account_value_min,
            account_value_max,
            tags_any,
            tags_all,
            tags_exclude,
            roi_day_min,
            roi_day_max,
            roi_week_min,
            roi_week_max,
            roi_month_min,
            roi_month_max,
            roi_all_time_min,
            roi_all_time_max,
            volume_day_min,
            volume_day_max,
            volume_week_min,
            volume_week_max,
            volume_month_min,
            volume_month_max,
            profitable_windows,
            sort_by,
            sort_dir,
            offset,
            include_total_mode,
            include_metrics,
            include_total,
            addresses,
        )
    )
    now_ts = time.time()
    cached_entry = _TRADERS_ROUTE_CACHE.get(request_cache_key)
    if cached_entry and (now_ts - cached_entry[0]) <= _TRADERS_CACHE_TTL_SECONDS:
        return cached_entry[1]

    try:
        def parse_csv(value: str | None) -> list[str]:
            if not value:
                return []
            return [item.strip().lower().lstrip("+") for item in value.split(",") if item.strip()]

        def parse_addresses_csv(value: str | None) -> list[str]:
            if not value:
                return []
            parsed: list[str] = []
            for raw in value.split(","):
                candidate = raw.strip()
                if not candidate:
                    continue
                parsed.append(validate_eth_address(candidate))
            return parsed

        tags_any_list = parse_csv(tags_any)
        tags_all_list = parse_csv(tags_all)
        tags_exclude_list = parse_csv(tags_exclude)
        profitable_window_list = parse_csv(profitable_windows)
        selected_addresses = parse_addresses_csv(addresses)
        selected_address_set = set(selected_addresses)
        valid_profitable_windows = {"day", "week", "month", "all_time"}
        profitable_window_list = [w for w in profitable_window_list if w in valid_profitable_windows]

        include_exact_count = include_total
        if include_total_mode is not None:
            include_exact_count = include_total_mode.lower() == "exact"

        has_extended_filters = any(
            value is not None
            for value in (
                addresses,
                address_contains,
                display_name_contains,
                max_score,
                account_value_min,
                account_value_max,
                roi_day_min,
                roi_day_max,
                roi_week_min,
                roi_week_max,
                roi_month_min,
                roi_month_max,
                roi_all_time_min,
                roi_all_time_max,
                volume_day_min,
                volume_day_max,
                volume_week_min,
                volume_week_max,
                volume_month_min,
                volume_month_max,
            )
        ) or bool(tags_any_list or tags_all_list or tags_exclude_list or profitable_window_list)
        needs_performance_fields = include_metrics or any(
            value is not None
            for value in (
                roi_day_min,
                roi_day_max,
                roi_week_min,
                roi_week_max,
                roi_month_min,
                roi_month_max,
                roi_all_time_min,
                roi_all_time_max,
                volume_day_min,
                volume_day_max,
                volume_week_min,
                volume_week_max,
                volume_month_min,
                volume_month_max,
            )
        ) or bool(profitable_window_list)

        prefetch_limit = limit
        if has_extended_filters or any(
            value is not None for value in (has_positions, has_open_orders, position_status, updated_within_hours)
        ):
            # Keep the hot path bounded for low-resource VPS deployments.
            prefetch_limit = min(120, max(30, limit * 3))
        if selected_addresses:
            # Exact-address mode needs a wider prefetch window than score-ranked pages.
            prefetch_limit = max(prefetch_limit, min(5000, max(200, len(selected_addresses) * 4)))

        # Get traders from tracked_traders collection
        tracked_kwargs: dict[str, Any] = {
            "min_score": min_score,
            "tag": tag,
            "active_only": True,
            "limit": prefetch_limit,
        }
        if needs_performance_fields:
            tracked_kwargs["include_performances"] = True
        tracked_traders_call = repository.get_tracked_traders(**tracked_kwargs)

        traders = await asyncio.wait_for(
            tracked_traders_call,
            timeout=_TRADERS_HARD_TIMEOUT_SECONDS,
        )
        total = None
        if include_exact_count:
            total = await asyncio.wait_for(
                repository.count_tracked_traders(
                    min_score=min_score,
                    tag=tag,
                    active_only=True,
                    include_exact_count=True,
                ),
                timeout=_TRADERS_HARD_TIMEOUT_SECONDS,
            )

        trader_addresses = [str(t.get("eth", t.get("address", ""))).lower() for t in traders]
        current_states_call = repository.get_trader_current_states(
            addresses=trader_addresses,
            symbol=lifecycle._settings.hyperliquid.symbol,
        )

        states_by_address = await asyncio.wait_for(
            current_states_call,
            timeout=_TRADERS_HARD_TIMEOUT_SECONDS,
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
            display_name = t.get("name", t.get("displayName"))
            score_value = float(t.get("score", 0) or 0)
            account_value = float(t.get("acct_val", t.get("accountValue", 0)) or 0)
            normalized_tags = [str(item).lower() for item in (t.get("tags", []) or [])]
            metrics = None
            if needs_performance_fields:
                performances = t.get("performances", {})
                if not isinstance(performances, dict):
                    performances = {}
                day = performances.get("day", {}) if isinstance(performances.get("day", {}), dict) else {}
                week = performances.get("week", {}) if isinstance(performances.get("week", {}), dict) else {}
                month = performances.get("month", {}) if isinstance(performances.get("month", {}), dict) else {}
                all_time = performances.get("allTime", {}) if isinstance(performances.get("allTime", {}), dict) else {}
                metrics = {
                    "roi": {
                        "day": float(day.get("roi", 0) or 0),
                        "week": float(week.get("roi", 0) or 0),
                        "month": float(month.get("roi", 0) or 0),
                        "all_time": float(all_time.get("roi", 0) or 0),
                    },
                    "volume": {
                        "day": float(day.get("vlm", 0) or 0),
                        "week": float(week.get("vlm", 0) or 0),
                        "month": float(month.get("vlm", 0) or 0),
                    },
                    "pnl": {
                        "day": float(day.get("pnl", 0) or 0),
                        "week": float(week.get("pnl", 0) or 0),
                        "month": float(month.get("pnl", 0) or 0),
                        "all_time": float(all_time.get("pnl", 0) or 0),
                    },
                }

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
                    pos_status = "flat"
            else:
                pos_status = "unknown"

            # Apply filters
            if score_value < min_score:
                continue
            if max_score is not None and score_value > max_score:
                continue
            if account_value_min is not None and account_value < account_value_min:
                continue
            if account_value_max is not None and account_value > account_value_max:
                continue
            if has_positions is not None and has_pos != has_positions:
                continue
            if has_open_orders is not None and has_orders != has_open_orders:
                continue
            if position_status is not None and pos_status != position_status:
                continue
            if address_contains and address_contains.lower() not in address:
                continue
            if display_name_contains:
                display_name_value = str(display_name or "").lower()
                if display_name_contains.lower() not in display_name_value:
                    continue
            if tags_any_list and not any(item in normalized_tags for item in tags_any_list):
                continue
            if tags_all_list and not all(item in normalized_tags for item in tags_all_list):
                continue
            if tags_exclude_list and any(item in normalized_tags for item in tags_exclude_list):
                continue
            if roi_day_min is not None and (not metrics or metrics["roi"]["day"] < roi_day_min):
                continue
            if roi_day_max is not None and (not metrics or metrics["roi"]["day"] > roi_day_max):
                continue
            if roi_week_min is not None and (not metrics or metrics["roi"]["week"] < roi_week_min):
                continue
            if roi_week_max is not None and (not metrics or metrics["roi"]["week"] > roi_week_max):
                continue
            if roi_month_min is not None and (not metrics or metrics["roi"]["month"] < roi_month_min):
                continue
            if roi_month_max is not None and (not metrics or metrics["roi"]["month"] > roi_month_max):
                continue
            if roi_all_time_min is not None and (not metrics or metrics["roi"]["all_time"] < roi_all_time_min):
                continue
            if roi_all_time_max is not None and (not metrics or metrics["roi"]["all_time"] > roi_all_time_max):
                continue
            if volume_day_min is not None and (not metrics or metrics["volume"]["day"] < volume_day_min):
                continue
            if volume_day_max is not None and (not metrics or metrics["volume"]["day"] > volume_day_max):
                continue
            if volume_week_min is not None and (not metrics or metrics["volume"]["week"] < volume_week_min):
                continue
            if volume_week_max is not None and (not metrics or metrics["volume"]["week"] > volume_week_max):
                continue
            if volume_month_min is not None and (not metrics or metrics["volume"]["month"] < volume_month_min):
                continue
            if volume_month_max is not None and (not metrics or metrics["volume"]["month"] > volume_month_max):
                continue
            if profitable_window_list:
                if not metrics:
                    continue
                profitable_map = {
                    "day": metrics["roi"]["day"] > 0,
                    "week": metrics["roi"]["week"] > 0,
                    "month": metrics["roi"]["month"] > 0,
                    "all_time": metrics["roi"]["all_time"] > 0,
                }
                if not all(profitable_map.get(window, False) for window in profitable_window_list):
                    continue
            if updated_within_hours is not None and last_update:
                cutoff = datetime.now(UTC) - timedelta(hours=updated_within_hours)
                if last_update < cutoff:
                    continue
            if selected_address_set and address not in selected_address_set:
                continue

            trader_responses.append(
                TraderResponse(
                    address=address,
                    display_name=display_name,
                    score=score_value,
                    tags=t.get("tags", []),
                    account_value=account_value,
                    active=t.get("active", True),
                    has_positions=has_pos,
                    has_open_orders=has_orders,
                    open_order_count=order_count,
                    position_status=pos_status,
                    last_position_update=last_update,
                    metrics=metrics,
                )
            )

        reverse_sort = sort_dir.lower() != "asc"
        if sort_by == "account_value":
            trader_responses.sort(key=lambda item: float(item.account_value), reverse=reverse_sort)
        elif sort_by == "last_position_update":
            trader_responses.sort(
                key=lambda item: item.last_position_update or datetime.fromtimestamp(0, tz=UTC),
                reverse=reverse_sort,
            )
        elif sort_by == "address":
            trader_responses.sort(key=lambda item: item.address, reverse=reverse_sort)
        else:
            trader_responses.sort(key=lambda item: float(item.score), reverse=reverse_sort)

        matched_total = len(trader_responses)
        for item in trader_responses:
            if item.position_status == "unknown":
                total_unknown += 1
            elif item.position_status == "flat":
                total_flat += 1
            else:
                total_with_positions += 1
        paginated_traders = trader_responses[offset : offset + limit]

        filtered_query_applied = any(
            value is not None
            for value in (
                has_positions,
                has_open_orders,
                position_status,
                updated_within_hours,
                addresses,
            )
        )
        response_total = (
            matched_total
            if filtered_query_applied
            else (total if isinstance(total, int) else matched_total)
        )

        response = {
            "traders": paginated_traders,
            "total": response_total,
            "symbol": lifecycle._settings.hyperliquid.symbol,
            "total_with_positions": total_with_positions,
            "total_flat": total_flat,
            "total_unknown": total_unknown,
            "matched_total": matched_total,
            "returned_count": len(paginated_traders),
            "has_more": offset + len(paginated_traders) < matched_total,
            "applied_filters": {
                "min_score": min_score,
                "max_score": max_score,
                "tag": tag,
                "tags_any": tags_any_list,
                "tags_all": tags_all_list,
                "tags_exclude": tags_exclude_list,
                "has_positions": has_positions,
                "has_open_orders": has_open_orders,
                "position_status": position_status,
                "updated_within_hours": updated_within_hours,
                "address_contains": address_contains,
                "addresses": selected_addresses,
                "display_name_contains": display_name_contains,
                "account_value_min": account_value_min,
                "account_value_max": account_value_max,
                "roi_day_min": roi_day_min,
                "roi_day_max": roi_day_max,
                "roi_week_min": roi_week_min,
                "roi_week_max": roi_week_max,
                "roi_month_min": roi_month_min,
                "roi_month_max": roi_month_max,
                "roi_all_time_min": roi_all_time_min,
                "roi_all_time_max": roi_all_time_max,
                "volume_day_min": volume_day_min,
                "volume_day_max": volume_day_max,
                "volume_week_min": volume_week_min,
                "volume_week_max": volume_week_max,
                "volume_month_min": volume_month_min,
                "volume_month_max": volume_month_max,
                "profitable_windows": profitable_window_list,
                "offset": offset,
                "limit": limit,
                "sort_by": sort_by,
                "sort_dir": sort_dir,
                "include_total_mode": "exact" if include_exact_count else "none",
                "include_metrics": include_metrics,
            },
        }
        _TRADERS_ROUTE_CACHE[request_cache_key] = (time.time(), response)
        return response

    except TimeoutError:
        stale = _TRADERS_ROUTE_CACHE.get(request_cache_key)
        if stale:
            stale_response = dict(stale[1])
            stale_response["is_degraded"] = True
            stale_response["error"] = "traders query timed out; served stale cache"
            return stale_response
        return {
            "traders": [],
            "total": 0,
            "symbol": lifecycle._settings.hyperliquid.symbol,
            "total_with_positions": 0,
            "total_flat": 0,
            "total_unknown": 0,
            "matched_total": 0,
            "returned_count": 0,
            "has_more": False,
            "applied_filters": {},
            "is_degraded": True,
            "error": "traders query timed out",
        }
    except HTTPException:
        raise
    except Exception as e:
        stale = _TRADERS_ROUTE_CACHE.get(request_cache_key)
        if stale:
            stale_response = dict(stale[1])
            stale_response["is_degraded"] = True
            stale_response["error"] = str(e)
            return stale_response
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/batch", response_model=TraderBatchResponse)
async def get_traders_batch(
    request: TraderBatchRequest = Body(...),
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, Any]:
    """Return detailed trader snapshots for an exact address set."""
    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    if not request.addresses:
        raise HTTPException(status_code=400, detail="addresses must be a non-empty list")
    if len(request.addresses) > 1000:
        raise HTTPException(status_code=400, detail="addresses list cannot exceed 1000 entries")

    validated_addresses: list[str] = []
    seen: set[str] = set()
    for address in request.addresses:
        normalized = validate_eth_address(str(address))
        if normalized in seen:
            continue
        seen.add(normalized)
        validated_addresses.append(normalized)

    # Fast path for production reliability:
    # fetch only requested addresses with bounded async fan-out instead of prefetching
    # large tracked-trader windows that can stall on resource-constrained VPS nodes.
    async def _fetch_trader(address: str) -> tuple[str, dict[str, Any] | None]:
        row = await repository.get_trader_by_address(address)
        return address, row if isinstance(row, dict) else None

    fetch_tasks = [_fetch_trader(address) for address in validated_addresses]
    tracked_pairs = await asyncio.wait_for(
        asyncio.gather(*fetch_tasks, return_exceptions=False),
        timeout=_TRADERS_HARD_TIMEOUT_SECONDS,
    )
    tracked_by_address = {address: row for address, row in tracked_pairs if row is not None}

    states_by_address = await asyncio.wait_for(
        repository.get_trader_current_states(
            addresses=validated_addresses,
            symbol=lifecycle._settings.hyperliquid.symbol,
            include_legacy_fallback=False,
        ),
        timeout=_TRADERS_HARD_TIMEOUT_SECONDS,
    )

    traders_payload: list[dict[str, Any]] = []
    for address in validated_addresses:
        trader = tracked_by_address.get(address)
        if trader is None:
            continue
        if not request.include_inactive and not bool(trader.get("active", True)):
            continue
        state = states_by_address.get(address)
        positions, open_orders, position_status, has_positions = _extract_trader_state_summary(state)
        has_open_orders = len(open_orders) > 0

        performances = trader.get("performances", {})
        if not isinstance(performances, dict):
            performances = {}

        traders_payload.append(
            {
                "address": address,
                "display_name": trader.get("name", trader.get("displayName")),
                "score": _parse_float(trader.get("score", 0), 0.0),
                "tags": trader.get("tags", []),
                "account_value": _parse_float(
                    trader.get("acct_val", trader.get("accountValue", 0)),
                    0.0,
                ),
                "active": bool(trader.get("active", True)),
                "has_positions": has_positions,
                "has_open_orders": has_open_orders,
                "open_order_count": len(open_orders),
                "position_status": position_status,
                "last_position_update": state.get("updated_at") if isinstance(state, dict) else None,
                "performances": performances,
                "positions": positions,
                "open_orders": open_orders,
                "margin_summary": state.get("margin_summary", {}) if isinstance(state, dict) else {},
            }
        )

    return {
        "traders": traders_payload,
        "requested": len(validated_addresses),
        "found": len(traders_payload),
    }


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
                pos_data = _normalize_position(pos)
                positions.append(pos_data)

                # Check for BTC position
                if pos_data.get("coin") == "BTC":
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
