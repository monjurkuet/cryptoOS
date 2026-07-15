"""REST API routes."""
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from market_scraper.db import get_db

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check — validates MongoDB connectivity."""
    try:
        db = get_db()
        await db.command("ping")
        return {"status": "ok", "mongo": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unreachable: {e}")


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    """Lightweight liveness check for reverse-proxy & monitoring."""
    return {"status": "alive"}


@router.get("/api/v1/traders")
async def list_traders(
    limit: int = Query(50, ge=1, le=1000),
    min_score: float = Query(0, ge=0),
    has_positions: bool | None = Query(None),
    sort_by: str = Query(
        "score",
        pattern="^(score|roi_all_time|acct_val|last_position_update)$",
    ),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
) -> dict[str, Any]:
    """List tracked traders with current positions."""
    db = get_db()
    sort_order = -1 if sort_dir == "desc" else 1

    cursor = (
        db.tracked_traders.find(
            {"score": {"$gte": min_score}},
            sort=[(sort_by, sort_order)],
        ).limit(limit)
    )
    traders = await cursor.to_list(length=limit)

    # Filter by position status if requested
    eths = [t.get("eth") for t in traders]
    states = {}
    if eths:
        state_cursor = db.trader_current_state.find({"eth": {"$in": eths}})
        async for s in state_cursor:
            states[s["eth"]] = s

    if has_positions is not None:
        traders = [
            t for t in traders
            if (has_positions and states.get(t.get("eth"), {}).get("positions"))
            or (not has_positions and not states.get(t.get("eth"), {}).get("positions"))
        ]

    result = []
    for t in traders:
        state = states.get(t.get("eth"), {})
        result.append({
            "eth": t.get("eth"),
            "name": t.get("name"),
            "score": t.get("score"),
            "acct_val": t.get("acct_val"),
            "tags": t.get("tags", []),
            "roi_all_time": t.get("roi_all_time"),
            "roi_month": t.get("roi_month"),
            "position_status": _get_position_status(state),
            "position_count": len(state.get("positions", [])) if state else 0,
            "last_position_update": state.get("updated_at").isoformat()
                if state and state.get("updated_at")
                else None,
        })

    return {"traders": result, "count": len(result)}


@router.get("/api/v1/traders/{address}")
async def get_trader(address: str) -> dict[str, Any]:
    """Get single trader detail with current state."""
    db = get_db()
    addr = address.lower()
    trader = await db.tracked_traders.find_one({"eth": addr})
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
    state = await db.trader_current_state.find_one({"eth": addr})
    return {
        **trader,
        "current_state": state or {},
    }


@router.get("/api/v1/leaderboard")
async def list_leaderboard(
    limit: int = Query(100, ge=1, le=1000),
    min_score: float = Query(0, ge=0),
) -> dict[str, Any]:
    """Query latest leaderboard snapshot."""
    db = get_db()
    doc = await db.leaderboard_daily.find_one(
        {},
        sort=[("date", -1)],
    )
    if not doc:
        return {"date": None, "rows": [], "count": 0}

    rows = [
        r for r in doc.get("rows", [])
        if r.get("score", 0) >= min_score
    ]
    rows = rows[:limit]

    return {
        "date": doc.get("date"),
        "total_fetched": doc.get("total_fetched"),
        "rows": rows,
        "count": len(rows),
    }


@router.get("/api/v1/positions/{address}/history")
async def get_position_history(
    address: str,
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    """Get position history for a trader."""
    db = get_db()
    addr = address.lower()
    since = datetime.now(UTC) - timedelta(hours=hours)
    cursor = db.trader_positions.find(
        {"eth": addr, "t": {"$gte": since}},
        sort=[("t", -1)],
    ).limit(limit)
    return {"positions": await cursor.to_list(length=limit)}


def _get_position_status(state: dict | None) -> str:
    if not state:
        return "unknown"
    positions = state.get("positions", [])
    if not positions:
        return "flat"
    has_long = any(
        float(p.get("position", {}).get("szi", 0)) > 0
        for p in positions
        if isinstance(p, dict)
    )
    has_short = any(
        float(p.get("position", {}).get("szi", 0)) < 0
        for p in positions
        if isinstance(p, dict)
    )
    if has_long and has_short:
        return "mixed"
    return "long" if has_long else "short"
