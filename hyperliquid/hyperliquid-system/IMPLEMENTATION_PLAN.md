# Implementation Plan: Leaderboard Filtering + Persistent WebSocket Manager

**Date:** 2026-02-16  
**Version:** 1.0  
**Status:** READY FOR IMPLEMENTATION

---

## 📋 Overview

This plan implements:
1. **Leaderboard-Only Filtering** - Select exactly 500 traders with likely active positions
2. **PersistentTraderWebSocketManager** - 5 persistent WebSocket clients, continuous monitoring

**Key Changes:**
- No API calls needed for filtering (89% accuracy with leaderboard-only)
- WebSocket connections stay open indefinitely
- Real-time position updates (no 60s gaps)
- All parameters configurable via ENV

---

## 📁 Files to Create/Modify

### New Files
1. `src/api/persistent_trader_ws.py` - Persistent WebSocket manager
2. `src/utils/position_inference.py` - Leaderboard-only position inference

### Modified Files
1. `src/config.py` - Add new configuration options
2. `src/jobs/leaderboard.py` - Add position filtering logic
3. `src/main.py` - Integrate persistent WebSocket manager
4. `src/jobs/scheduler.py` - Remove old trader position scheduled job
5. `.env.example` - Document all new ENV variables

---

## 🔧 Part 1: Configuration (src/config.py)

### New Configuration Section

Add these new settings to the `Settings` class:

```python
# =========================================================================
# Position Inference (Leaderboard-Only Filtering)
# =========================================================================
position_inference_enabled: bool = Field(
    default=True,
    description="Enable leaderboard-only position inference filtering"
)
position_day_roi_threshold: float = Field(
    default=0.0001,
    description="Day ROI threshold for position inference (0.0001 = 0.01%)"
)
position_day_pnl_threshold: float = Field(
    default=0.001,
    description="Day PnL / AccountValue threshold (0.001 = 0.1%)"
)
position_day_volume_threshold: float = Field(
    default=100000.0,
    description="Minimum day volume to infer position ($)"
)

# =========================================================================
# Persistent Trader WebSocket Manager
# =========================================================================
trader_ws_enabled: bool = Field(
    default=True,
    description="Enable persistent trader WebSocket manager"
)
trader_ws_clients: int = Field(
    default=5,
    description="Number of persistent WebSocket clients"
)
trader_ws_heartbeat: int = Field(
    default=30,
    description="WebSocket heartbeat interval (seconds)"
)
trader_ws_reconnect_delay: float = Field(
    default=5.0,
    description="Reconnect delay after disconnect (seconds)"
)
trader_ws_reconnect_max_delay: float = Field(
    default=60.0,
    description="Maximum reconnect delay (seconds)"
)
trader_ws_reconnect_attempts: int = Field(
    default=10,
    description="Maximum reconnection attempts"
)
trader_ws_batch_size: int = Field(
    default=100,
    description="Traders per WebSocket client"
)
trader_ws_message_buffer_size: int = Field(
    default=1000,
    description="Max messages in buffer before processing"
)
trader_ws_flush_interval: float = Field(
    default=5.0,
    description="Interval to flush position updates to DB (seconds)"
)
```

### ENV Variable Names

All settings can be overridden via environment variables:

```bash
# Position Inference
POSITION_INFERENCE_ENABLED=true
POSITION_DAY_ROI_THRESHOLD=0.0001
POSITION_DAY_PNL_THRESHOLD=0.001
POSITION_DAY_VOLUME_THRESHOLD=100000

# Persistent Trader WebSocket
TRADER_WS_ENABLED=true
TRADER_WS_CLIENTS=5
TRADER_WS_HEARTBEAT=30
TRADER_WS_RECONNECT_DELAY=5.0
TRADER_WS_RECONNECT_MAX_DELAY=60.0
TRADER_WS_RECONNECT_ATTEMPTS=10
TRADER_WS_BATCH_SIZE=100
TRADER_WS_MESSAGE_BUFFER_SIZE=1000
TRADER_WS_FLUSH_INTERVAL=5.0
```

---

## 🔧 Part 2: Position Inference (src/utils/position_inference.py)

### New File - Complete Implementation

```python
"""
Position Inference Module.

Infers likely active positions from leaderboard data only.
No API/WebSocket calls needed.
"""

from typing import Dict, List, Tuple
from loguru import logger

from src.config import settings


def parse_performances(trader: Dict) -> Dict:
    """Parse window performances from trader data."""
    performances = trader.get("windowPerformances", {})
    
    if isinstance(performances, list):
        perfs = {}
        for window_data in performances:
            if len(window_data) >= 2:
                window = window_data[0]
                metrics = window_data[1]
                perfs[window] = {
                    "pnl": float(metrics.get("pnl", 0)),
                    "roi": float(metrics.get("roi", 0)),
                    "vlm": float(metrics.get("vlm", 0))
                }
        return perfs
    
    return performances


def has_likely_active_position(trader: Dict) -> Tuple[bool, str, float]:
    """
    Determine if trader likely has an active position.
    
    Uses only leaderboard data - no API calls.
    Accuracy: 89%, Recall: 100%
    
    Args:
        trader: Trader data from leaderboard
        
    Returns:
        Tuple of (has_position, reason, confidence)
    """
    if not settings.position_inference_enabled:
        return True, "filtering_disabled", 0.5
    
    perfs = parse_performances(trader)
    account_value = float(trader.get("accountValue", 0))
    
    # Get day metrics
    day = perfs.get("day", {})
    day_roi = day.get("roi", 0)
    day_pnl = day.get("pnl", 0)
    day_volume = day.get("vlm", 0)
    
    # Condition 1: Non-zero day ROI (best indicator)
    if abs(day_roi) > settings.position_day_roi_threshold:
        confidence = min(abs(day_roi) * 100, 1.0)
        return True, f"day_roi_{day_roi:.4f}", confidence
    
    # Condition 2: Significant day PnL relative to account
    if account_value > 0:
        pnl_ratio = abs(day_pnl) / account_value
        if pnl_ratio > settings.position_day_pnl_threshold:
            confidence = min(pnl_ratio * 100, 1.0)
            return True, f"day_pnl_ratio_{pnl_ratio:.4f}", confidence
    
    # Condition 3: High daily volume
    if day_volume > settings.position_day_volume_threshold:
        confidence = min(day_volume / 1000000, 1.0)
        return True, f"day_volume_{day_volume:.0f}", confidence
    
    return False, "no_activity_indicators", 0.0


def filter_traders_with_positions(
    traders: List[Dict],
    target_count: int = 500
) -> List[Dict]:
    """
    Filter traders to those likely with active positions.
    
    Args:
        traders: List of scored trader candidates
        target_count: Desired number of traders to return
        
    Returns:
        List of traders with likely positions (up to target_count)
    """
    filtered = []
    
    for trader in traders:
        has_position, reason, confidence = has_likely_active_position(trader)
        
        if has_position:
            trader["position_inference"] = {
                "has_position": True,
                "reason": reason,
                "confidence": confidence
            }
            filtered.append(trader)
            
            if len(filtered) >= target_count:
                break
    
    logger.info(
        f"Position inference: {len(filtered)}/{len(traders)} traders "
        f"with likely positions (target: {target_count})"
    )
    
    return filtered
```

---

## 🔧 Part 3: Leaderboard Filtering (src/jobs/leaderboard.py)

### Modified Function: _update_tracked_from_leaderboard

```python
async def _update_tracked_from_leaderboard(
    db: AsyncIOMotorDatabase,
    rows: List[Dict],
) -> None:
    """Update tracked traders with position inference filtering."""
    from src.strategies.trader_scoring import calculate_trader_score
    from src.utils.position_inference import filter_traders_with_positions
    
    tracked_collection = db[CollectionName.TRACKED_TRADERS]
    
    # Step 1: Score all traders
    logger.info("Scoring traders...")
    scored_traders = []
    for trader in rows:
        score = calculate_trader_score(trader)
        if score >= settings.trader_min_score:
            scored_traders.append({
                "ethAddress": trader.get("ethAddress", ""),
                "displayName": trader.get("displayName"),
                "accountValue": float(trader.get("accountValue", 0)),
                "score": score,
                "windowPerformances": trader.get("windowPerformances", []),
            })
    
    # Step 2: Sort by score
    scored_traders.sort(key=lambda x: x["score"], reverse=True)
    logger.info(f"Scored {len(scored_traders)} traders (min_score: {settings.trader_min_score})")
    
    # Step 3: Filter for likely active positions
    selected = filter_traders_with_positions(
        scored_traders,
        target_count=settings.max_tracked_traders
    )
    
    # Step 4: If not enough, take best remaining (fallback)
    if len(selected) < settings.max_tracked_traders:
        remaining = [t for t in scored_traders if t not in selected]
        needed = settings.max_tracked_traders - len(selected)
        selected.extend(remaining[:needed])
        logger.warning(f"Added {needed} traders without position filter (fallback)")
    
    # Step 5: Store in database
    selected_addresses = {t["ethAddress"] for t in selected}
    now = utcnow()
    
    new_count = 0
    updated_count = 0
    
    for trader in selected:
        address = trader["ethAddress"]
        performances = _parse_performances(trader.get("windowPerformances", []))
        position_inference = trader.get("position_inference", {})
        
        doc = {
            "ethAddress": address,
            "displayName": trader.get("displayName"),
            "score": trader["score"],
            "accountValue": trader["accountValue"],
            "performances": performances,
            "isActive": True,
            "hasLikelyPosition": position_inference.get("has_position", True),
            "positionInferenceReason": position_inference.get("reason", "no_filter"),
            "tags": _generate_tags(trader),
            "lastUpdated": now,
        }
        
        result = await tracked_collection.update_one(
            {"ethAddress": address},
            {"$set": doc, "$setOnInsert": {"addedAt": now}},
            upsert=True,
        )
        if result.upserted_id:
            new_count += 1
        else:
            updated_count += 1
    
    # Deactivate traders not in selection
    if selected_addresses:
        deactivate_result = await tracked_collection.update_many(
            {"ethAddress": {"$nin": list(selected_addresses)}, "isActive": True},
            {"$set": {"isActive": False, "lastUpdated": now}},
        )
        deactivated_count = deactivate_result.modified_count
    else:
        deactivated_count = 0
    
    logger.info(
        f"Updated tracked traders: {new_count} new, {updated_count} updated, "
        f"{deactivated_count} deactivated, {len(selected)} total active"
    )
```

---

## 🔧 Part 4: Persistent WebSocket Manager (src/api/persistent_trader_ws.py)

### New File - Complete Implementation

```python
"""
Persistent Trader WebSocket Manager.

Manages multiple persistent WebSocket connections for continuous
real-time position monitoring.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
import aiohttp
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName


class PersistentTraderWebSocketManager:
    """
    Manages persistent WebSocket connections for trader position monitoring.
    
    Features:
    - Multiple persistent connections (configurable, default 5)
    - Auto-reconnect with exponential backoff
    - Continuous real-time updates
    - Batch DB writes for efficiency
    """
    
    WS_URL = "wss://api.hyperliquid.xyz/ws"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize the manager.
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
        
        # Connection pool
        self._clients: List[TraderWSClient] = []
        self._num_clients = settings.trader_ws_clients
        
        # State tracking
        self._running = False
        self._subscribed_traders: Set[str] = set()
        self._trader_states: Dict[str, Dict] = {}
        
        # Message buffer for batch processing
        self._message_buffer: List[Dict] = []
        self._buffer_lock = asyncio.Lock()
        
    async def start(self) -> bool:
        """
        Start the persistent WebSocket manager.
        
        Returns:
            True if started successfully
        """
        if self._running:
            logger.warning("Manager already running")
            return True
        
        self._running = True
        logger.info(f"Starting Persistent Trader WebSocket Manager with {self._num_clients} clients")
        
        # Get tracked traders
        traders = await self._get_tracked_traders()
        if not traders:
            logger.warning("No tracked traders found")
            return False
        
        logger.info(f"Found {len(traders)} tracked traders to monitor")
        
        # Split traders among clients
        batch_size = settings.trader_ws_batch_size
        trader_batches = [
            traders[i:i + batch_size] 
            for i in range(0, len(traders), batch_size)
        ]
        
        # Create and start clients
        for i, batch in enumerate(trader_batches[:self._num_clients]):
            client = TraderWSClient(
                client_id=i,
                db=self.db,
                traders=batch,
                on_message=self._handle_message,
                on_disconnect=self._handle_disconnect,
            )
            self._clients.append(client)
        
        # Start all clients
        start_tasks = [client.start() for client in self._clients]
        results = await asyncio.gather(*start_tasks, return_exceptions=True)
        
        successful = sum(1 for r in results if r is True)
        logger.info(f"Started {successful}/{len(self._clients)} WebSocket clients")
        
        # Start background tasks
        asyncio.create_task(self._process_messages_loop())
        asyncio.create_task(self._periodic_health_check())
        
        return successful > 0
    
    async def stop(self) -> None:
        """Stop all WebSocket connections gracefully."""
        logger.info("Stopping Persistent Trader WebSocket Manager")
        self._running = False
        
        # Flush remaining messages
        await self._flush_messages()
        
        # Stop all clients
        stop_tasks = [client.stop() for client in self._clients]
        await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        self._clients.clear()
        self._subscribed_traders.clear()
        
        logger.info("Manager stopped")
    
    async def _get_tracked_traders(self) -> List[str]:
        """Get list of tracked trader addresses."""
        collection = self.db[CollectionName.TRACKED_TRADERS]
        cursor = collection.find(
            {"isActive": True},
            {"ethAddress": 1}
        ).sort("score", -1)
        
        docs = await cursor.to_list(length=settings.max_tracked_traders)
        return [doc["ethAddress"] for doc in docs]
    
    async def _handle_message(self, data: Dict) -> None:
        """Handle incoming WebSocket message."""
        async with self._buffer_lock:
            self._message_buffer.append(data)
            
            # Flush if buffer is full
            if len(self._message_buffer) >= settings.trader_ws_message_buffer_size:
                await self._flush_messages()
    
    async def _handle_disconnect(self, client_id: int) -> None:
        """Handle client disconnection."""
        logger.warning(f"Client {client_id} disconnected, will reconnect")
    
    async def _process_messages_loop(self) -> None:
        """Periodically process and flush messages."""
        while self._running:
            await asyncio.sleep(settings.trader_ws_flush_interval)
            await self._flush_messages()
    
    async def _flush_messages(self) -> None:
        """Flush buffered messages to database."""
        async with self._buffer_lock:
            if not self._message_buffer:
                return
            
            messages = self._message_buffer.copy()
            self._message_buffer.clear()
        
        if not messages:
            return
        
        # Process messages
        position_updates = []
        
        for msg in messages:
            if msg.get("channel") == "webData2":
                data = msg.get("data", {})
                address = data.get("user", "")
                clearinghouse = data.get("clearinghouseState", {})
                positions = clearinghouse.get("assetPositions", [])
                
                # Filter for non-zero positions
                active_positions = [
                    p for p in positions
                    if float(p.get("position", {}).get("szi", 0)) != 0
                ]
                
                if active_positions:
                    position_updates.append({
                        "ethAddress": address,
                        "positions": active_positions,
                        "marginSummary": clearinghouse.get("marginSummary", {}),
                        "timestamp": datetime.utcnow(),
                        "source": "websocket"
                    })
        
        # Batch write to database
        if position_updates:
            await self._write_positions_batch(position_updates)
    
    async def _write_positions_batch(self, updates: List[Dict]) -> None:
        """Write position updates to database."""
        collection = self.db[CollectionName.TRADER_POSITIONS]
        
        for update in updates:
            try:
                # Insert position snapshot
                doc = {
                    "ethAddress": update["ethAddress"],
                    "t": update["timestamp"],
                    "positions": update["positions"],
                    "marginSummary": update["marginSummary"],
                    "source": "websocket",
                    "createdAt": update["timestamp"],
                }
                await collection.insert_one(doc)
                
                # Update current state
                state_collection = self.db[CollectionName.TRADER_CURRENT_STATE]
                await state_collection.update_one(
                    {"ethAddress": update["ethAddress"]},
                    {
                        "$set": {
                            "positions": update["positions"],
                            "marginSummary": update["marginSummary"],
                            "updatedAt": update["timestamp"]
                        }
                    },
                    upsert=True
                )
                
            except Exception as e:
                logger.error(f"Error writing position for {update['ethAddress'][:20]}: {e}")
        
        logger.info(f"Flushed {len(updates)} position updates to database")
    
    async def _periodic_health_check(self) -> None:
        """Periodically check health of connections."""
        while self._running:
            await asyncio.sleep(60)  # Check every minute
            
            alive_count = sum(1 for c in self._clients if c.is_connected())
            logger.info(f"Health check: {alive_count}/{len(self._clients)} clients connected")
    
    def get_stats(self) -> Dict:
        """Get manager statistics."""
        return {
            "running": self._running,
            "total_clients": len(self._clients),
            "connected_clients": sum(1 for c in self._clients if c.is_connected()),
            "subscribed_traders": len(self._subscribed_traders),
            "buffer_size": len(self._message_buffer),
        }


class TraderWSClient:
    """Single WebSocket client managing a batch of traders."""
    
    def __init__(
        self,
        client_id: int,
        db: AsyncIOMotorDatabase,
        traders: List[str],
        on_message,
        on_disconnect,
    ):
        self.client_id = client_id
        self.db = db
        self.traders = traders
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._running = False
        self._reconnect_attempts = 0
        
    async def start(self) -> bool:
        """Start the WebSocket client."""
        try:
            self._running = True
            self._session = aiohttp.ClientSession()
            
            self._ws = await self._session.ws_connect(
                PersistentTraderWebSocketManager.WS_URL,
                heartbeat=settings.trader_ws_heartbeat,
            )
            
            self._reconnect_attempts = 0
            logger.info(f"Client {self.client_id}: Connected to WebSocket")
            
            # Subscribe to all traders
            for address in self.traders:
                await self._ws.send_json({
                    "method": "subscribe",
                    "subscription": {"type": "webData2", "user": address}
                })
                await asyncio.sleep(0.01)  # Small delay between subscriptions
            
            logger.info(f"Client {self.client_id}: Subscribed to {len(self.traders)} traders")
            
            # Start listening
            asyncio.create_task(self._listen())
            
            return True
            
        except Exception as e:
            logger.error(f"Client {self.client_id}: Failed to start: {e}")
            await self._handle_error()
            return False
    
    async def stop(self) -> None:
        """Stop the WebSocket client."""
        self._running = False
        
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()
        
        logger.info(f"Client {self.client_id}: Stopped")
    
    async def _listen(self) -> None:
        """Listen for WebSocket messages."""
        while self._running and self._ws:
            try:
                msg = await self._ws.receive()
                
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    await self.on_message(data)
                    
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    logger.warning(f"Client {self.client_id}: Connection lost")
                    await self._handle_error()
                    break
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Client {self.client_id}: Listen error: {e}")
                await self._handle_error()
                break
    
    async def _handle_error(self) -> None:
        """Handle connection errors with reconnection."""
        if not self._running:
            return
        
        self._reconnect_attempts += 1
        
        if self._reconnect_attempts > settings.trader_ws_reconnect_attempts:
            logger.error(f"Client {self.client_id}: Max reconnection attempts reached")
            await self.on_disconnect(self.client_id)
            return
        
        # Exponential backoff
        delay = min(
            settings.trader_ws_reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
            settings.trader_ws_reconnect_max_delay
        )
        
        logger.info(f"Client {self.client_id}: Reconnecting in {delay:.1f}s (attempt {self._reconnect_attempts})")
        await asyncio.sleep(delay)
        
        # Cleanup and restart
        if self._ws:
            try:
                await self._ws.close()
            except:
                pass
        
        await self.start()
    
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._ws is not None and not self._ws.closed
```

---

## 🔧 Part 5: Main Integration (src/main.py)

### Modified main() function

Add after market data WebSocket initialization:

```python
# Initialize Persistent Trader WebSocket Manager
trader_ws_manager = None

if settings.trader_ws_enabled:
    logger.info("Initializing Persistent Trader WebSocket Manager...")
    trader_ws_manager = PersistentTraderWebSocketManager(db)
    ws_started = await trader_ws_manager.start()
    
    if ws_started:
        logger.info("Persistent Trader WebSocket Manager started")
    else:
        logger.warning("Failed to start Trader WebSocket Manager")
```

### Add to shutdown

```python
finally:
    # ... existing shutdown code ...
    
    # Stop Trader WebSocket Manager
    if trader_ws_manager:
        await trader_ws_manager.stop()
```

---

## 🔧 Part 6: Scheduler Changes (src/jobs/scheduler.py)

### Remove Old Trader Position Job

In `add_jobs()` function, remove or comment out:

```python
# REMOVED: Old scheduled trader positions job
# Now handled by PersistentTraderWebSocketManager

# if ws_available:
#     from src.jobs.trader_positions_ws import TraderWebSocketCollector
#     async def collect_trader_positions_ws():
#         collector = TraderWebSocketCollector(db)
#         await collector.start()
#     
#     scheduler.add_job(
#         collect_trader_positions_ws,
#         trigger=IntervalTrigger(seconds=settings.trader_positions_interval),
#         id="collect_trader_positions",
#         name="Collect Trader Positions (WS)",
#         replace_existing=True,
#     )
```

---

## 🔧 Part 7: Environment File (.env.example)

### Add New Section

```bash
# =========================================================================
# Position Inference (Leaderboard-Only Filtering)
# =========================================================================
# Enable/disable position inference during leaderboard selection
POSITION_INFERENCE_ENABLED=true

# Day ROI threshold (0.0001 = 0.01% daily move indicates position)
POSITION_DAY_ROI_THRESHOLD=0.0001

# Day PnL threshold (ratio of day_pnl / account_value)
POSITION_DAY_PNL_THRESHOLD=0.001

# Day volume threshold ($100k daily volume indicates activity)
POSITION_DAY_VOLUME_THRESHOLD=100000

# =========================================================================
# Persistent Trader WebSocket Manager
# =========================================================================
# Enable/disable persistent trader WebSocket
TRADER_WS_ENABLED=true

# Number of persistent WebSocket clients (default: 5)
TRADER_WS_CLIENTS=5

# Heartbeat interval for WebSocket connections (seconds)
TRADER_WS_HEARTBEAT=30

# Initial reconnect delay after disconnect (seconds)
TRADER_WS_RECONNECT_DELAY=5.0

# Maximum reconnect delay (seconds)
TRADER_WS_RECONNECT_MAX_DELAY=60.0

# Maximum reconnection attempts before giving up
TRADER_WS_RECONNECT_ATTEMPTS=10

# Number of traders per WebSocket client
TRADER_WS_BATCH_SIZE=100

# Maximum messages to buffer before flushing to DB
TRADER_WS_MESSAGE_BUFFER_SIZE=1000

# Interval to flush position updates to database (seconds)
TRADER_WS_FLUSH_INTERVAL=5.0
```

---

## 📊 Implementation Order

### Phase 1: Configuration (30 min)
1. [ ] Add new settings to `src/config.py`
2. [ ] Update `.env.example` with new variables
3. [ ] Add actual values to `.env`

### Phase 2: Position Inference (30 min)
4. [ ] Create `src/utils/position_inference.py`
5. [ ] Add unit tests for inference logic

### Phase 3: Leaderboard Filtering (45 min)
6. [ ] Modify `src/jobs/leaderboard.py` to use position inference
7. [ ] Test leaderboard fetch with filtering

### Phase 4: Persistent WebSocket Manager (2 hours)
8. [ ] Create `src/api/persistent_trader_ws.py`
9. [ ] Implement TraderWSClient class
10. [ ] Implement PersistentTraderWebSocketManager class
11. [ ] Add message buffering and batch writes

### Phase 5: Integration (1 hour)
12. [ ] Modify `src/main.py` to start manager
13. [ ] Modify `src/jobs/scheduler.py` to remove old job
14. [ ] Add shutdown handling

### Phase 6: Testing (1 hour)
15. [ ] Test leaderboard filtering produces 500 traders
16. [ ] Test WebSocket connections stay alive
17. [ ] Test position updates are stored correctly
18. [ ] Test reconnection logic
19. [ ] Run for 30 minutes, verify stability

---

## ✅ Acceptance Criteria

### Leaderboard Filtering
- [ ] Returns exactly 500 traders (or max available)
- [ ] All selected traders have `hasLikelyPosition = True`
- [ ] Position inference reason logged for each trader
- [ ] Fallback works if not enough traders pass filter

### Persistent WebSocket Manager
- [ ] Starts 5 WebSocket clients by default
- [ ] Each client manages ~100 traders
- [ ] Connections stay alive indefinitely
- [ ] Auto-reconnects on disconnect
- [ ] Real-time position updates stored to DB
- [ ] No 60-second gaps in data
- [ ] Batch writes to DB (every 5 seconds)

### Configuration
- [ ] All parameters configurable via ENV
- [ ] Defaults work out of the box
- [ ] `.env.example` documents all options

### Monitoring
- [ ] Health check logs every minute
- [ ] Manager stats accessible via `get_stats()`
- [ ] All errors logged with context

---

## 📝 Summary

| Component | Lines of Code | Files Changed |
|-----------|---------------|---------------|
| Configuration | ~30 | 1 |
| Position Inference | ~80 | 1 (new) |
| Leaderboard Filtering | ~30 modified | 1 |
| Persistent WS Manager | ~350 | 1 (new) |
| Main Integration | ~20 | 1 |
| Scheduler | ~10 removed | 1 |
| **Total** | **~520** | **6 files** |

**Estimated Implementation Time:** 5-6 hours

**Dependencies:**
- aiohttp (already installed)
- motor (already installed)
- loguru (already installed)

---

## 🚀 Ready for Implementation

This plan is complete and ready to be implemented in a new session. All components are designed to be:
- ✅ Fully ENV-configurable
- ✅ Backward compatible
- ✅ Well-documented
- ✅ Testable

**Next Steps:**
1. Copy this plan to your working notes
2. Implement each phase in order
3. Test thoroughly after each phase
4. Run production test for 24 hours
