# Market-Scraper Optimization Plan

## Current State: The Problem

On a **1-vCPU / 1GB VPS**, the service is doing WAY too much work:

| Metric | Current | Problem |
|---|---|---|
| Tracked traders | 100 | 10 WS clients × 10 subs each |
| WS messages/min | ~550 | All buffered, normalized, hashed |
| Events per 60s flush | ~190 | After 65% dedup — still 190 |
| MongoDB writes per flush | ~380 | 190 upserts + 190 bulk inserts |
| Leaderboard fetch | 25MB / 35K rows / hour | 99.7% of data is discarded |
| Redis events per flush | ~190 publish calls | ALL consumers are in-process |
| Normalize CPU waste | 65% of messages | Normalized then skipped |
| Event loop lag spikes | 30-140s | From write storms blocking |
| Memory | 400MB+ RSS + swap | OOM risk on 1GB machine |

**Root cause**: Architecture was designed for a larger machine. On budget VPS, every inefficiency is amplified.

---

## Optimization Plan (3 Phases)

### Phase 1: Quick Wins (High Impact, Low Risk)
*Estimated reduction: 70% less writes, 50% less CPU*

**1A. Reduce tracked traders: 100 → 50**
- Change `filters.max_count: 100` → `50` in `market_config.yaml`
- 5 WS clients instead of 10 → half the connections, half the messages
- Still covers top 50 Hyperliquid traders by score — more than enough for signals
- **Impact**: 50% fewer WS messages, 50% fewer MongoDB writes

**1B. Increase flush interval: 60s → 120s**
- Change `buffer.flush_interval: 60.0` → `120.0` in `market_config.yaml`
- `position_max_interval: 600s` (10 min) ensures we never go too stale
- More messages per flush but fewer flush cycles → better batching
- **Impact**: 50% fewer flush cycles per hour

**1C. Slim down leaderboard event payload**
- In `leaderboard.py`, the event publishes BOTH `rows` (35K) AND `traders` (same 35K)
- Change: only publish the filtered ~50-100 scored traders, not raw 35K rows
- Downstream processors (position_inference, trader_scoring) already filter — give them pre-filtered data
- **Impact**: Eliminates ~50MB Redis payload per hour, reduces serialization time from seconds to ms

**1D. Cap concurrent MongoDB write tasks**
- `_max_active_writes = 16` exists but isn't actually enforced (the cap logic was incomplete)
- Properly enforce the cap: if active writes >= max, queue instead of `create_task`
- Or simpler: use `asyncio.Semaphore(12)` around the write task creation
- **Impact**: Prevents write storms from saturating thread pool → eliminates 140s lag spikes

### Phase 2: Architecture Improvements (Medium Effort, High Impact)
*Estimated reduction: 80% less CPU on normalization, eliminate Redis overhead*

**2A. Move dedup BEFORE normalization**
- Current: buffer → normalize (CPU) → hash → compare → skip if same
- Proposed: buffer → **quick hash of raw JSON bytes** → if same, skip → if different, normalize + full hash
- Saves 65% of normalization CPU (the skipped messages never get normalized)
- **Impact**: Eliminates ~360 unnecessary normalization calls per flush cycle

**2B. Batch MongoDB upserts with bulk_write**
- Current: 190 individual `find_one + replace_one` calls per flush
- Proposed: Collect all upserts into a single `bulk_write([UpdateOne(...), ...])`
- MongoDB Atlas handles bulk_write much more efficiently than individual ops
- **Impact**: ~380 writes → 1-2 bulk operations per flush

**2C. Bypass Redis for intra-process events**
- All `trader_positions` consumers are in-process (storage handler, signal processor)
- Add a direct dispatch path: `event_bus.publish()` → checks if any in-process subscribers → calls handlers directly
- Only use Redis publish for events that have external consumers
- **Impact**: Eliminates 190 Redis round-trips per flush (each saves ~1-2ms of event loop time)

### Phase 3: Optional / Lower Priority
*For further optimization if needed*

**3A. Reduce position_max_interval: 600s → 300s**
- Currently force-saves every 10 min even if no change
- Reducing to 5 min is still safe for signal freshness
- **Impact**: Fewer force-saves during quiet periods

**3B. Disable candles WS on startup**
- Already disabled `candle_backfill.run_on_startup`
- Could also reduce candle update frequency if not needed for signals
- **Impact**: Reduces WS connection count + message volume

**3C. Add WS connection pooling**
- Instead of 5-10 separate aiohttp sessions, share one session across all clients
- Reduces TCP connection overhead and memory
- **Impact**: ~5x fewer TCP connections, lower memory

**3D. Switch leaderboard from full fetch to delta sync**
- Instead of re-fetching entire 35K-row leaderboard every hour, cache the last response
- Only re-process traders whose scores/positions have changed
- **Impact**: Reduces hourly leaderboard CPU from ~25MB JSON parse to near-zero

---

## Expected Results After Each Phase

| Metric | Current | After Phase 1 | After Phase 2 |
|---|---|---|---|
| WS clients | 10 | 5 | 5 |
| Messages/flush | ~550 | ~275 | ~275 |
| Events/flush | ~190 | ~50-80 | ~50-80 |
| MongoDB writes/flush | ~380 | ~1-2 (bulk) | ~1-2 (bulk) |
| Normalization CPU/flush | 550 calls | ~275 calls | ~95 calls (only changes) |
| Redis round-trips/flush | 190 | 190 → direct | 0 (direct dispatch) |
| Leaderboard payload | 50MB | ~200KB | ~200KB |
| Event loop lag | 30-140s | <5s | <1s |
| Memory (RSS) | 400MB+ | ~250MB | ~200MB |

---

## Implementation Order

1. **Phase 1A-1D**: Config changes + small code fixes → commit → restart → verify
2. **Phase 2A**: Quick hash before normalization → test hash accuracy
3. **Phase 2B**: Bulk write for upserts → test MongoDB compat
4. **Phase 2C**: Direct dispatch bypass → test event delivery

Each step is independently deployable and reversible.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Fewer traders = missed signals | Top 50 by score covers >95% of profitable traders |
| Longer flush = slightly stale data | `position_max_interval=600s` ensures max 10min staleness |
| Bulk write failures | Fall back to individual writes on error |
| Direct dispatch breaks consumers | Keep Redis as fallback, add feature flag |
| Quick hash false negatives | Full normalize is still run when quick hash differs |

---

*Awaiting review before implementation.*
