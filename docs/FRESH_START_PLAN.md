# cryptoOS Fresh-Start Implementation Plan

**Goal**: Replace market-scraper trader tracking with a lean daily-leaderboard → serial WebSocket architecture.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        DAILY CRON (00:00 UTC)                   │
├─────────────────────────────────────────────────────────────────┤
│  1. Fetch full 39K leaderboard from Hyperliquid Stats API      │
│  2. Score all traders (configurable weights)                   │
│  3. Filter: ROI all_time > 0 AND ROI this_year > 0             │
│     AND ROI this_month > 0                                     │
│  4. Sort by score desc, take top 200                           │
│  5. Store to `leaderboard_daily` collection (date-partitioned) │
│  6. Store top 200 to `tracked_traders` collection (active set) │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SERIAL WEBSOCKET WORKER                      │
├─────────────────────────────────────────────────────────────────┤
│  Loop forever:                                                  │
│    For each batch of 5 traders (from tracked_traders):         │
│      1. Connect 1 WebSocket to wss://api.hyperliquid.xyz/ws    │
│      2. Subscribe webData2 for 5 traders                       │
│      3. Listen for 60 seconds                                  │
│      4. On each message: normalize, hash, dedup, store to      │
│         `trader_positions` (time-series) + update              │
│         `trader_current_state` (upsert)                        │
│      5. Unsubscribe, close WS cleanly                          │
│      6. Next batch                                              │
│    Repeat from start (cycles ~40 min for 200 traders @ 5/batch) │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Core Infrastructure (New Files)

### 1.1 `market-scraper/src/market_scraper/core/settings.py`
- Single Pydantic Settings class (no nested config classes)
- All env vars with `env_nested_delimiter="__"`
- Fields: `mongo_url`, `mongo_db`, `redis_url`, `hyperliquid_symbol`, `api_host`, `api_port`, `log_level`

### 1.2 `market-scraper/src/market_scraper/db/mongo.py`
- `async def get_mongo() -> AsyncIOMotorDatabase`
- Connection pooling: max 10, min 1
- Collection get_mongo
- Single shared Motor client

### 1.3 `market-scraper/src/market_scraper/db/redis.py`
- `async def get_redis() -> redis.asyncio.Redis`
- Connection pool max 10

### 1.4 `market-scraper/src/market_scraper/models/leaderboard.py`
```python
class LeaderboardRow(BaseModel):
    eth: str
    name: str | None
    acct_val: float
    roi_all_time: float
    roi_year: float
    roi_month: float
    roi_week: float
    roi_day: float
    volume_month: float
    pnl_all_time: float
    score: float
    tags: list[str] = []
    rank: int = 0
    fetched_at: datetime

class DailyLeaderboard(BaseModel):
    date: date  # partition key
    rows: list[LeaderboardRow]
    total_fetched: int
    created_at: datetime
```

### 1.5 `market-scraper/src/market_scraper/models/tracked.py`
```python
class TrackedTrader(BaseModel):
    eth: str
    name: str | None
    acct_val: float
    score: float
    tags: list[str]
    leaderboard_rank: int
    selected_at: datetime
    # Position state (updated by WS worker)
    last_position_update: datetime | None = None
    current_positions: list[Position] = []
    current_open_orders: list[Order] = []
    margin_summary: dict = {}
```

### 1.6 `market-scraper/src/market_scraper/models/position.py`
```python
class Position(BaseModel):
    eth: str
    symbol: str
    size: float
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: float
    liquidation_price: float | None
    timestamp: datetime
```

### 1.7 `market-scraper/src/market_scraper/models/events.py`
- StandardEvent (from existing codebase — keep)

---

## Phase 2: Daily Leaderboard Fetch (New Module)

### 2.1 `market-scraper/src/market_scraper/services/leaderboard_fetch.py`

```python
class LeaderboardFetchService:
    """Fetches, scores, filters, and stores daily leaderboard."""
    
    async def fetch_and_store(self) -> DailyLeaderboard:
        # 1. GET https://stats-data.hyperliquid.xyz/Mainnet/leaderboard
        # 2. Parse windowPerformances → roi_all_time, roi_year, roi_month, roi_week, roi_day
        # 3. Score: 30% all_time, 25% month, 20% week, 15% acct_val, 10% volume
        #    (configurable via market_config.yaml)
        # 4. Filter: roi_all_time > 0 AND roi_year > 0 AND roi_month > 0
        # 5. Sort by score desc, take top 200
        # 6. Generate tags: whale, consistent, high_performer, etc.
        # 7. Upsert to leaderboard_daily (date=today)
        # 8. Upsert top 200 to tracked_traders (replace all)
        # 9. Return DailyLeaderboard
```

### 2.2 Scoring Logic (configurable)
```yaml
# market_config.yaml
scoring:
  weights:
    roi_all_time: 30
    roi_month: 25
    roi_week: 20
    account_value: 15
    volume_month: 10
  multipliers:
    roi_all_time: 30    # max points
    roi_month: 50
    roi_week: 100
  account_value_tiers: [...]
  volume_tiers: [...]
filters:
  require_positive_all_time: true
  require_positive_year: true
  require_positive_month: true
  max_tracked: 200
```

### 2.3 Cron Job
- Runs daily at 00:00 UTC (or configurable)
- Single async function, no daemon
- Logs: fetched_count, scored_count, filtered_count, stored_count
- Idempotent: safe to re-run same day

---

## Phase 3: Serial WebSocket Worker (New Module)

### 3.1 `market-scraper/src/market_scraper/services/ws_worker.py`

```python
class SerialWSWorker:
    """Single WebSocket, 5 traders at a time, 60s dwell."""
    
    BATCH_SIZE = 5
    DWELL_SECONDS = 60
    WS_URL = "wss://api.hyperliquid.xyz/ws"
    
    async def run_forever(self):
        while True:
            tracked = await self.get_tracked_traders()  # from tracked_traders collection
            if not tracked:
                await asyncio.sleep(300)
                continue
            
            for batch in self.chunk(tracked, self.BATCH_SIZE):
                await self.process_batch(batch)
                if not self._running:
                    return
    
    async def process_batch(self, traders: list[TrackedTrader]):
        addresses = [t.eth for t in traders]
        
        # Connect
        ws = await websockets.connect(self.WS_URL, ping_interval=30, ping_timeout=10)
        
        # Subscribe all 5
        for addr in addresses:
            await ws.send(json.dumps({
                "method": "subscribe",
                "subscription": {"type": "webData2", "user": addr}
            }))
            await asyncio.sleep(0.05)  # stagger
        
        # Listen for DWELL_SECONDS
        end_time = time.monotonic() + self.DWELL_SECONDS
        while time.monotonic() < end_time:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                await self.handle_message(msg, addresses)
            except asyncio.TimeoutError:
                continue
            except websockets.ConnectionClosed:
                break
        
        # Clean unsubscribe
        for addr in addresses:
            try:
                await ws.send(json.dumps({
                    "method": "unsubscribe",
                    "subscription": {"type": "webData2", "user": addr}
                }))
            except Exception:
                pass
        
        await ws.close()
    
    async def handle_message(self, msg: str, addresses: list[str]):
        data = json.loads(msg)
        if data.get("channel") != "webData2":
            return
        
        # Extract + normalize
        extracted = self.extract_webdata2(data["data"])
        if not extracted:
            return
        
        eth, positions, orders, margin = extracted
        
        # Hash dedup
        norm = self.normalize(positions, orders, margin)
        h = sha256(norm.encode()).hexdigest()
        last = await self.get_last_hash(eth)
        if last == h:
            return  # no change
        
        # Store
        await self.store_position(Position(
            eth=eth,
            symbol=self.symbol,
            size=positions[0].size if positions else 0,
            ...
        ))
        await self.upsert_current_state(eth, positions, orders, margin, h)
```

### 3.2 Key Differences from Old Code
| Old | New |
|-----|-----|
| 5 parallel WS clients | **1 WS client, serial batches** |
| Complex reconnect with stagger | **Simple: connect → listen 60s → close → next** |
| Bounded queues + 6 workers | **Direct processing in listen loop** |
| Quick hash + thread pool | **Inline normalization (5 traders = trivial CPU)** |
| `get_capacity()` rotation logic | **Just iterate tracked_traders in order** |
| TTL cleanup in flush | **No TTL — tracked_traders replaced daily** |

### 3.3 Resilience
- WS connection failure → log, wait 5s, retry same batch
- Partial subscription failure → continue with successful ones
- MongoDB write failure → log, continue (don't block WS loop)
- Process cancellation (SIGTERM) → close WS cleanly, exit

---

## Phase 4: API Layer (Minimal — Keep Working Endpoints)

### 4.1 `market-scraper/src/market_scraper/api/main.py`
- FastAPI app with lifespan
- Mount only necessary routers:
  - `health` (keep all)
  - `markets` (keep — candles from CollectorManager)
  - `traders` (simplify — read from `tracked_traders` + `trader_current_state`)
  - `signals` (keep — generated by signal-system)
  - `leaderboard_raw` (keep — query `leaderboard_daily`)
  - `onchain` / `cbbi` (keep)
  - `websocket` (keep — streams from event bus)

### 4.2 `traders.py` Simplification
- Remove 30+ filter params
- Only: `limit`, `offset`, `min_score`, `has_positions`, `sort_by`
- Read from `tracked_traders` (joined with `trader_current_state`)
- No 4s timeout, no caching needed (small dataset: 200)

### 4.3 `leaderboard_raw.py` Simplification
- Query `leaderboard_daily` by date
- Filters: score, acct_val, roi_*, volume
- No `fetch_time` parameter (daily partition = implicit)

---

## Phase 5: Event Bus (Keep Redis for External Consumers)

### 5.1 `market-scraper/src/market_scraper/event_bus/redis_bus.py`
- Keep **local dispatch** for `trader_positions` (high volume)
- Redis publish only for external consumers (WebSocket server, signal-system)
- Simplify: no reconnection manager (systemd restarts on crash)

### 5.2 Events Published
| Event | Source | local_only |
|-------|--------|------------|
| `trader_positions` | WS worker | True |
| `ohlcv` | CollectorManager | False |
| `leaderboard` | LeaderboardFetchService (after daily run) | False |
| `signals` | SignalGenerationProcessor | False |

---

## Phase 6: CollectorManager (Keep for Candles Only)

### 6.1 `market-scraper/src/market_scraper/connectors/hyperliquid/collectors/manager.py`
- **Only** `CandlesCollector` (1m, 5m, 15m, 1h, 4h, 1d)
- Remove `LeaderboardCollector`, `TraderWebSocketCollector`
- Single WS for market data, separate from trader WS worker

---

## Phase 7: Lifecycle (Simplified)

### 7.1 `market-scraper/src/market_scraper/orchestration/lifecycle.py`
```python
class LifecycleManager:
    async def startup():
        1. Connect MongoDB
        2. Connect Redis → EventBus
        3. Start CollectorManager (candles only)
        4. Subscribe storage handlers
        5. Start SignalGenerationProcessor
        6. Start SerialWSWorker (background task)
        7. Start FastAPI
    
    async def shutdown():
        1. Stop WS worker
        2. Stop CollectorManager
        3. Close EventBus
        4. Close MongoDB
```

---

## Phase 8: Configuration

### 8.1 `market-scraper/config/market_config.yaml` (New — Minimal)
```yaml
# Daily leaderboard
leaderboard:
  fetch_time_utc: "00:00"
  scoring:
    weights:
      roi_all_time: 30
      roi_month: 25
      roi_week: 20
      account_value: 15
      volume_month: 10
    multipliers:
      roi_all_time: 30
      roi_month: 50
      roi_week: 100
  filters:
    require_positive: [all_time, year, month]
    max_tracked: 200

# Serial WS worker
trader_ws:
  batch_size: 5
  dwell_seconds: 60
  ws_url: "wss://api.hyperliquid.xyz/ws"

# Collector (candles only)
collector:
  symbol: "BTC"
  intervals: ["1m", "5m", "15m", "1h", "4h", "1d"]
```

---

## Phase 9: Tests to Keep / Add

| Test | Purpose |
|------|---------|
| `test_leaderboard_fetch.py` | Score + filter logic |
| `test_ws_worker.py` | Batch processing, hash dedup, storage |
| `test_traders_api.py` | Simplified trader list endpoint |
| `test_leaderboard_raw_api.py` | Daily query endpoint |

---

## Phase 10: Migration Steps

1. **Create new branch** `fresh-start`
2. **Add new files** (Phase 1-3) alongside old code
3. **Write tests** for new modules
4. **Run daily fetch manually** → verify `leaderboard_daily` + `tracked_traders`
5. **Run WS worker manually** → verify `trader_positions` + `trader_current_state`
6. **Swap API routes** to read new collections
7. **Remove old collectors** (`trader_ws.py`, `leaderboard.py`)
8. **Remove old processors** (`position_inference.py`, `trader_scoring.py`)
9. **Simplify lifecycle**
10. **Delete archival, smart-money-signal-system from workspace**
11. **Update systemd service** (same command, new code)
12. **Deploy, monitor 24h**

---

## Resource Estimates

| Component | Old | New |
|-----------|-----|-----|
| WS Connections | 5 parallel (50 traders) | 1 serial (5 traders) |
| Memory (trader tracking) | 5000 tracked | 200 tracked |
| MongoDB writes/sec | ~100 (buffered) | ~5 (5 traders × 60s) |
| Event loop lag | Frequent spikes | Minimal (single client) |
| CPU (normalization) | Thread pool (4 workers) | Inline (trivial) |
| Daily leaderboard fetch | Every hour | Once/day |
| Code size (trader_ws) | 1793 lines | ~300 lines |

---

## Acceptance Criteria

- [ ] Daily cron runs at 00:00 UTC, stores leaderboard_daily + tracked_traders (200)
- [ ] WS worker cycles through all 200 in ~40 min (200/5 × 60s + overhead)
- [ ] Position updates stored to trader_positions (time-series) + trader_current_state (upsert)
- [ ] API `/traders` returns 200 traders with current positions
- [ ] API `/leaderboard/query` works against daily partition
- [ ] Candles still collected via CollectorManager
- [ ] Signals still generated by signal-system (Redis events)
- [ ] Memory < 300MB, CPU < 30%, no event loop lag > 500ms
- [ ] All 21 existing trader_ws tests pass (adapted to new code)
- [ ] Systemd service restarts cleanly, WatchdogSec=300 never fires

---

## Files to Delete After Migration

```
market-scraper/src/market_scraper/connectors/hyperliquid/collectors/trader_ws.py
market-scraper/src/market_scraper/connectors/hyperliquid/collectors/leaderboard.py
market-scraper/src/market_scraper/processors/position_inference.py
market-scraper/src/market_scraper/processors/trader_scoring.py
market-scraper/src/market_scraper/processors/signal_generation.py
market-scraper/src/market_scraper/archival/
market-scraper/tests/unit/connectors/test_leaderboard.py
market-scraper/tests/unit/processors/test_position_inference.py
market-scraper/tests/unit/processors/test_trader_scoring.py
market-scraper/tests/unit/processors/test_signal_generation.py
smart-money-signal-system/  (entire - move to separate repo if needed)
```

---

## Rollback Plan

- Keep `master` branch at current f3b4ab3
- New work on `fresh-start` branch
- If issues: `git checkout master && systemctl restart market-scraper`