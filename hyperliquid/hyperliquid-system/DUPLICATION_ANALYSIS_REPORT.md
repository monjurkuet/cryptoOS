# Data Collection Duplication Risk Analysis Report

**Date**: February 16, 2026  
**System**: Hyperliquid BTC Trading System  
**Scope**: Data collection architecture and duplication risks

---

## Executive Summary

The system employs a dual-mode data collection strategy:
- **Primary**: Real-time WebSocket collectors for high-frequency data
- **Fallback**: REST API polling via APScheduler when WebSocket is unavailable

**Overall Assessment**: The architecture has **LOW RISK** of data duplication due to proper conditional logic that prevents REST jobs from running when WebSocket is active. However, there are a few areas where deduplication mechanisms could be strengthened.

---

## 1. WebSocket Data Collection (Continuous)

### 1.1 Orderbook Collector (`src/jobs/btc_orderbook_ws.py`)

**Data Collected**:
- Real-time orderbook snapshots with bid/ask levels
- Derived metrics: spread, midPrice, bidDepth, askDepth, imbalance
- Source tag: `"websocket"`

**Collection Frequency**: Event-driven with throttling
- Saves only on significant price changes (>1% threshold, line 48)
- Maximum save interval: 600 seconds (safety net, line 50)
- Keeps latest in memory for instant access

**Key Code References**:
- Lines 45-50: Optimization parameters
- Lines 152-156: Save decision logic
- Line 135: Source field set to "websocket"

**Collection**: `btc_orderbook` (time-series)

### 1.2 Trades Collector (`src/jobs/btc_trades_ws.py`)

**Data Collected**:
- Individual trades with TID, price, size, side, hash
- USD value calculated (px * sz)
- Source tag: `"websocket"`

**Collection Frequency**: Real-time with buffering
- Batch inserts every 5 seconds (line 49)
- Filters trades < $1,000 USD value (line 128)
- TID tracking for deduplication

**Key Code References**:
- Lines 44-45: TID tracking for duplicates
- Lines 80-88: Load last TID from DB on startup
- Lines 119-121: Skip duplicate TIDs
- Line 145: Source field set to "websocket"

**Collection**: `btc_trades` (time-series)

### 1.3 Candles Collector (`src/jobs/btc_candles_ws.py`)

**Data Collected**:
- OHLCV candles for multiple intervals (1m, 5m, 15m, 1h, 4h, 1d)
- Trade count per candle
- Source tag: `"websocket"`

**Collection Frequency**: Real-time per interval
- Batch inserts every 5 seconds (line 47)
- Buffer size: 10 candles per interval (line 46)

**Key Code References**:
- Lines 41-46: Configuration per interval
- Lines 100-115: Candle parsing and document creation
- Line 114: Source field set to "websocket"

**Collection**: `btc_candles` (time-series with metaField: interval)

### 1.4 AllMids Collector (`src/jobs/btc_all_mids_ws.py`)

**Data Collected**:
- Mark prices for all coins
- Price changes and percentages
- Source tag: `"websocket"`

**Collection Frequency**: Real-time with change detection
- Only records when price changes (line 99)
- Batch inserts every 10 seconds (line 49)
- Buffer size: 50 price updates (line 48)

**Key Code References**:
- Lines 44-45: Previous price tracking
- Lines 99-114: Change detection and document creation
- Line 110: Source field set to "websocket"

**Collection**: `all_mids` (time-series)

### 1.5 Trader Positions Collector (`src/api/persistent_trader_ws.py`)

**Data Collected**:
- Trader position snapshots
- BTC-only filtering (configurable)
- Margin summary
- Source tag: `"websocket"`

**Collection Frequency**: Event-driven with safety interval
- Only saves on position changes (line 259)
- Max interval: 600 seconds (line 67)
- Flush interval: 5 seconds (line 172)
- BTC-only positions (line 249-256)

**Key Code References**:
- Lines 64-68: Configuration parameters
- Lines 175-191: Position normalization for comparison
- Lines 193-213: Change detection logic
- Line 269: Source field set to "websocket"

**Collections**: 
- `trader_positions` (time-series) - historical snapshots
- `trader_current_state` (regular) - current state (upsert)

---

## 2. Scheduler Data Collection (Periodic)

The scheduler (`src/jobs/scheduler.py`) manages APScheduler with conditional job registration based on `ws_available` flag.

### 2.1 Conditional Job Registration (Lines 73-124)

**Jobs SKIPPED when WebSocket is available**:

| Job | REST Function | WebSocket Equivalent | Interval |
|-----|--------------|---------------------|----------|
| Orderbook | `collect_orderbook` | `OrderbookWebSocketCollector` | 30s |
| Trades | `collect_trades` | `TradesWebSocketCollector` | 60s |
| Candles | `collect_candles` | `CandleWebSocketCollector` | 300s |

**Jobs ALWAYS running** (no WebSocket equivalent):

| Job | Function | Interval | Collection |
|-----|----------|----------|------------|
| Ticker | `update_ticker` | 60s | `btc_ticker` |
| Trader Orders | `collect_trader_orders` | 300s | `trader_orders` |
| Funding | `collect_funding` | 28800s (8h) | `btc_funding_history` |
| Signals | `generate_signals` | 300s | `btc_signals` |
| Leaderboard | `fetch_leaderboard` | 86400s (daily) | `tracked_traders` |
| Daily Stats | `collect_daily_stats` | 86400s (daily) | `btc_open_interest`, etc. |
| Archive | `archive_all_collections` | 86400s (daily) | N/A |

### 2.2 Startup Tasks (Lines 198-242)

**Always executed on startup**:
1. `update_ticker` - Initial ticker fetch
2. `collect_candles` - Backfill recent candles (last 24 hours)
3. `fetch_leaderboard` - Initial leaderboard and trader setup

**Note**: Candles backfill runs regardless of WebSocket status, which could cause duplicates if not handled properly.

---

## 3. Duplication Risk Analysis

### 3.1 Risk Assessment Matrix

| Collection | WebSocket | REST Scheduler | Risk Level | Notes |
|-----------|-----------|----------------|------------|-------|
| `btc_orderbook` | ✅ Yes | ❌ Conditional* | **LOW** | REST skipped when WS active |
| `btc_trades` | ✅ Yes | ❌ Conditional* | **LOW** | REST skipped when WS active |
| `btc_candles` | ✅ Yes | ❌ Conditional* | **MEDIUM** | REST skipped, but startup backfill risk |
| `trader_positions` | ✅ Yes | ❌ Skipped | **LOW** | REST job removed (line 98) |
| `all_mids` | ✅ Yes | ❌ None | **NONE** | No REST equivalent |
| `btc_ticker` | ❌ No | ✅ Always | **NONE** | Only REST |
| `trader_orders` | ❌ No | ✅ Always | **NONE** | Only REST |
| `btc_funding` | ❌ No | ✅ Always | **NONE** | Only REST |

*REST jobs skipped when `ws_available=True` (lines 73-94, 114-124)

### 3.2 Identified Risk Areas

#### Risk 1: Candles Backfill Duplication (MEDIUM)

**Location**: `src/jobs/scheduler.py` lines 228-229

```python
# Initial candles (last 24 hours for each interval)
logger.info("Backfilling recent candles...")
await collect_candles(hl_client, db)  # Runs regardless of ws_available
```

**Issue**: Startup backfill always runs, even when WebSocket candles collector is active. If WebSocket candles are already collecting real-time data, the REST backfill could insert duplicate candle data.

**Impact**: Duplicate candles for the last 24 hours at startup.

#### Risk 2: Ticker Data (LOW)

**Location**: `src/jobs/btc_ticker.py`

**Issue**: No WebSocket collector for ticker data. The `update_ticker` job runs every 60 seconds via REST, but there's no real-time ticker stream via WebSocket.

**Impact**: None - this is by design, no duplication possible.

#### Risk 3: Trader Orders (LOW)

**Location**: `src/jobs/trader_orders.py`

**Issue**: No WebSocket collector for trader orders (different from positions). The `collect_trader_orders` job runs every 5 minutes via REST.

**Impact**: None - this is by design, no duplication possible.

#### Risk 4: Source Field Inconsistency (LOW)

**Issue**: Some REST jobs may not set the `source` field, making it difficult to identify data origin.

**Affected Collections**:
- `btc_ticker` - No source field (uses `_id: "btc_ticker"` with upsert)
- `btc_funding_history` - No source field check in code
- `trader_orders` - REST-based, source field not verified

### 3.3 No Risk Areas (Properly Handled)

#### Orderbook (Lines 73-94)
```python
if not ws_available:
    # Orderbook - REST fallback
    scheduler.add_job(...)
else:
    logger.info("WebSocket orderbook/trades active - skipping REST jobs")
```

#### Trades (Lines 85-94)
Same conditional logic as orderbook - properly skipped when WebSocket active.

#### Trader Positions (Line 98)
```python
logger.info("Trader positions handled by PersistentTraderWebSocketManager")
```
REST job completely removed - no duplication possible.

---

## 4. Current Deduplication Mechanisms

### 4.1 MongoDB Indexes

**Time-Series Collections** (`src/database.py` lines 38-74, `src/models/base.py` lines 101-135):

MongoDB time-series collections do NOT support unique indexes. Deduplication relies on application-level logic.

| Collection | Index Type | Fields | Unique | Purpose |
|-----------|-----------|--------|--------|---------|
| `btc_candles` | Compound | `(t, interval)` | No | Time-based queries |
| `btc_candles` | Compound | `(interval, t)` | No | Interval-based queries |
| `btc_orderbook` | Single | `(t)` | No | Time sorting |
| `btc_trades` | Single | `(tid)` | No | TID lookup |
| `btc_trades` | Single | `(t)` | No | Time sorting |
| `trader_positions` | Compound | `(ethAddress, t)` | No | Trader history |
| `trader_orders` | Compound | `(ethAddress, oid)` | No | Order deduplication |
| `all_mids` | Compound | `(coin, t)` | No | Price history |

**Regular Collections** (`src/models/base.py` lines 138-159):

| Collection | Index Type | Fields | Unique | Purpose |
|-----------|-----------|--------|--------|---------|
| `btc_funding_history` | Single | `(t)` | **Yes** | Prevent duplicate funding |
| `btc_open_interest` | Single | `(date)` | **Yes** | One entry per day |
| `btc_liquidity` | Single | `(date)` | **Yes** | One entry per day |
| `btc_liquidations` | Single | `(date)` | **Yes** | One entry per day |
| `tracked_traders` | Single | `(ethAddress)` | **Yes** | Unique traders |
| `trader_current_state` | Single | `(ethAddress)` | **Yes** | Current state per trader |

### 4.2 TID-Based Deduplication (Trades)

**Location**: `src/jobs/btc_trades_ws.py` lines 44-45, 80-88, 119-121

```python
# Track last trade ID to avoid duplicates
self._last_tid: int = 0

async def _load_last_tid(self) -> None:
    """Load the last trade ID from database."""
    last_trade = await self.collection.find_one(sort=[("tid", -1)])
    if last_trade:
        self._last_tid = last_trade.get("tid", 0)

# In handler:
if tid <= self._last_tid:
    continue  # Skip duplicates
```

**Effectiveness**: HIGH - Prevents duplicate trades by tracking the highest TID.

### 4.3 Time-Based Deduplication (Candles)

**Location**: `src/jobs/btc_candles.py` lines 72-93

```python
# Get the last candle timestamp for this interval
last_candle = await collection.find_one(
    {"interval": interval},
    sort=[("t", -1)],
)

# Calculate start time
if last_candle:
    last_time = last_candle["t"]
    start_time = datetime_to_timestamp(last_time) + _get_interval_ms(interval)
```

**Effectiveness**: MEDIUM - Fetches candles starting from `last_candle_time + interval`, which should prevent exact duplicates but may miss candles in the same interval.

### 4.4 Exception-Based Deduplication

**Location**: Multiple files use `insert_many` with error handling

```python
try:
    await collection.insert_many(documents, ordered=False)
except Exception as e:
    if "duplicate key error" not in str(e).lower():
        raise
```

**Files**:
- `src/jobs/btc_trades.py` lines 74-78
- `src/jobs/btc_candles.py` lines 115-121
- `src/jobs/btc_trades_ws.py` lines 185-193
- `src/jobs/btc_candles_ws.py` lines 150-158

**Effectiveness**: MEDIUM - Catches MongoDB duplicate key errors silently. However, this only works if unique indexes exist (which they don't for time-series collections).

### 4.5 Event-Driven Deduplication (Positions)

**Location**: `src/api/persistent_trader_ws.py` lines 175-213

```python
def _normalize_positions(self, positions: List[Dict]) -> str:
    """Normalize positions for comparison."""
    sorted_positions = sorted(positions, key=lambda x: x.get("position", {}).get("coin", ""))
    parts = []
    for pos in sorted_positions:
        coin = pos.get("position", {}).get("coin", "")
        szi = float(pos.get("position", {}).get("szi", 0))
        leverage = pos.get("position", {}).get("leverage", {}).get("value", 0)
        parts.append(f"{coin}:{szi:.8f}:{leverage}")
    return "|".join(parts)

def _has_significant_change(self, address: str, new_positions: List[Dict]) -> bool:
    last_normalized = last_saved.get("normalized", "")
    current_normalized = self._normalize_positions(new_positions)
    if last_normalized != current_normalized:
        return True
    return False
```

**Effectiveness**: HIGH - Only saves when positions actually change, significantly reducing duplicate snapshots.

### 4.6 Price Change Threshold (Orderbook)

**Location**: `src/jobs/btc_orderbook_ws.py` lines 145-156

```python
price_change_pct = abs(mid_price - self._last_mid_price) / self._last_mid_price

should_save = (
    price_change_pct >= self._price_change_threshold
    or time_since_last_save >= self._max_save_interval
)
```

**Effectiveness**: HIGH - Only saves on >1% price changes or 600s max interval.

---

## 5. Recommendations

### 5.1 HIGH PRIORITY: Fix Candles Startup Backfill

**Issue**: Startup backfill always runs regardless of WebSocket status.

**Recommendation**: Skip candles backfill when WebSocket is active, or implement time-range deduplication.

**Implementation** (`src/jobs/scheduler.py` lines 227-229):

```python
# Current:
logger.info("Backfilling recent candles...")
await collect_candles(hl_client, db)

# Recommended:
if not ws_available:
    logger.info("Backfilling recent candles...")
    await collect_candles(hl_client, db)
else:
    logger.info("WebSocket candles active - skipping REST backfill")
```

### 5.2 MEDIUM PRIORITY: Add Unique Index on Trades TID

**Issue**: Time-series collections don't support unique indexes, but `btc_trades` has a TID field that should be unique.

**Recommendation**: Consider migrating `btc_trades` to a regular collection with a unique index on `tid`, or implement stronger application-level deduplication.

**Note**: This is a breaking change that would require data migration.

### 5.3 MEDIUM PRIORITY: Consistent Source Field

**Issue**: Not all collections have a `source` field to track data origin.

**Recommendation**: Add `source` field to all collections:
- `btc_ticker` - Add `"source": "rest"`
- `btc_funding_history` - Add `"source": "rest"`
- `trader_orders` - Verify and add if missing

This helps with debugging and data lineage tracking.

### 5.4 LOW PRIORITY: Candles Deduplication Query

**Issue**: Candle deduplication relies on `last_candle_time + interval`, which may not be precise.

**Recommendation**: Add pre-insert check to skip candles that already exist:

```python
# In src/jobs/btc_candles.py, before insert_many:
existing_candle = await collection.find_one({
    "interval": interval,
    "t": doc["t"]
})
if not existing_candle:
    documents.append(doc)
```

### 5.5 LOW PRIORITY: Add WebSocket Ticker Collector

**Issue**: No real-time ticker updates via WebSocket.

**Recommendation**: Consider subscribing to `allMids` or `trades` WebSocket feeds to calculate real-time ticker metrics, reducing reliance on REST polling.

**Alternative**: The `allMids` WebSocket collector already captures mark prices, which could be used to update ticker data more frequently.

### 5.6 LOW PRIORITY: Enhanced Monitoring

**Recommendation**: Add metrics/alerting for:
- Duplicate detection events (log when duplicates are caught)
- WebSocket vs REST data volume comparison
- Source field distribution queries

Example query to detect duplicates:
```javascript
db.btc_candles.aggregate([
  { $group: { _id: { t: "$t", interval: "$interval" }, count: { $sum: 1 } } },
  { $match: { count: { $gt: 1 } } }
])
```

---

## 6. Summary

### Current State

✅ **Strengths**:
1. Proper conditional job registration based on WebSocket availability
2. TID tracking for trade deduplication
3. Event-driven position collection with change detection
4. Price change thresholds for orderbook optimization
5. Unique indexes on regular collections (funding, OI, liquidations)

⚠️ **Weaknesses**:
1. Candles startup backfill runs regardless of WebSocket status
2. No unique constraints on time-series collections (MongoDB limitation)
3. Inconsistent `source` field usage across collections

### Risk Summary

| Risk Level | Count | Description |
|-----------|-------|-------------|
| **HIGH** | 0 | No high-risk duplication scenarios |
| **MEDIUM** | 1 | Candles startup backfill could duplicate WebSocket data |
| **LOW** | 2 | Missing source fields, TID not indexed as unique |
| **NONE** | 5 | Properly handled with no duplication risk |

### Recommended Actions (Priority Order)

1. **Fix candles startup backfill** (30 min) - Add `ws_available` check
2. **Add source fields** (1 hour) - Update REST collectors to set source="rest"
3. **Monitor duplicate rates** (ongoing) - Add queries to detect duplicates
4. **Consider unique TID index** (2-4 hours) - Requires data migration
5. **Add real-time ticker** (future enhancement) - Use allMids WebSocket data

---

## Appendix A: Code References

### Scheduler Conditional Logic
- **File**: `src/jobs/scheduler.py`
- **Lines**: 73-94 (orderbook/trades), 114-124 (candles)
- **Function**: `add_jobs()`

### WebSocket Collectors
- **Orderbook**: `src/jobs/btc_orderbook_ws.py`, lines 1-235
- **Trades**: `src/jobs/btc_trades_ws.py`, lines 1-237
- **Candles**: `src/jobs/btc_candles_ws.py`, lines 1-184
- **AllMids**: `src/jobs/btc_all_mids_ws.py`, lines 1-191
- **Positions**: `src/api/persistent_trader_ws.py`, lines 1-470

### REST Fallbacks
- **Orderbook**: `src/jobs/btc_orderbook.py`, lines 17-94
- **Trades**: `src/jobs/btc_trades.py`, lines 17-90
- **Candles**: `src/jobs/btc_candles.py`, lines 19-54

### Database Setup
- **File**: `src/database.py`
- **Lines**: 34-100 (time-series), 103-130 (regular)
- **Function**: `setup_database()`

### Index Definitions
- **File**: `src/models/base.py`
- **Lines**: 101-135 (time-series), 138-159 (regular)

---

## Appendix B: Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Data Sources                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  WebSocket   │  │  REST API    │  │   Startup    │      │
│  │  (Primary)   │  │  (Fallback)  │  │   Backfill   │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼────────────────┼────────────────┼──────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Collection Logic                          │
│                                                              │
│  IF ws_available=True:                                       │
│    ├─> Start WebSocket collectors                            │
│    ├─> Skip REST orderbook/trades/candles jobs               │
│    └─> Run REST ticker/funding/orders (always)               │
│                                                              │
│  IF ws_available=False:                                      │
│    ├─> Start REST orderbook/trades/candles jobs              │
│    └─> Run all REST jobs                                     │
│                                                              │
│  ALWAYS (startup):                                           │
│    ├─> Backfill candles (⚠️ POTENTIAL DUPLICATE)             │
│    ├─> Fetch leaderboard                                     │
│    └─> Update ticker                                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      MongoDB Collections                     │
│  Time-Series:        Regular:                                │
│  ├─ btc_candles      ├─ btc_ticker                           │
│  ├─ btc_orderbook    ├─ btc_funding_history (unique: t)     │
│  ├─ btc_trades       ├─ btc_open_interest (unique: date)    │
│  ├─ trader_positions ├─ tracked_traders (unique: ethAddress)│
│  ├─ trader_orders    └─ trader_current_state                │
│  ├─ all_mids                                                │
│  └─ btc_signals                                             │
└─────────────────────────────────────────────────────────────┘
```

---

*Report generated: February 16, 2026*  
*System Version: Hyperliquid BTC Trading System*
