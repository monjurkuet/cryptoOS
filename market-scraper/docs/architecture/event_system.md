# Event System Architecture

## Overview

The market-scraper uses a dual-dispatch event bus pattern:

1. **Direct Local Dispatch** — In-process handlers receive events immediately without Redis serialization
2. **Redis Pub/Sub** — Events are published to Redis channels for external consumers

## Event Flow

```
Trader WS Message
       │
       ▼
┌──────────────┐     Quick Hash     ┌───────────────┐
│ Message Buffer│ ──── Dedup ────→  │ Skip (65%)    │
│ (asyncio.Queue)│                   └───────────────┘
└──────┬───────┘
       │ New/Changed
       ▼
┌──────────────┐     Normalize      ┌───────────────┐
│ Thread Pool   │ ──── (CPU) ────→  │ Normalized    │
│ (2 workers)   │                   │ Events        │
└──────┬───────┘                    └───────┬───────┘
       │                                    │
       ▼                                    ▼
┌──────────────────────────────────────────────────────┐
│ RedisBus.publish()                                    │
│                                                      │
│  1. Direct dispatch to local subscribers (awaited)   │
│     - storage_handler → MongoDB buffer               │
│     - signal_handler → Signal generation             │
│     - leaderboard_sync_handler → Leaderboard update  │
│                                                      │
│  2. Redis PUBLISH for external consumers             │
│     - API server WebSocket streaming                 │
│     - Dashboard                                      │
└──────────────────────────────────────────────────────┘
```

## Local Subscribers (subscribe_local)

| Event Type | Handler | Purpose |
|---|---|---|
| `*` (wildcard) | `storage_handler` | Buffer all events for MongoDB persistence |
| `trader_positions` | `signal_handler` | Generate trading signals from position changes |
| `scored_traders` | `signal_handler` | Process scored trader updates |
| `mark_price` | `signal_handler` | Process mark price updates |
| `leaderboard` | `leaderboard_sync_handler` | Sync leaderboard to tracked traders |

## Write Buffering

Position events are not written to MongoDB individually. Instead:

1. Events are buffered in `_position_buffer` (dict of address → state)
2. Buffer is flushed every 5 seconds OR when 50 items accumulate
3. Flush uses `bulk_write([UpdateOne(...)])` — a single MongoDB operation
4. This reduces ~380 individual writes per flush to 1-2 batch operations

## Quick Hash Dedup

Before running expensive normalization (CPU-bound in thread pool):

1. Compute SHA-256 hash of: position entries (coin, size, entryPx, leverage) + open orders (coin, side, size, price)
2. Compare with previous hash for that trader address
3. If unchanged → skip normalization entirely (saves ~65% of CPU work)
4. If changed → proceed with full normalization and update hash

This is especially effective because most WS updates are heartbeats with no position changes.
