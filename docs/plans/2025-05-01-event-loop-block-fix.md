# Event Loop Block Fix Plan — market-scraper

> **Root Cause Chain:** 60s buffer accumulates thousands of WS messages → flush processes all synchronously (CPU-bound JSON normalization ×6 per event) → publishes all events → storage handler makes 27K+ sequential MongoDB writes → event loop blocked for seconds → WebSocket pings time out → disconnects

## 1. Diagnosis — Confirm the Root Cause

### 1.1 Add timing instrumentation
- **File:** `src/market_scraper/core/trader_ws.py`
  - Add `time.monotonic()` around `_flush_messages()` (line 617) — log total flush duration
  - Add timing around `publish_bulk()` call (line 655) — log event publish duration
- **File:** `src/market_scraper/orchestration/lifecycle.py`
  - Add `time.monotonic()` around `_store_trader_positions_state()` (line 343+) — log storage duration per event
  - Log count of individual `store_trader_position` calls per flush cycle

### 1.2 Add memory profiling
- Add `tracemalloc` snapshots before/after flush to measure allocation per cycle
- Log `len(self._message_buffer)` and event count at flush start

### 1.3 Add event loop lag detector
- Create `asyncio.create_task(monitor_loop_lag())` that measures `loop.time()` drift
- Log warning if lag exceeds 500ms, critical if >2s

---

## 2. Quick Wins — Immediate Mitigations (no architecture change)

### 2.1 Reduce WebSocket message throughput
- **File:** `src/market_scraper/core/trader_ws.py` line 73
- Reduce `_num_clients` from 5 to 2 — halves incoming message rate
- **Already done:** `max_traders=200` config limit

### 2.2 More frequent event loop yields
- **File:** `src/market_scraper/core/trader_ws.py` line 641
- Change `yield` every 10 messages → every 5 messages
- Change from simple `yield` to `await asyncio.sleep(0)` for explicit yield

### 2.3 Batch MongoDB position writes (HIGHEST IMPACT)
- **File:** `src/market_scraper/orchestration/lifecycle.py` lines 578-611
- **Current:** Sequential `await store_trader_position()` for each position — 27K individual MongoDB round-trips
- **Fix:** Collect all `TraderPosition` models in a list, call new `store_trader_position_bulk()` method using MongoDB `insert_many()`
- **Expected:** 27K round-trips → 1 bulk write = **100x reduction in MongoDB latency**

### 2.4 Skip unchanged positions
- **File:** `src/market_scraper/orchestration/lifecycle.py`
- Before creating `TraderPosition` model, compare position payload with previous state
- If unchanged, skip the write entirely

---

## 3. Architectural Fixes — Prevent Event Loop Blocking

### 3.1 Offload flush to background task with chunked processing
- **File:** `src/market_scraper/core/trader_ws.py`
- Split 27K events into chunks of 200
- `asyncio.gather(*[process_chunk(c) for c in chunks])` with `asyncio.sleep(0)` between chunks
- This yields control back to the event loop between chunks so WebSocket pings are handled

### 3.2 Make flush non-blocking
- **File:** `src/market_scraper/core/trader_ws.py`
- `_flush_messages()` should spawn a background `asyncio.Task` instead of blocking `_flush_loop()`
- The flush task processes chunks asynchronously while the main loop continues handling WebSocket messages

### 3.3 Bulk MongoDB writes
- **File:** `src/market_scraper/storage/mongo_repository.py`
- Create `upsert_trader_current_state_bulk()` using `bulk_write()` with `UpdateOne` operations
- Single round-trip instead of N individual upserts
- Create `store_trader_position_bulk()` using `insert_many()` for position history

### 3.4 Offload CPU-bound normalization to thread pool
- **File:** `src/market_scraper/core/trader_ws.py`
- `_serialize_for_comparison()` (line 476) and `_normalize_positions()` do deep recursive dict/list traversal + `json.dumps()` — CPU-bound
- Move to `asyncio.to_thread()` or `loop.run_in_executor()` to avoid blocking the event loop
- **Critical:** `_has_significant_change()` (line 547) calls 3 normalize functions per message — this is the main CPU bottleneck
- **Even more critical:** `_create_trader_positions_event()` (line 716) calls ALL 3 normalize functions AGAIN to cache in `_last_positions` — so each event triggers **6 JSON serializations total**

### 3.5 Fix the triple-normalization anti-pattern
- **File:** `src/market_scraper/core/trader_ws.py`
- `_has_significant_change()` (line 547): normalizes positions, open_orders, and balances to compare — 3 JSON serializations
- `_create_trader_positions_event()` (line 716): normalizes the same 3 things AGAIN to store in `_last_positions` — 3 more serializations
- **Fix:** Compute normalization once, pass the result to both the comparison AND the cache
- This cuts CPU work per event from 6 serializations → 3 (**50% reduction**)

---

## 4. Memory Fixes — Reduce 876MB → Target <600MB

### 4.1 Replace `_last_positions` cache with hashes (BIGGEST MEMORY WIN)
- **File:** `src/market_scraper/core/trader_ws.py` lines 741-747
- **Current:** Stores raw positions + 3 normalized JSON strings per trader — ~5KB per trader
- **Fix:** Replace with a single SHA-256 hash of normalized data — ~100 bytes per trader
- **Impact:** 1000 traders × 5KB = 5MB → 100KB (**98% reduction in comparison cache**)
- Comparison becomes: `hash(new_data) != hash(old_data)` instead of deep dict comparison

### 4.2 Clear buffer references after flush
- **File:** `src/market_scraper/core/trader_ws.py`
- After `_flush_messages()` completes, explicitly `del` or clear references to processed messages
- Ensure no retained references to large dicts that prevent GC

### 4.3 Reduce max tracked positions
- **File:** `src/market_scraper/core/trader_ws.py` line 46
- Reduce `MAX_TRACKED_POSITIONS` from 1000 to 200 — matches `max_traders=200` config
- This limits per-trader position memory to what's actually needed

### 4.4 Reduce position state TTL
- **File:** `src/market_scraper/core/trader_ws.py` line 44
- Reduce `POSITION_STATE_TTL` from 86400 (24h) to 3600 (1h) — faster stale entry cleanup
- Prevents memory accumulation from inactive traders

### 4.5 Limit leaderboard cache
- **File:** `src/market_scraper/core/leaderboard.py` line 79
- `_last_leaderboard` can grow to multi-MB with full leaderboard payloads
- Add size limit or switch to hash-based change detection like 4.1

### 4.6 Use `__slots__` on high-volume dataclasses
- **Files:** All model classes in `src/market_scraper/models/`
- `__slots__` reduces per-instance memory by 40-50% by eliminating `__dict__`
- Particularly impactful for TraderPosition and event models with millions of instances

---

## 5. Verification — Confirm Each Fix Works

### 5.1 Per-fix metrics
| Metric | Before | Target | How to measure |
|--------|--------|--------|----------------|
| Event loop lag | ~5-10s | <100ms | `monitor_loop_lag()` task |
| RSS memory | 876MB | <600MB | `psutil.Process().memory_info().rss` |
| Flush duration | ~5-10s | <2s | `time.monotonic()` instrumentation |
| MongoDB writes per flush | 27K individual | 1-5 bulk ops | Counter in storage handler |
| WS reconnects/hour | ~10 | 0 | WebSocket manager logs |

### 5.2 Load test
- Simulate 27K position updates in a single flush cycle
- Measure: flush duration, event loop lag, memory delta, MongoDB write count

### 5.3 Continuous monitoring
- Add metrics: `flush_duration_seconds`, `buffer_size`, `mongodb_write_duration_seconds`, `event_loop_lag_seconds`
- Log these every flush cycle for trend analysis

---

## Implementation Order (by impact × ease)

| Priority | Task | Section | Expected Impact | Effort |
|----------|------|---------|-----------------|--------|
| 1 | Batch MongoDB position writes | 2.3 | **100x fewer DB round-trips** | Medium |
| 2 | Fix triple-normalization anti-pattern | 3.5 | **50% CPU reduction per event** | Low |
| 3 | Replace cache with hashes | 4.1 | **98% comparison cache reduction** | Medium |
| 4 | More frequent event loop yields | 2.2 | Unblocks event loop between chunks | Trivial |
| 5 | Chunked flush processing | 3.1 | Prevents multi-second blocking | Medium |
| 6 | Offload CPU normalization to thread pool | 3.4 | Moves CPU work off event loop | Medium |
| 7 | Reduce MAX_TRACKED_POSITIONS | 4.3 | ~80% position memory reduction | Trivial |
| 8 | Reduce POSITION_STATE_TTL | 4.4 | Faster stale cleanup | Trivial |
| 9 | Add timing instrumentation | 1.1 | Enables measurement of all other fixes | Low |
| 10 | Clear buffer references | 4.2 | Prevents GC misses | Low |
