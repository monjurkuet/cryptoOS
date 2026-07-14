# cryptoOS Fresh-Start Architecture — Revised

**Principle**: Google/Meta don't build complex systems for simple jobs. One job = one service. Flat, boring, correct.

---

## What This System Actually Does

```
DAILY:  Fetch 39K traders → Score → Filter → Store top 1000
        (runs once per day, takes ~30 seconds)

LOOP:   Monitor 5 traders at a time via 1 WebSocket
        Cycle through 1000 traders in ~3.3 hours
        Save positions to MongoDB on every update
        Repeat forever

API:    Dashboard reads from MongoDB
```

That's the entire system. Everything else is infrastructure around those three jobs.

---

## Revised Configuration

```yaml
# config.yaml (single file, no nested config classes)
leaderboard:
  # When to run daily fetch
  fetch_cron: "0 0 * * *"          # midnight UTC

  # Scoring weights (must sum to 100)
  weights:
    roi_all_time: 30
    roi_month: 25
    roi_week: 20
    account_value: 15
    volume_month: 10

  # Hard filter: ALL must be true for a trader to be tracked
  require_positive:
    - all_time
    - year
    - month

  # Maximum traders to track after scoring
  max_tracked: 1000

position_monitor:
  batch_size: 5
  dwell_seconds: 60
  symbol: BTC
  ws_url: wss://api.hyperliquid.xyz/ws
  # Position ordering: process lowest-ROI first, highest-ROI last
  # Highest-ROI traders get sampled most frequently (cycle restarts)
  sort_ascending_by_roi: true

  # Hash dedup: skip DB writes when position unchanged
  enable_hash_dedup: true

api:
  host: "127.0.0.1"
  port: 3845

storage:
  mongo_url: "${MONGO__URL}"
  mongo_db: "${MONGO__DATABASE}"
  # TTL retention per collection
  retention:
    leaderboard_daily: 365     # 1 year of daily snapshots
    tracked_traders: null      # no TTL — replaced daily
    trader_positions: 30       # 30 days of position history
    trader_current_state: null # no TTL — always current
    candles: 30                # 30 days if candles enabled
```

---

## Architecture: Three Services in One Process

```
┌──────────────────────────────────────────────────────────────────┐
│                     market-scraper (1 process)                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────┐  ┌──────────────────┐  ┌────────────┐  │
│  │  Daily Leaderboard  │  │  Position Monitor │  │  REST API  │  │
│  │  (cron: midnight)   │  │  (loop: forever)  │  │  (FastAPI) │  │
│  └─────────┬───────────┘  └────────┬─────────┘  └──────┬─────┘  │
│            │                       │                     │        │
│            └───────────┬───────────┘                     │        │
│                        │                                 │        │
│                 ┌──────▼──────┐                          │        │
│                 │   MongoDB   │◄─────────────────────────┘        │
│                 │  (Motor)    │                                   │
│                 └─────────────┘                                   │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

**No Redis. No event bus. No processors. No schedulers. No archival.**

Two independent async tasks + one HTTP server, all sharing one MongoDB connection pool.

---

## MongoDB Collections (4 collections — not 20)

| Collection | Purpose | TTL | Replaced How |
|------------|---------|-----|--------------|
| `leaderboard_daily` | Full 39K trader score snapshots, date-partitioned | 365 days | New doc per day, TTL deletes old |
| `tracked_traders` | Top 1000 scored traders (active set) | None | Replaced wholesale daily by leaderboard cron |
| `trader_positions` | Time-series position history | 30 days | Appended by position monitor |
| `trader_current_state` | Latest position per trader (upsert) | None | Updated by position monitor on every change |

**Why only 4?** We're not storing: raw events (audit log), separate signals, separate score history, separate leaderboard history with scores, separate candle buffers, separate trade logs. Those are all future-if-needed.

---

## Module Structure

```
market-scraper/
├── main.py                     # Entry point (15 lines)
├── config.py                   # Pydantic Settings (50 lines)
├── db.py                       # MongoDB connection (25 lines)
├── models.py                   # Pydantic models (80 lines)
├── services/
│   ├── leaderboard.py          # Daily fetch + score + filter (200 lines)
│   └── monitor.py              # Serial WS position monitor (350 lines)
├── api.py                      # FastAPI routes (150 lines)
├── config.yaml                 # Runtime config
├── pyproject.toml              # Dependencies
└── tests/
    ├── test_leaderboard.py     # Score + filter logic
    ├── test_monitor.py         # Batch processing + dedup
    └── test_api.py             # API contract
```

**Total: ~870 lines** (vs current 47,502). One file per responsibility. No inheritance hierarchy.

---

## Detailed Module Design

### `main.py` — Entry Point
```python
import asyncio
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from db import connect_mongo, close_mongo
from services.leaderboard import LeaderboardService
from services.monitor import PositionMonitor
from config import get_config

@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_config()
    db = await connect_mongo(cfg.mongo_url, cfg.mongo_db)
    
    # Start background tasks
    monitor = PositionMonitor(db, cfg)
    monitor_task = asyncio.create_task(monitor.run_forever())
    
    yield
    
    monitor_task.cancel()
    await close_mongo()

app = FastAPI(lifespan=lifespan)
# Mount API routes...
```

### `config.py` — Single Settings Class
```python
from pydantic_settings import BaseSettings
from pydantic import BaseModel

class LeaderboardConfig(BaseModel):
    weights: dict[str, float] = {"roi_all_time": 30, "roi_month": 25, "roi_week": 20, "account_value": 15, "volume_month": 10}
    require_positive: list[str] = ["all_time", "year", "month"]
    max_tracked: int = 1000

class MonitorConfig(BaseModel):
    batch_size: int = 5
    dwell_seconds: int = 60
    symbol: str = "BTC"
    ws_url: str = "wss://api.hyperliquid.xyz/ws"
    sort_ascending_by_roi: bool = True
    enable_hash_dedup: bool = True

class Settings(BaseSettings):
    mongo_url: str
    mongo_db: str = "market_scraper"
    api_host: str = "127.0.0.1"
    api_port: int = 3845
    leaderboard: LeaderboardConfig = LeaderboardConfig()
    monitor: MonitorConfig = MonitorConfig()
    
    model_config = SettingsConfigDict(env_nested_delimiter="__")
```

### `db.py` — MongoDB Connection
```python
import motor.motor_asyncio
from pymongo import ASCENDING, DESCENDING, IndexModel

_client: motor.motor_asyncio.AsyncIOMotorClient | None = None
_db: motor.motor_asyncio.AsyncIOMotorDatabase | None = None

async def connect_mongo(url: str, db_name: str):
    global _client, _db
    _client = motor.motor_asyncio.AsyncIOMotorClient(url)
    _db = _client[db_name]
    await _ensure_indexes(_db)
    return _db

async def _ensure_indexes(db):
    await db.leaderboard_daily.create_indexes([
        IndexModel([("date", DESCENDING)]),
        IndexModel([("date", DESCENDING), ("score", DESCENDING)]),
        # TTL index: auto-delete after 365 days
        IndexModel([("created_at", ASCENDING)], expireAfterSeconds=365*86400),
    ])
    await db.tracked_traders.create_indexes([
        IndexModel([("eth", ASCENDING)], unique=True),
        IndexModel([("score", DESCENDING)]),
    ])
    await db.trader_positions.create_indexes([
        IndexModel([("eth", ASCENDING), ("t", DESCENDING)]),
        # TTL: auto-delete after 30 days
        IndexModel([("t", ASCENDING)], expireAfterSeconds=30*86400),
    ])
    await db.trader_current_state.create_indexes([
        IndexModel([("eth", ASCENDING)], unique=True),
    ])

def get_db():
    return _db
```

### `models.py` — Clean Data Models
```python
from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Any

class LeaderboardRow(BaseModel):
    eth: str
    name: str | None = None
    acct_val: float = 0
    roi_all_time: float = 0
    roi_year: float = 0
    roi_month: float = 0
    roi_week: float = 0
    roi_day: float = 0
    volume_month: float = 0
    pnl_all_time: float = 0
    score: float = 0
    tags: list[str] = []
    rank: int = 0

class TrackedTrader(BaseModel):
    eth: str
    name: str | None = None
    acct_val: float = 0
    score: float = 0
    tags: list[str] = []
    leaderboard_rank: int = 0
    selected_at: datetime
    last_position_update: datetime | None = None
    position_hash: str | None = None

class Position(BaseModel):
    eth: str
    symbol: str
    size: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: float
    liquidation_price: float | None = None
    timestamp: datetime

class TraderState(BaseModel):
    eth: str
    symbol: str
    positions: list[dict[str, Any]] = []
    open_orders: list[dict[str, Any]] = []
    margin_summary: dict[str, Any] = {}
    position_hash: str
    updated_at: datetime
```

### `services/leaderboard.py` — Daily Fetch + Score + Filter
```python
from datetime import date, datetime, UTC
import structlog
import httpx
from db import get_db
from models import LeaderboardRow

LEADERBOARD_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"

class LeaderboardService:
    def __init__(self, config):
        self.config = config
    
    async def run_daily(self) -> int:
        """Fetch, score, filter, store. Returns number of tracked traders."""
        # 1. Fetch raw leaderboard
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(LEADERBOARD_URL)
            rows_raw = resp.json().get("leaderboardRows", [])
        
        # 2. Score + parse all 39K traders
        scored = [self._score_trader(row, i) for i, row in enumerate(rows_raw)]
        
        # 3. Hard filter: ALL required ROIs must be positive
        filtered = [
            r for r in scored
            if (r.roi_all_time > 0
                and r.roi_year > 0
                and r.roi_month > 0
                and r.acct_val >= 10000)
        ]
        
        # 4. Sort by score descending, take top 1000
        filtered.sort(key=lambda x: x.score, reverse=True)
        tracked = filtered[:self.config.leaderboard.max_tracked]
        
        # 5. Store to MongoDB
        db = get_db()
        today = date.today()
        
        # Store full snapshot (with TTL for automatic cleanup)
        await db.leaderboard_daily.update_one(
            {"date": today.isoformat()},
            {"$set": {
                "date": today.isoformat(),
                "rows": [r.model_dump() for r in scored[:10000]],  # top 10K for historical
                "total_fetched": len(rows_raw),
                "created_at": datetime.now(UTC),
            }},
            upsert=True,
        )
        
        # Replace tracked_traders (daily refresh)
        await db.tracked_traders.delete_many({})
        await db.tracked_traders.insert_many([
            {
                **t.model_dump(),
                "selected_at": datetime.now(UTC),
            }
            for t in tracked
        ])
        
        structlog.get_logger().info(
            "leaderboard_daily_complete",
            fetched=len(rows_raw),
            scored=len(scored),
            filtered=len(filtered),
            tracked=len(tracked),
        )
        return len(tracked)
    
    def _score_trader(self, row: dict, rank: int) -> LeaderboardRow:
        """Score a single trader from leaderboard API response."""
        # Parse window performances
        perfs = {}
        for p in row.get("windowPerformances", []):
            if len(p) >= 2:
                perfs[p[0]] = p[1]
        
        def get_roi(window: str) -> float:
            return float(perfs.get(window, {}).get("roi", 0) or 0)
        
        def get_volume(window: str) -> float:
            return float(perfs.get(window, {}).get("vlm", 0) or 0)
        
        acct_val = float(row.get("accountValue", 0))
        
        # Calculate score using configured weights
        score = 0.0
        w = self.config.leaderboard.weights
        
        score += min(get_roi("allTime") * 30, w.get("roi_all_time", 30))
        score += min(get_roi("month") * 50, w.get("roi_month", 25))
        score += max(min(get_roi("week") * 100, w.get("roi_week", 20)), -10)
        
        # Account value tier scoring
        if acct_val >= 10_000_000: score += w.get("account_value", 15) * 1.0
        elif acct_val >= 1_000_000: score += w.get("account_value", 15) * 0.8
        elif acct_val >= 100_000: score += w.get("account_value", 15) * 0.5
        elif acct_val >= 10_000: score += w.get("account_value", 15) * 0.3
        
        # Volume scoring
        month_vol = get_volume("month")
        vol_weight = w.get("volume_month", 10)
        if month_vol >= 100_000_000: score += vol_weight * 1.0
        elif month_vol >= 10_000_000: score += vol_weight * 0.7
        elif month_vol >= 1_000_000: score += vol_weight * 0.4
        
        # Tags
        tags = []
        if acct_val >= 10_000_000: tags.append("whale")
        if acct_val >= 1_000_000: tags.append("large")
        if get_roi("day") > 0 and get_roi("week") > 0 and get_roi("month") > 0:
            tags.append("consistent")
        if get_roi("allTime") > 1.0: tags.append("high_performer")
        if score > 80: tags.append("elite")
        
        return LeaderboardRow(
            eth=row.get("ethAddress", "").lower(),
            name=row.get("displayName"),
            acct_val=acct_val,
            roi_all_time=get_roi("allTime"),
            roi_year=float(perfs.get("year", {}).get("roi", 0) or 0),
            roi_month=get_roi("month"),
            roi_week=get_roi("week"),
            roi_day=get_roi("day"),
            volume_month=get_volume("month"),
            pnl_all_time=float(perfs.get("allTime", {}).get("pnl", 0) or 0),
            score=round(score, 2),
            tags=tags,
            rank=rank + 1,
        )
```

### `services/monitor.py` — Serial Position Monitor
```python
import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
import structlog
import websockets
from db import get_db
from models import Position, TraderState

logger = structlog.get_logger(__name__)

class PositionMonitor:
    """Single WebSocket, 5 traders at a time, 60s dwell. Ascending ROI order."""
    
    def __init__(self, config):
        self.config = config
        self._running = True
    
    async def run_forever(self):
        """Main loop: fetch tracked traders, cycle through batches."""
        while self._running:
            try:
                traders = await self._get_tracked_traders()
                if not traders:
                    logger.info("monitor_no_traders")
                    await asyncio.sleep(300)
                    continue
                
                # Sort ascending by ROI — lowest first, highest last
                # Highest-ROI traders get sampled most frequently (cycle restarts)
                traders.sort(key=lambda t: t.roi_all_time)
                
                logger.info("monitor_cycle_start", traders=len(traders))
                
                for i in range(0, len(traders), self.config.batch_size):
                    if not self._running:
                        break
                    batch = traders[i:i + self.config.batch_size]
                    await self._process_batch(batch)
                
                logger.info("monitor_cycle_complete")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("monitor_cycle_error", error=str(e))
                await asyncio.sleep(30)
    
    async def _get_tracked_traders(self) -> list:
        """Get tracked traders from MongoDB, sorted by ROI ascending."""
        db = get_db()
        cursor = db.tracked_traders.find({}).sort("roi_all_time", 1)
        return await cursor.to_list(length=1000)
    
    async def _process_batch(self, traders: list[dict]):
        """Connect WS, subscribe, listen for DWELL seconds, store positions."""
        addresses = [t["eth"].lower() for t in traders if t.get("eth")]
        if not addresses:
            return
        
        logger.info("monitor_batch_connecting", batch_size=len(addresses))
        
        try:
            async with websockets.connect(
                self.config.ws_url,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                # Subscribe all traders in batch
                for addr in addresses:
                    await ws.send(json.dumps({
                        "method": "subscribe",
                        "subscription": {"type": "webData2", "user": addr}
                    }))
                    await asyncio.sleep(0.05)
                
                logger.info("monitor_batch_subscribed", addresses=len(addresses))
                
                # Listen for dwell_seconds
                end_time = time.monotonic() + self.config.dwell_seconds
                messages_processed = 0
                while time.monotonic() < end_time:
                    try:
                        msg = await asyncio.wait_for(
                            ws.recv(),
                            timeout=min(1.0, end_time - time.monotonic())
                        )
                        await self._handle_message(msg)
                        messages_processed += 1
                    except asyncio.TimeoutError:
                        continue
                    except websockets.ConnectionClosed:
                        break
                
                # Clean unsubscribe before closing
                for addr in addresses:
                    try:
                        await ws.send(json.dumps({
                            "method": "unsubscribe",
                            "subscription": {"type": "webData2", "user": addr}
                        }))
                    except Exception:
                        pass
                
                logger.info("monitor_batch_complete", messages=messages_processed)
        
        except Exception as e:
            logger.error("monitor_batch_error", error=str(e))
    
    async def _handle_message(self, msg: str):
        """Parse webData2, normalize, dedup, store to MongoDB."""
        try:
            data = json.loads(msg)
        except json.JSONDecodeError:
            return
        
        if data.get("channel") != "webData2":
            return
        
        payload = data.get("data", {})
        eth = str(payload.get("user", "")).lower()
        if not eth:
            return
        
        # Extract clearinghouse state
        ch = payload.get("clearinghouseState", {})
        if not isinstance(ch, dict):
            return
        
        # Filter to configured symbol only
        symbol = self.config.symbol.upper()
        raw_positions = ch.get("assetPositions", [])
        if not isinstance(raw_positions, list):
            raw_positions = []
        
        positions = []
        for raw_pos in raw_positions:
            pos = raw_pos.get("position", {})
            if not isinstance(pos, dict):
                continue
            if pos.get("coin", "").upper() != symbol:
                continue
            try:
                if float(pos.get("szi", 0)) != 0:
                    positions.append(raw_pos)
            except (TypeError, ValueError):
                pass
        
        # Open orders for this symbol
        raw_orders = payload.get("openOrders", [])
        if not isinstance(raw_orders, list):
            raw_orders = []
        open_orders = [
            o for o in raw_orders
            if isinstance(o, dict)
            and o.get("coin", "").upper() == symbol
        ]
        
        margin_summary = ch.get("marginSummary", {})
        if not isinstance(margin_summary, dict):
            margin_summary = {}
        
        # Hash for dedup
        position_str = json.dumps(positions, sort_keys=True, separators=(",", ":"))
        orders_str = json.dumps(open_orders, sort_keys=True, separators=(",", ":"))
        margin_str = json.dumps(margin_summary, sort_keys=True, separators=(",", ":"))
        position_hash = hashlib.sha256(
            (position_str + orders_str + margin_str).encode()
        ).hexdigest()
        
        # Check if changed
        if self.config.enable_hash_dedup:
            db = get_db()
            existing = await db.trader_current_state.find_one({"eth": eth})
            if existing and existing.get("position_hash") == position_hash:
                return  # No change — skip write
        
        now = datetime.now(UTC)
        
        # Store current state (upsert)
        await db.trader_current_state.update_one(
            {"eth": eth},
            {"$set": {
                "eth": eth,
                "symbol": symbol,
                "positions": positions,
                "open_orders": open_orders,
                "margin_summary": margin_summary,
                "position_hash": position_hash,
                "updated_at": now,
            }},
            upsert=True,
        )
        
        # Store position history (append for time-series queries)
        for raw_pos in positions:
            pos = raw_pos.get("position", {})
            await db.trader_positions.insert_one({
                "eth": eth,
                "symbol": symbol,
                "size": float(pos.get("szi", 0)),
                "entry_price": float(pos.get("entryPx", 0)),
                "mark_price": float(pos.get("markPx", 0)),
                "unrealized_pnl": float(pos.get("unrealizedPnl", 0)),
                "leverage": float(pos.get("leverage", 1)) if not isinstance(pos.get("leverage"), dict) else 1,
                "liquidation_price": float(pos.get("liquidationPx", 0)) if pos.get("liquidationPx") else None,
                "t": now,
            })
        
        # Update trader's last position timestamp
        await db.tracked_traders.update_one(
            {"eth": eth},
            {"$set": {"last_position_update": now, "position_hash": position_hash}}
        )
    
    def stop(self):
        self._running = False
```

### `api.py` — Minimal REST API
```python
from fastapi import APIRouter, HTTPException, Query
from db import get_db
from datetime import datetime, timedelta, UTC

router = APIRouter()

@router.get("/health")
async def health():
    """Health check — also validates MongoDB connection."""
    try:
        db = get_db()
        await db.command("ping")
        return {"status": "ok", "mongo": "connected"}
    except Exception as e:
        raise HTTPException(503, detail=f"MongoDB unreachable: {e}")

@router.get("/api/v1/traders")
async def list_traders(
    limit: int = Query(50, ge=1, le=1000),
    min_score: float = Query(0, ge=0),
    has_positions: bool | None = Query(None),
    sort_by: str = Query("score", pattern="^(score|roi_all_time|acct_val|last_position_update)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
):
    """List tracked traders with current positions."""
    db = get_db()
    sort_order = -1 if sort_dir == "desc" else 1
    cursor = db.tracked_traders.find(
        {"score": {"$gte": min_score}},
        sort=[(sort_by, sort_order)],
    ).limit(limit)
    traders = await cursor.to_list(length=limit)
    
    # Enrich with current state
    result = []
    for t in traders:
        state = await db.trader_current_state.find_one({"eth": t.get("eth")})
        result.append({
            "eth": t.get("eth"),
            "name": t.get("name"),
            "score": t.get("score"),
            "acct_val": t.get("acct_val"),
            "tags": t.get("tags", []),
            "roi_all_time": t.get("roi_all_time"),
            "roi_month": t.get("roi_month"),
            "position_status": _get_position_status(state),
            "positions": state.get("positions", []) if state else [],
            "open_orders": state.get("open_orders", []) if state else [],
            "margin_summary": state.get("margin_summary", {}) if state else {},
            "last_update": state.get("updated_at").isoformat() if state and state.get("updated_at") else None,
        })
    
    return {"traders": result, "count": len(result)}

@router.get("/api/v1/traders/{address}")
async def get_trader(address: str):
    """Get single trader detail."""
    db = get_db()
    trader = await db.tracked_traders.find_one({"eth": address.lower()})
    if not trader:
        raise HTTPException(404, "Trader not found")
    state = await db.trader_current_state.find_one({"eth": address.lower()})
    return {**trader, "current_state": state or {}}

@router.get("/api/v1/leaderboard")
async def list_leaderboard(
    days_back: int = Query(1, ge=1, le=30),
    limit: int = Query(100, ge=1, le=1000),
    min_score: float = Query(0, ge=0),
):
    """Query stored leaderboard snapshots."""
    db = get_db()
    from datetime import date, timedelta
    start_date = (date.today() - timedelta(days=days_back)).isoformat()
    docs = await db.leaderboard_daily.find(
        {"date": {"$gte": start_date}},
        sort=[("date", -1)],
    ).to_list(length=10)
    
    rows = []
    for doc in docs:
        for row in doc.get("rows", [])[:limit]:
            if row.get("score", 0) >= min_score:
                rows.append(row)
    
    return {"snapshots": len(docs), "rows": rows[:limit]}

@router.get("/api/v1/positions/{address}/history")
async def get_position_history(
    address: str,
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get historical position data for a trader."""
    db = get_db()
    since = datetime.now(UTC) - timedelta(hours=hours)
    cursor = db.trader_positions.find(
        {"eth": address.lower(), "t": {"$gte": since}},
        sort=[("t", -1)],
    ).limit(limit)
    return {"positions": await cursor.to_list(length=limit)}

def _get_position_status(state: dict | None) -> str:
    if not state:
        return "unknown"
    positions = state.get("positions", [])
    if not positions:
        return "flat"
    # Check if any position has non-zero size
    has_long = any(float(p.get("position", {}).get("szi", 0)) > 0 for p in positions)
    has_short = any(float(p.get("position", {}).get("szi", 0)) < 0 for p in positions)
    if has_long and has_short:
        return "mixed"
    return "long" if has_long else "short"
```

---

## Candles: Optional Add-On (NOT in MVP)

If you want candles later, add `services/candles.py` as a separate async task. Hyperliquid WS allows subscribing to candle channels on the same connection as webData2. The candles collector is ~100 lines and stores to `candles` collection (TTL 30 days).

**Not needed for trader position tracking.** Add when you have a dashboard that needs historical price data alongside positions.

---

## Redis: Not Needed

Redis was used for:
1. Pub/Sub between components → We don't have separate components
2. Event bus for processors → We don't have processors
3. External consumers (signal-system) → Not deployed, not in scope

**If** you need Redis later (e.g., for a separate signal-system microservice), add it then. Don't build for a future that doesn't exist.

---

## Crons: One Simple Cron

```bash
# Daily leaderboard fetch at midnight UTC
0 0 * * * cd /home/administrator/githubrepo/cryptoOS/market-scraper && \
    /home/administrator/githubrepo/cryptoOS/.venv/bin/python -m services.leaderboard
```

That's it. One cron. No scheduler library, no cron-parser, no task registry.

---

## Test Plan

| Test File | What It Tests |
|-----------|---------------|
| `test_leaderboard.py` | Score calculation, filter logic (ROI > 0), sort order, max_tracked limit |
| `test_monitor.py` | Batch processing, hash dedup (skip unchanged), WS connect/subscribe/unsubscribe |
| `test_api.py` | GET /traders, GET /leaderboard, GET /positions/{addr}/history |

**Coverage target**: 80%+ on `services/` (the actual business logic). API routes are thin enough to trust.

---

## Resource Projections

| Metric | Old | New |
|--------|-----|-----|
| Lines of code | 47,502 | ~870 |
| Files | 200+ | 9 |
| WS connections | 5 parallel (50 traders) | 1 serial (5 traders) |
| DB collections | 20+ | 4 |
| Dependencies | 29 (motor, redis, aiohttp, httpx, websockets, pydantic, structlog, fastapi, uvicorn, prometheus-client, zstandard, argon2-cffi, etc.) | 6 (motor, httpx, websockets, pydantic-settings, structlog, fastapi+uvicorn) |
| Memory (runtime) | 289MB (peak 474MB) | <100MB |
| Event loop lag | Frequent spikes (180s) | None (no concurrent WS, no Redis) |
| Cycle time (1000 traders) | N/A (not tracked) | 3.3 hours |

---

## Migration: What to Delete

After new code is working:

```
DELETE:
├── market-scraper/src/market_scraper/connectors/hyperliquid/collectors/trader_ws.py
├── market-scraper/src/market_scraper/connectors/hyperliquid/collectors/leaderboard.py
├── market-scraper/src/market_scraper/connectors/hyperliquid/collectors/manager.py
├── market-scraper/src/market_scraper/connectors/hyperliquid/collectors/base.py
├── market-scraper/src/market_scraper/connectors/hyperliquid/collectors/candles.py
├── market-scraper/src/market_scraper/connectors/hyperliquid/collectors/__init__.py
├── market-scraper/src/market_scraper/connectors/hyperliquid/client.py
├── market-scraper/src/market_scraper/connectors/hyperliquid/parsers.py
├── market-scraper/src/market_scraper/connectors/hyperliquid/config.py
├── market-scraper/src/market_scraper/connectors/hyperliquid/connector.py
├── market-scraper/src/market_scraper/connectors/hyperliquid/__init__.py
├── market-scraper/src/market_scraper/connectors/
├── market-scraper/src/market_scraper/event_bus/
├── market-scraper/src/market_scraper/processors/
├── market-scraper/src/market_scraper/orchestration/
├── market-scraper/src/market_scraper/storage/
├── market-scraper/src/market_scraper/streaming/
├── market-scraper/src/market_scraper/archival/
├── market-scraper/src/market_scraper/config/
├── market-scraper/src/market_scraper/auth/
├── market-scraper/src/market_scraper/binance_account/
├── market-scraper/src/market_scraper/services/
├── market-scraper/src/market_scraper/utils/
├── market-scraper/src/market_scraper/core/
├── market-scraper/src/market_scraper/api/routes/
├── market-scraper/src/market_scraper/api/__init__.py
├── market-scraper/src/market_scraper/api/main.py
├── market-scraper/src/market_scraper/api/models.py
├── market-scraper/src/market_scraper/api/dependencies.py
├── market-scraper/src/market_scraper/__init__.py
├── market-scraper/src/market_scraper/__main__.py
├── market-scraper/src/market_scraper.py
├── market-scraper/src/__init__.py
├── smart-money-signal-system/
├── shared/
├── data-sources/
├── scripts/
├── systemd/market-scraper.service (rewrite)
├── market-scraper/config/ (old config dir)
├── market-scraper/docs/ (old docs dir)
├── market-scraper/tests/ (old tests)
```

**Keep**: `pyproject.toml`, `.pre-commit-config.yaml`, `README.md`, `.env`

---

## Acceptance Criteria

- [ ] `python -m services.leaderboard` runs daily, stores 1000 tracked traders in MongoDB
- [ ] `python main.py` starts position monitor + API server
- [ ] Position monitor cycles through 1000 traders in ~3.3 hours (ascending ROI order)
- [ ] Each trader's position is saved on every WS update (hash dedup skips unchanged)
- [ ] GET /api/v1/traders returns 1000 traders with current positions
- [ ] GET /api/v1/traders/{address} returns detailed trader state
- [ ] GET /api/v1/leaderboard returns stored daily snapshots
- [ ] GET /api/v1/positions/{address}/history returns position history
- [ ] Memory < 100MB, CPU < 20%
- [ ] systemd service restarts cleanly
- [ ] All tests pass (pytest tests/ -v)

---

## Rollback

- Keep `master` at current f3b4ab3
- New work on `fresh-start` branch
- If issues: `git checkout master && systemctl restart market-scraper`