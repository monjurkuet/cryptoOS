# Staggered WebSocket Ramp-Up Implementation Plan

## Problem Statement

The market-scraper starts **50 WebSocket clients simultaneously** during bootstrap via `asyncio.gather(*start_tasks)`. Each client performs `ws_connect` + 10 sequential `send_json` calls. This floods the event loop causing:
- Event loop lag spikes of 15–228 seconds
- API endpoints unresponsive for 3–17 minutes
- WS heartbeats time out → connection losses → reconnect storms
- Full startup takes 3–17 minutes

## Root Cause Analysis

| Phase | What Happens | Event Loop Impact |
|-------|-------------|-------------------|
| 1. `ws_connect` × 50 | 50 concurrent TCP handshakes to Hyperliquid | Moderate (async I/O) |
| 2. `send_json` × 500 | 500 sequential subscribe messages across 50 clients | **Severe** — each `send_json` + `sleep(0.01)` occupies the loop |
| 3. MongoDB flush | Fire-and-forget but semaphore-bound (4 slots) | Moderate (0.6-3.5s at steady state) |
| 4. `_init_trader_ws_collector` blocks | `await collector.start()` blocks lifecycle | **Severe** — `is_ready` never becomes true until all 50 clients connected |

The core issue: **`asyncio.gather` starts all 50 clients at once**, each executing 10+ sequential async operations. With event loop lag, the 0.01s sleeps become 1-5s each, so 500 subs × 2s = ~16 minutes.

## Implementation Plan

### Change 1: Staggered Client Startup in `TraderWebSocketCollector.start()`

**File:** `trader_ws.py` (line 148-213)

**Current code:**
```python
start_tasks = [client.start() for client in self._clients]
results = await asyncio.gather(*start_tasks, return_exceptions=True)
```

**New code:**
```python
async def start(self, traders: list[str] | None = None) -> None:
    """Start the collector with staggered client ramp-up."""
    if self._running:
        logger.warning("trader_ws_already_running")
        return

    self._tracked_traders = [str(t).lower() for t in (traders or []) if t]
    self._running = True

    # ... existing flush/lag monitor setup ...

    if not self._tracked_traders:
        logger.warning("no_traders_to_track")
        return

    # Split traders among clients (existing logic)
    trader_batches = [
        self._tracked_traders[i : i + self._batch_size]
        for i in range(0, len(self._tracked_traders), self._batch_size)
    ]
    num_needed_clients = len(trader_batches)
    num_clients_to_create = min(num_needed_clients, self._num_clients)

    for i, batch in enumerate(trader_batches[:num_clients_to_create]):
        client = TraderWSClient(
            client_id=i,
            traders=batch,
            on_message=self._handle_message,
            on_disconnect=self._handle_disconnect,
            config=self.config,
        )
        self._clients.append(client)

    # NEW: Staggered ramp-up instead of gather-all
    await self._ramp_up_clients()

    self._schedule_bootstrap(self._tracked_traders)


async def _ramp_up_clients(self) -> None:
    """Start clients in small batches with inter-batch delays.

    This prevents event loop starvation by limiting concurrent
    WebSocket handshakes and subscription floods.
    """
    RAMP_CONCURRENCY = 2       # Start 2 clients at a time
    RAMP_BATCH_DELAY = 2.0     # 2s pause between batches
    RAMP_SUBSCRIBE_DELAY = 0.05  # 50ms between subscribe messages (was 10ms)

    successful = 0
    failed = 0

    for batch_start in range(0, len(self._clients), RAMP_CONCURRENCY):
        batch = self._clients[batch_start : batch_start + RAMP_CONCURRENCY]

        # Start this small batch concurrently
        start_tasks = [client.start(subscribe_delay=RAMP_SUBSCRIBE_DELAY) for client in batch]
        results = await asyncio.gather(*start_tasks, return_exceptions=True)

        for r in results:
            if r is True:
                successful += 1
            else:
                failed += 1
                if isinstance(r, Exception):
                    logger.warning(
                        "trader_ws_client_start_failed",
                        error=str(r),
                    )

        logger.info(
            "trader_ws_ramp_batch_complete",
            batch_start=batch_start,
            batch_size=len(batch),
            successful_so_far=successful,
            failed_so_far=failed,
            total=len(self._clients),
        )

        # Pause between batches to let event loop process other tasks
        if batch_start + RAMP_CONCURRENCY < len(self._clients):
            await asyncio.sleep(RAMP_BATCH_DELAY)

    logger.info(
        "trader_ws_ramp_complete",
        successful=successful,
        failed=failed,
        total=len(self._clients),
    )
```

**Parameters:**
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `RAMP_CONCURRENCY` | 2 | Only 2 concurrent WS connections. With 50 clients, 25 batches × 2s = ~50s total |
| `RAMP_BATCH_DELAY` | 2.0s | Gives event loop time to process heartbeats, API requests, MongoDB callbacks |
| `RAMP_SUBSCRIBE_DELAY` | 0.05s | 5× increase from 0.01s. 10 subs × 0.05s = 0.5s per client — still fast enough |

### Change 2: Parameterize `TraderWSClient.start()` subscribe delay

**File:** `trader_ws.py` (line 1149-1198)

**Current code:**
```python
async def start(self) -> bool:
    # ...
    for address in self.traders:
        await self._ws.send_json({...})
        await asyncio.sleep(0.01)  # Hardcoded
```

**New code:**
```python
async def start(self, subscribe_delay: float = 0.01) -> bool:
    """Start the WebSocket client.

    Args:
        subscribe_delay: Seconds to sleep between subscribe messages.
            Increase during ramp-up (0.05s) to reduce event loop pressure.
    """
    try:
        self._running = True
        self._session = aiohttp.ClientSession()
        self._session_closed = False

        self._ws = await self._session.ws_connect(
            TraderWebSocketCollector.WS_URL,
            heartbeat=self.config.heartbeat_interval,
        )

        logger.info("trader_ws_client_connected", client_id=self.client_id)

        for address in self.traders:
            if self._ws.closed:
                raise ConnectionError(
                    "WebSocket closed before subscription completed"
                )
            await self._ws.send_json({
                "method": "subscribe",
                "subscription": {"type": "webData2", "user": address},
            })
            await asyncio.sleep(subscribe_delay)  # Parameterized

        self._reconnect_attempts = 0

        logger.info(
            "trader_ws_client_subscribed",
            client_id=self.client_id,
            traders=len(self.traders),
        )

        self._listen_task = asyncio.create_task(self._listen())
        return True
```

**Reconnect path unchanged:** The `_reconnect_with_backoff()` method calls `start()` without arguments → defaults to 0.01s. Reconnections of 1-2 clients don't need throttling.

### Change 3: Non-Blocking Lifecycle Startup

**File:** `lifecycle.py` (line 899-958)

**Current code:**
```python
async def _init_trader_ws_collector(self) -> None:
    # ... create collector ...

    async def sync_trader_ws_from_repository(reason: str) -> None:
        # ...
        await self._trader_ws_collector.start(addresses)  # BLOCKS!
```

Called from `_startup()` which awaits it before setting `is_ready = True`.

**New code:**
```python
async def _init_trader_ws_collector(self) -> None:
    """Initialize the trader WebSocket collector for position tracking.

    The collector is started in the background — this method returns
    immediately after creating the collector instance. The actual WS
    ramp-up happens in a fire-and-forget task so that lifecycle startup
    can complete and the API becomes responsive within seconds.
    """
    if not self._event_bus:
        raise RuntimeError("Event bus not initialized")

    if not self._settings.hyperliquid.enabled:
        logger.info("trader_ws_collector_disabled")
        return

    # Load market configuration from YAML
    market_config = load_market_config()

    # Create the collector
    self._trader_ws_collector = TraderWebSocketCollector(
        event_bus=self._event_bus,
        config=self._settings.hyperliquid,
        on_bootstrap_event=self._store_trader_positions_state,
        buffer_config=market_config.buffer,
    )

    # Start the collector in the background — do NOT await
    asyncio.create_task(self._bg_start_trader_ws(reason="startup"))


async def _bg_start_trader_ws(self, reason: str) -> None:
    """Background task to sync and start trader WS collector.

    This runs after lifecycle startup completes, so the API and health
    endpoints are responsive while WS clients ramp up.
    """
    if not self._repository or not self._trader_ws_collector:
        return

    try:
        addresses = await self._repository.get_active_trader_addresses()
    except Exception as e:
        logger.error(
            "trader_ws_sync_repository_error",
            reason=reason,
            error=str(e),
            exc_info=True,
        )
        return

    if not addresses:
        logger.warning("trader_ws_sync_no_active_addresses", reason=reason)
        return

    try:
        if not self._trader_ws_collector.get_stats().get("running", False):
            logger.info("trader_ws_starting_from_sync", reason=reason, count=len(addresses))
            await self._trader_ws_collector.start(addresses)
            return

        result = await self._trader_ws_collector.sync_traders(addresses)
        logger.info("trader_ws_synced", reason=reason, **result)
    except Exception as e:
        logger.error(
            "trader_ws_sync_failed",
            reason=reason,
            error=str(e),
            exc_info=True,
        )
```

### Change 4: Health Status Reflects WS Ramp-Up Progress

**File:** `lifecycle.py` — in `get_detailed_health()`

Add a `ws_ramp_up` component to health status that shows progress:

```python
# In get_detailed_health(), add:
if self._trader_ws_collector:
    stats = self._trader_ws_collector.get_stats()
    total = stats.get("total_clients", 0)
    connected = stats.get("connected_clients", 0)
    if total > 0 and connected < total:
        components["ws_ramp_up"] = {
            "status": "degraded",
            "connected": connected,
            "total": total,
            "progress_pct": round(connected / total * 100, 1),
        }
    elif total > 0 and connected == total:
        components["ws_ramp_up"] = {
            "status": "healthy",
            "connected": connected,
            "total": total,
        }
```

### Change 5: Add `get_stats()` Fields for Ramp-Up Tracking

**File:** `trader_ws.py` — in `get_stats()` method

Add `total_clients` and `connected_clients` fields:

```python
def get_stats(self) -> dict[str, Any]:
    """..."""
    connected = sum(1 for c in self._clients if c._running and not c._ws.closed if hasattr(c, '_ws') else False)
    return {
        # ... existing fields ...
        "total_clients": len(self._clients),
        "connected_clients": connected,
        "running": self._running,
    }
```

## Expected Results

| Metric | Before | After |
|--------|--------|-------|
| Startup time | 3–17 min | < 60s (lifecycle) + ~50s (background WS ramp-up) |
| Event loop lag during startup | 15–228s | < 5s |
| API responsiveness during startup | Unresponsive | Responsive within 10s |
| `is_ready` becomes true | After ALL 50 clients | Immediately after lifecycle init |
| Steady-state behavior | Unchanged | Unchanged |

## Risk Analysis

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Some WS clients fail during ramp-up | Low (2 at a time is gentle) | Existing reconnect logic handles it — retries with exponential backoff |
| Background `_bg_start_trader_ws` crashes silently | Low | Wrapped in try/except with logger.error; health endpoint tracks ws_ramp_up status |
| Slower startup for the WS connections themselves | Expected (50s vs instant) | Acceptable trade-off: API is responsive, dashboard doesn't timeout |
| `subscribe_delay=0.05` too slow for reconnections | N/A | Reconnect path uses default 0.01s — only ramp-up uses 0.05s |
| Race condition if `add_trader()` called during ramp-up | Low | `_running` flag set before ramp-up starts; `add_trader()` checks it |

## Rollback Strategy

1. Revert `start()` to use `asyncio.gather(*start_tasks)` 
2. Revert `_init_trader_ws_collector()` to block on `await start()`
3. Revert `TraderWSClient.start()` to hardcoded `0.01s`

All changes are self-contained in 2 files with no schema or dependency changes.

## Files Modified

1. `/home/administrator/githubrepo/cryptoOS/market-scraper/src/market_scraper/connectors/hyperliquid/collectors/trader_ws.py`
   - `start()`: Replace `gather` with `_ramp_up_clients()`
   - New: `_ramp_up_clients()` method
   - `TraderWSClient.start()`: Add `subscribe_delay` parameter
   - `get_stats()`: Add `total_clients`, `connected_clients` fields

2. `/home/administrator/githubrepo/cryptoOS/market-scraper/src/market_scraper/orchestration/lifecycle.py`
   - `_init_trader_ws_collector()`: Non-blocking background start
   - New: `_bg_start_trader_ws()` method
   - `get_detailed_health()`: Add `ws_ramp_up` component
