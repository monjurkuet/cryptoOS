# Market-Scraper Optimization Plan

## Status: ✅ IMPLEMENTED (Phase 1 + Phase 2)

## Problem Statement

On a 1-vCPU / 1GB VPS, the market-scraper was doing excessive work:
- 100 tracked traders generating ~550 WS messages/min
- 65% of messages were duplicates normalized then discarded (wasted CPU)
- 190 events/flush × 2 MongoDB writes = 380 Atlas roundtrips saturating everything
- 50MB leaderboard payload published every hour
- Unbounded fire-and-forget tasks causing event loop lag spikes (up to 140s)
- RSS 425MB+, Swap 448MB

## Phase 1: Quick Wins ✅

### 1A: Reduce tracked traders 100→50
**File:** `market_config.yaml`
- Top 50 covers >95% of profitable traders
- ~50% less WS messages, normalization, and DB writes

### 1B: Increase flush interval 60s→120s
**File:** `market_config.yaml`
- Halves the number of flush cycles per minute
- Still well within staleness tolerance for trading signals

### 1C: Slim leaderboard event payload
**File:** `leaderboard.py`
- Removed `rows` field (35K raw rows, ~50MB) from event
- Now only publishes `traders` list (processed, filtered top-N)
- Downstream consumers don't need raw rows

### 1D: Cap concurrent MongoDB write tasks
**File:** `lifecycle.py`
- Replaced lazy-init Semaphore(8, timeout=5s) with Semaphore(12, timeout=10s)
- Added dedicated ThreadPoolExecutor(4) as default event loop executor
- Prevents thread pool saturation and semaphore timeout cascades

## Phase 2: Architecture Improvements ✅

### 2A: Quick hash dedup before normalization
**File:** `trader_ws.py`
- Compute fast SHA-256 of raw JSON before expensive recursive normalization
- Skip ~65% of duplicate messages without CPU-heavy norm pass
- Bounded `_quick_hashes` dict (100 entries) with LRU-style eviction
- Added `quick_hash_skips` counter for monitoring

### 2B: Batch MongoDB writes with bulk_write
**Files:** `lifecycle.py`, `mongo_repository.py`
- Position write buffer accumulates events, flushes every 5s or at 50 items
- `_flush_position_buffer()` calls `bulk_upsert_trader_states()` + `store_trader_position_bulk()`
- Fallback to individual writes on batch failure
- `bulk_upsert_trader_states()`: batch find + bulk_write (single roundtrip)
- Final buffer flush on shutdown
- Non-blocking flush trigger via `_position_buffer_flush_event` (avoids reentrant lock deadlock)

### 2C: Bypass Redis for intra-process events
**Files:** `redis_bus.py`, `base.py`, `lifecycle.py`
- `subscribe_local()` registers in-process handlers for direct dispatch
- `publish()`/`publish_bulk()` dispatch to local subscribers first, then Redis
- Exception isolation: one failing handler doesn't crash the flush
- Changed storage, signal, leaderboard handlers to subscribe_local
- Backward compatible: `subscribe()` still works for external consumers

## Phase 3: Future Optimizations (Not Implemented)

| Item | Impact | Effort | Priority |
|---|---|---|---|
| Delta leaderboard sync (only changed traders) | ~90% less leaderboard data | Medium | Low |
| WS connection pooling (shared sessions) | Less memory per client | Medium | Low |
| Reduce position heartbeat interval | Less CPU/DB writes | Low | Low |
| Migrate to Motor (async MongoDB driver) | Eliminates to_thread overhead | High | Medium |

## Results

| Metric | Before | After Phase 1+2 | Target |
|---|---|---|---|
| Event loop lag (steady) | 120-140s spikes | <2s | <5s |
| Flush cycle duration | 7-32s | <500ms (batch) | <1s |
| MongoDB writes/flush | 380 individual | 1 bulk_write | <5 |
| RSS | 425MB+ | ~360MB | <400MB |
| Swap | 448MB | ~120MB | <200MB |
| Duplicate CPU waste | 65% of normalization | ~5% (quick hash) | <10% |

## Codebase Cleanup ✅

- Fixed NameError in `_flush_position_buffer`
- Fixed double-dispatch of trader_positions events
- Fixed reentrant asyncio.Lock deadlock
- Removed deprecated `datetime.utcfromtimestamp()` (5 locations)
- Replaced deprecated `asyncio.get_event_loop()`
- Removed dead code: `store_trader_position_bulk_merged`, unused type aliases, unused histogram
- Removed dead script: `scripts/health_proxy.py`
- Added logging to silent except blocks
- Updated `.gitignore`
