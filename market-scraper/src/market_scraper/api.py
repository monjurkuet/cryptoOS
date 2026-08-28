"""REST API routes."""
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from market_scraper.db import get_db
from market_scraper.services.candles import fetch_kraken_candles, get_btc_price

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check — validates MongoDB connectivity."""
    try:
        db = get_db()
        await db.command("ping")
        return {"status": "ok", "mongo": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"MongoDB unreachable: {e}") from e


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    """Lightweight liveness probe — returns immediately without DB check."""
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

    if has_positions is not None:
        # Flip query: find traders with/without positions first, then join
        state_filter = {"positions.0": {"$exists": True}} if has_positions \
            else {"$or": [{"positions": {"$size": 0}}, {"positions": {"$exists": False}}]}

        # Get eth addresses that match position filter
        state_eths = set()
        state_cursor = db.trader_current_state.find(state_filter, {"eth": 1, "_id": 0})
        async for s in state_cursor:
            state_eths.add(s["eth"])

        if not state_eths:
            return {"traders": [], "count": 0}

        # Now get trader details, sorted and limited
        trader_filter = {"eth": {"$in": list(state_eths)}, "score": {"$gte": min_score}}
        cursor = db.tracked_traders.find(
            trader_filter, {"_id": 0}, sort=[(sort_by, sort_order)]
        ).limit(limit)
        traders = await cursor.to_list(length=limit)

        # Get states for result set
        result_eths = [t.get("eth") for t in traders]
        states = {}
        if result_eths:
            async for s in db.trader_current_state.find(
                {"eth": {"$in": result_eths}}, {"_id": 0}
            ):
                states[s["eth"]] = s
    else:
        cursor = db.tracked_traders.find(
            {"score": {"$gte": min_score}},
            {"_id": 0},
            sort=[(sort_by, sort_order)],
        ).limit(limit)
        traders = await cursor.to_list(length=limit)

        eths = [t.get("eth") for t in traders]
        states = {}
        if eths:
            async for s in db.trader_current_state.find(
                {"eth": {"$in": eths}}, {"_id": 0}
            ):
                states[s["eth"]] = s

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


@router.get("/api/v1/traders/profitable")
async def profitable_traders(
    limit: int = Query(50, ge=1, le=200),
    min_roi_month: float = Query(0.1, ge=-1),
    min_roi_all: float = Query(0.2, ge=-1),
    require_consistent: bool = Query(True),
) -> dict[str, Any]:
    """Consistently profitable traders — strict filter + returns live position summary."""
    db = get_db()
    filt: dict[str, Any] = {"roi_all_time": {"$gte": min_roi_all}, "roi_month": {"$gte": min_roi_month}}
    if require_consistent:
        filt["roi_week"] = {"$gt": 0}
        filt["roi_day"] = {"$gt": 0}
    cursor = db.tracked_traders.find(filt, {"_id": 0}, sort=[("score", -1)]).limit(limit)
    traders = await cursor.to_list(length=limit)
    eths = [t["eth"] for t in traders]
    states = {}
    if eths:
        async for s in db.trader_current_state.find({"eth": {"$in": eths}}, {"_id": 0}):
            states[s["eth"]] = s
    result = []
    for t in traders:
        s = states.get(t["eth"], {})
        result.append({
            **{k: t[k] for k in ["eth", "name", "score", "acct_val", "roi_all_time", "roi_month", "roi_week", "roi_day", "tags"]},
            "position_status": _get_position_status(s),
            "position_count": len(s.get("positions", [])) if s else 0,
            "last_position_update": s.get("updated_at").isoformat() if s and s.get("updated_at") else None,
        })
    return {"traders": result, "count": len(result), "filter": {"min_roi_month": min_roi_month, "min_roi_all": min_roi_all, "consistent": require_consistent}}

@router.get("/api/v1/traders/{address}")
async def get_trader(address: str) -> dict[str, Any]:
    """Get single trader detail with current state."""
    db = get_db()
    addr = address.lower()
    trader = await db.tracked_traders.find_one({"eth": addr}, {"_id": 0})
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")
    state = await db.trader_current_state.find_one({"eth": addr}, {"_id": 0})
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
        {"_id": 0},
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
        {"_id": 0},
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


# ---- BTC historical & live data ----
@router.get("/api/v1/btc/price")
async def btc_price() -> dict[str, Any]:
    """Live BTC price (Kraken -> Coingecko fallback)."""
    return await get_btc_price()


@router.get("/api/v1/btc/candles")
async def btc_candles(
    interval: str = Query("1h", pattern="^(1m|5m|15m|1h|4h|1d)$"),
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    """Historical BTC candles — live from Kraken + fallback to DB if available."""
    db = get_db()
    col_name = f"btc_candles_{interval}"
    # Try DB first (if has recent data within 2 days)
    try:
        col = db[col_name]
        cursor = col.find({}, {"_id": 0}, sort=[("t", -1)]).limit(limit)
        docs = await cursor.to_list(length=limit)
        if docs and (datetime.now(UTC) - docs[0].get("t", datetime.min.replace(tzinfo=UTC))).total_seconds() < 172800:
            docs.reverse()
            return {"interval": interval, "candles": docs, "count": len(docs), "source": "db"}
    except Exception:
        pass
    # Fallback live fetch
    live = await fetch_kraken_candles(interval=interval, limit=limit)
    # Normalize to API shape
    normalized = [
        {"t": c["t"].isoformat(), "open": c["open"], "high": c["high"], "low": c["low"], "close": c["close"], "volume": c["volume"]}
        for c in live
    ]
    return {"interval": interval, "candles": normalized, "count": len(normalized), "source": "kraken_live"}


@router.get("/api/v1/btc/history")
async def btc_history(
    interval: str = Query("1h", pattern="^(1m|5m|15m|1h|4h|1d)$"),
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    """BTC history from DB for range."""
    db = get_db()
    col_name = f"btc_candles_{interval}"
    since = datetime.now(UTC) - timedelta(hours=hours)
    col = db[col_name]
    cursor = col.find({"t": {"$gte": since}}, {"_id": 0}, sort=[("t", 1)]).limit(limit)
    docs = await cursor.to_list(length=limit)
    if not docs:
        # fallback live
        live = await fetch_kraken_candles(interval=interval, limit=limit)
        docs = [{"t": c["t"].isoformat(), "open": c["open"], "high": c["high"], "low": c["low"], "close": c["close"], "volume": c["volume"]} for c in live]
        return {"interval": interval, "candles": docs, "count": len(docs), "source": "kraken_live"}
    # iso format times
    for d in docs:
        if isinstance(d.get("t"), datetime):
            d["t"] = d["t"].isoformat()
    return {"interval": interval, "candles": docs, "count": len(docs), "source": "db"}
