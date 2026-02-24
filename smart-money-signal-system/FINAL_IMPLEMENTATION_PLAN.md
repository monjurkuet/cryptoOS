# Smart Money Signal System - Final Implementation Plan

**Project**: Smart Money Signal System for BTC Trading
**Architecture**: Two-Repository (Data + Intelligence Separation)
**Timeline**: 4 Weeks Remaining (Phase 1 Complete)
**Start Date**: 2026-02-24
**Status**: Phase 1 Complete - Ready for Phase 2
**Version**: 3.1 (Updated with Implementation Corrections)

---

## Executive Summary

This implementation plan is based on a **comprehensive codebase audit** of `/home/muham/development/cryptodata/market-scraper/` (8,132 lines of production code).

### Current State Assessment

| Component | Status | Lines of Code | Notes |
|-----------|--------|---------------|-------|
| **Data Collection** | ✅ Production-Ready | ~2,500 | Hyperliquid, CBBI, on-chain connectors |
| **Event Bus** | ✅ Production-Ready | ~400 | Memory + Redis implementations |
| **Storage Layer** | ✅ Production-Ready | ~2,500 | Memory + MongoDB repositories |
| **API Server** | ✅ Production-Ready | ~1,000 | FastAPI with 8 route modules |
| **TraderWebSocketCollector** | ✅ **INTEGRATED** | 615 | Managed in lifecycle.py, NOT manager.py |
| **Signal Generation** | ⚠️ Basic | 310 | Simple score/100 weighting |
| **ML Components** | ❌ Not Started | 0 | Needs implementation |
| **Whale Alerts** | ❌ Not Started | 0 | Needs implementation |

### Critical Finding

**Phase 1 is COMPLETE**. The TraderWebSocketCollector is now integrated and publishing `trader_positions` events to Redis.

**Implementation Note:** The `TraderWebSocketCollector` is managed **directly in `lifecycle.py`**, not through `CollectorManager`. This is because:
1. It has a different interface: `start(addresses: list[str])` vs `start()`
2. It manages its own WebSocket connections (5 clients, not shared)
3. It requires trader addresses at startup from the leaderboard

**Remaining work:**
1. ~~TraderWebSocketCollector NOT registered~~ ✅ DONE
2. ~~No trader subscription from leaderboard~~ ✅ DONE
3. Basic signal weighting (not multi-dimensional)
4. No ML components
5. No whale alert system

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│              market-scraper (Data Infrastructure)               │
│  Location: /home/muham/development/cryptodata/market-scraper/   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Connectors (10 sources)                                 │  │
│  │  ├── Hyperliquid (WebSocket + REST)                      │  │
│  │  │   ├── CandlesCollector (working)                      │  │
│  │  │   ├── TraderWebSocketCollector (implemented, disabled)│  │
│  │  │   └── LeaderboardCollector (working)                  │  │
│  │  ├── CBBI (9-component bull index)                       │  │
│  │  ├── Bitview (SOPR, MVRV, NUPL)                          │  │
│  │  ├── Fear & Greed                                        │  │
│  │  ├── Coin Metrics                                        │  │
│  │  ├── Blockchain.info                                     │  │
│  │  └── Exchange Flow                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Event Bus (Redis or Memory)                             │  │
│  │  Events: trader_positions, candles, leaderboard, etc.    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Storage (MongoDB or Memory)                             │  │
│  │  Collections: events, traders, signals, candles          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  FastAPI Server (port 8000)                              │  │
│  │  Routes: /api/v1/traders, /signals, /onchain, /health    │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Redis Pub/Sub
                              │ Channel: smart_money:*
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│         smart-money-signal-system (Intelligence Layer)          │
│  Location: /home/muham/development/cryptodata/smart-money-...   │
│  Status: NEW - To be created                                    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Event Subscriber                                        │  │
│  │  Subscribes: trader_positions, leaderboard               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Weighting Engine (Multi-dimensional)                    │  │
│  │  ├── Performance (Sharpe, Sortino, Consistency)          │  │
│  │  ├── Size (Account value tiers)                          │  │
│  │  ├── Recency (Day/Week/Month decay)                      │  │
│  │  └── Regime (Market condition alignment)                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  ML Components                                           │  │
│  │  ├── Feature Importance (RandomForest)                   │  │
│  │  └── Regime Detection (KMeans clustering)                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Whale Alert Detector                                    │  │
│  │  Priorities: CRITICAL, HIGH, MEDIUM, LOW                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Signal API (port 4341)                                  │  │
│  │  Routes: /signals, /alerts, /health                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Enable Real-Time Data Flow (Week 1, Days 1-2)

**Repository**: `market-scraper`
**Goal**: Enable TraderWebSocketCollector and verify event flow
**Status**: ✅ **COMPLETE** (as of 2026-02-24)

### Step 1.1: TraderWebSocketCollector Integration ✅ DONE

**File**: `src/market_scraper/orchestration/lifecycle.py`

**Implementation Note:** The `TraderWebSocketCollector` is **NOT** registered in `manager.py`. It's managed directly in `lifecycle.py` because:
1. It has a different interface than `BaseCollector`: `start(addresses: list[str])` vs `start()`
2. It manages its own WebSocket connections (5 clients with 100 traders each)
3. It requires trader addresses at startup from the leaderboard

**What was implemented:**
```python
# lifecycle.py - Added new method _init_trader_ws_collector()
async def _init_trader_ws_collector(self) -> None:
    """Initialize the trader WebSocket collector for position tracking."""
    # ... creates TraderWebSocketCollector
    # ... gets tracked addresses from leaderboard
    # ... starts collector with addresses
```

**Verification:**
```bash
cd /home/muham/development/cryptodata/market-scraper
uv run python -m market_scraper health
# Should show: ✓ trader_ws: healthy
```

**Effort**: ~~2 hours~~ COMPLETED
**Priority**: ~~CRITICAL~~ DONE
**Acceptance Criteria**:
- [x] TraderWebSocketCollector starts without errors
- [x] 500 traders subscribed via WebSocket
- [x] `trader_positions` events published to Redis

---

### Step 1.2: Add get_tracked_addresses to LeaderboardCollector ✅ DONE

**File**: `src/market_scraper/connectors/hyperliquid/collectors/leaderboard.py`

**Implementation** (lines 571-595):
```python
async def get_tracked_addresses(self) -> list[str]:
    """Get list of tracked trader addresses from database.

    Returns tracked traders that are marked as active in the database.
    Falls back to empty list if database is not available.

    Returns:
        List of Ethereum addresses for tracked traders
    """
    if self._db is None:
        logger.warning("get_tracked_addresses_no_database")
        return []

    try:
        from market_scraper.storage.models import CollectionName

        cursor = self._db[CollectionName.TRACKED_TRADERS].find(
            {"active": True}, {"eth": 1, "_id": 0}
        )
        addresses = [doc["eth"] async for doc in cursor]
        logger.debug("get_tracked_addresses_found", count=len(addresses))
        return addresses
    except Exception as e:
        logger.error("get_tracked_addresses_error", error=str(e), exc_info=True)
        return []
```

**Effort**: ~~1 hour~~ COMPLETED
**Priority**: ~~CRITICAL~~ DONE
**Acceptance Criteria**:
- [x] Method returns list of addresses from MongoDB
- [x] Handles missing database gracefully
- [x] Returns 500 tracked addresses

---

### Step 1.3: Enable Trader Subscription in Lifecycle Manager ✅ DONE

**File**: `src/market_scraper/orchestration/lifecycle.py`

**Implementation Note:** The TraderWebSocketCollector is **NOT** managed through `CollectorManager`. It's managed directly because:
1. It has a different interface: `start(addresses: list[str])` vs `start()`
2. It manages its own WebSocket connections (5 clients)
3. It needs trader addresses from the leaderboard before starting

**What was implemented:**

1. Added `_trader_ws_collector` attribute (line 33)
2. Added import for `TraderWebSocketCollector` (line 18)
3. Added `_init_trader_ws_collector()` method (lines 489-526)
4. Called after leaderboard initialization in `startup()` (lines 454-456)
5. Added cleanup in `shutdown()` (lines 417-423)
6. Added health check support (lines 590, 622, 647, 680, 722, 774)
7. Added connector management methods (lines 805-842, 868-887, 905-918, 967-970)

```python
async def _init_trader_ws_collector(self) -> None:
    """Initialize the trader WebSocket collector for position tracking."""
    if not self._event_bus:
        raise RuntimeError("Event bus not initialized")

    if not self._settings.hyperliquid.enabled:
        logger.info("trader_ws_collector_disabled")
        return

    market_config = load_market_config()

    self._trader_ws_collector = TraderWebSocketCollector(
        event_bus=self._event_bus,
        config=self._settings.hyperliquid,
        buffer_config=market_config.buffer,
    )

    # Wait for leaderboard to process and store tracked traders
    await asyncio.sleep(2.0)

    if self._leaderboard_collector:
        tracked_addresses = await self._leaderboard_collector.get_tracked_addresses()
        if tracked_addresses:
            logger.info("starting_trader_ws_with_tracked", count=len(tracked_addresses))
            await self._trader_ws_collector.start(tracked_addresses)
```

**Effort**: ~~2 hours~~ COMPLETED
**Priority**: ~~CRITICAL~~ DONE
**Acceptance Criteria**:
- [x] Lifecycle starts with trader_ws collector
- [x] Traders subscribed from leaderboard (500 traders)
- [x] No startup errors
- [x] Health check shows `trader_ws: healthy`

---

### Step 1.4: Verify Redis Configuration ✅ DONE

**File**: `.env`

**Configuration**:
```bash
REDIS__URL=redis://localhost:6379
```

**Verification**:
```bash
redis-cli ping
# Should return: PONG
```

**Effort**: ~~30 minutes~~ COMPLETED
**Priority**: ~~CRITICAL~~ DONE
**Acceptance Criteria**:
- [x] Redis server running
- [x] Connection test succeeds

---

### Step 1.5: End-to-End Data Flow Test ✅ DONE

**IMPORTANT: Redis Channel Naming**

Events are published to `events:{event_type}` channels, NOT `smart_money:*`:
```python
# From redis_bus.py
channel = f"events:{event.event_type}"
# Actual channels: "events:trader_positions", "events:candles", etc.
```

**Test Script**: `scripts/test_data_flow.py`

```python
#!/usr/bin/env python3
"""Test end-to-end data flow from WebSocket to Redis."""

import asyncio
import json
import redis.asyncio as redis

async def test_data_flow():
    """Test trader_positions events flow to Redis."""
    r = redis.from_url("redis://localhost:6379/0")
    pubsub = r.pubsub()

    # Subscribe to correct channel - "events:*" not "smart_money:*"
    await pubsub.psubscribe("events:*")

    print("Listening for events on 'events:*' pattern...")
    print("Start market-scraper in another terminal")

    message_count = 0
    try:
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                channel = message["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode()
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()

                print(f"Channel: {channel}")
                if data:
                    parsed = json.loads(data)
                    print(f"Event type: {parsed.get('event_type')}")
                    print(f"Data preview: {data[:200]}...")
                    message_count += 1
                    if message_count >= 5:
                        break
    finally:
        await pubsub.punsubscribe()
        await r.close()

if __name__ == "__main__":
    asyncio.run(test_data_flow())
```

**Run Test**:
```bash
# Terminal 1: Start market-scraper
cd /home/muham/development/cryptodata/market-scraper
uv run python -m market_scraper server

# Terminal 2: Run test
uv run python scripts/test_data_flow.py
```

**Expected Output**:
```
Listening for events on 'events:*' pattern...
Channel: events:trader_positions
Event type: trader_positions
Data preview: {"event_type":"trader_positions","source":"hyperliquid_trader_ws","payload":{"address":"0x..."}}
```

**Effort**: ~~1 hour~~ COMPLETED
**Priority**: ~~HIGH~~ DONE
**Acceptance Criteria**:
- [x] Events visible in Redis
- [x] trader_positions events received
- [x] 500 trader addresses tracked

---

### Phase 1 Deliverables

| Deliverable | Status | Verification |
|-------------|--------|--------------|
| TraderWebSocketCollector enabled | ✅ DONE | Collector starts without errors |
| get_tracked_addresses method | ✅ DONE | Returns 500 addresses |
| Lifecycle subscription | ✅ DONE | Traders subscribed on startup |
| Redis event publishing | ✅ DONE | Events visible in Redis (channel: events:trader_positions) |
| End-to-end test | ✅ DONE | Verified with health check |

**Phase 1 Timeline**: ~~1-2 days~~ COMPLETED
**Phase 1 Exit Criteria**: ✅ Real-time trader positions flowing to Redis

---

## Phase 2: Create Signal System Foundation (Week 1, Days 3-5)

**Repository**: `smart-money-signal-system` (NEW)
**Goal**: Create new repository with event subscription and basic signal generation

### Step 2.1: Initialize Project

**Commands**:
```bash
cd /home/muham/development/cryptodata/smart-money-signal-system

# Initialize with uv
uv init smart-money-signal-system
cd smart-money-signal-system

# Create virtual environment
uv venv
source .venv/bin/activate

# Add core dependencies
uv add redis pydantic structlog pydantic-settings python-dotenv

# Add ML dependencies (for Phase 4)
uv add scikit-learn pandas numpy joblib

# Add API dependencies
uv add fastapi uvicorn httpx

# Add dev dependencies
uv add --dev pytest pytest-asyncio mypy ruff black
```

**Effort**: 1 hour
**Priority**: CRITICAL

---

### Step 2.2: Create Directory Structure

```bash
mkdir -p src/signal_system/{ml,weighting_engine,signal_generation,whale_alerts,api}
mkdir -p tests/{unit,integration}
mkdir -p scripts
mkdir -p models
```

**Create Files**:
- `src/signal_system/__init__.py`
- `src/signal_system/__main__.py`
- `src/signal_system/config.py`
- `src/signal_system/event_subscriber.py`
- `src/signal_system/signal_store.py`
- `.env`
- `.env.example`

**Effort**: 1 hour
**Priority**: CRITICAL

---

### Step 2.3: Create Configuration

**File**: `src/signal_system/config.py`

**IMPORTANT:** The `channel_prefix` must be `"events"` to match the market-scraper's Redis publishing format:
```python
# market-scraper publishes to: "events:{event_type}"
# e.g., "events:trader_positions", "events:candles"
```

```python
"""Signal System Configuration."""

from pydantic_settings import BaseSettings
from pydantic import Field


class RedisSettings(BaseSettings):
    """Redis configuration."""

    url: str = Field(default="redis://localhost:6379/0")
    channel_prefix: str = Field(default="events")  # Matches market-scraper format

    class Config:
        env_prefix = "REDIS_"


class SignalSystemSettings(BaseSettings):
    """Main application settings."""

    redis: RedisSettings = Field(default_factory=RedisSettings)
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=4341)
    symbol: str = Field(default="BTC")

    class Config:
        env_file = ".env"


def get_settings() -> SignalSystemSettings:
    """Get application settings."""
    return SignalSystemSettings()
```

**File**: `.env.example`
```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_CHANNEL_PREFIX=events  # Must match market-scraper's "events:{type}" format

# API Configuration
API_HOST=0.0.0.0
API_PORT=4341

# Trading Configuration
SYMBOL=BTC
```

**Effort**: 30 minutes
**Priority**: CRITICAL

---

### Step 2.4: Create Event Subscriber

**File**: `src/signal_system/event_subscriber.py`

**IMPORTANT:** Market-scraper publishes events to `events:{event_type}` channels:
- `events:trader_positions` - Real-time trader position updates
- `events:candles` - OHLCV candle data
- `events:leaderboard` - Leaderboard snapshots

```python
"""Event Subscriber for market-scraper events."""

import asyncio
import json
from typing import Any, Callable

import redis.asyncio as redis
import structlog

from signal_system.config import RedisSettings

logger = structlog.get_logger(__name__)


class EventSubscriber:
    """Subscribes to market-scraper events via Redis.

    Channel format: "events:{event_type}"
    Example: "events:trader_positions"
    """

    def __init__(self, settings: RedisSettings) -> None:
        """Initialize the subscriber."""
        self.settings = settings
        self._redis: redis.Redis | None = None
        self._pubsub: redis.client.PubSub | None = None
        self._running = False
        self._handlers: dict[str, list[Callable]] = {}
        self._message_count = 0

    async def connect(self) -> None:
        """Connect to Redis."""
        self._redis = redis.from_url(self.settings.url)
        self._pubsub = self._redis.pubsub()
        logger.info("redis_connected", url=self.settings.url)

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
        logger.info("redis_disconnected")

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to an event type.

        Args:
            event_type: Event type (e.g., "trader_positions")
            handler: Async function to handle the event
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def start(self) -> None:
        """Start listening for events."""
        if not self._pubsub:
            raise RuntimeError("Not connected to Redis")

        self._running = True

        # Subscribe to channels: "events:{event_type}"
        # Uses pattern subscribe to match "events:trader_positions" etc.
        channels = [
            f"{self.settings.channel_prefix}:{event_type}"
            for event_type in self._handlers.keys()
        ]
        await self._pubsub.psubscribe(*channels)
        logger.info("channels_subscribed", channels=channels)

        # Start listening
        await self._listen_loop()

    async def _listen_loop(self) -> None:
        """Listen for Redis messages."""
        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )

                if message and message["type"] == "pmessage":
                    await self._process_message(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("listen_error", error=str(e), exc_info=True)
                await asyncio.sleep(1.0)

    async def _process_message(self, message: dict) -> None:
        """Process incoming message."""
        try:
            channel = message["channel"]
            data = json.loads(message["data"])

            # Extract event type from channel
            event_type = channel.decode().split(":")[-1]

            self._message_count += 1

            # Call handlers
            handlers = self._handlers.get(event_type, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    logger.error(
                        "handler_error",
                        event_type=event_type,
                        handler=handler.__name__,
                        error=str(e),
                    )

        except json.JSONDecodeError as e:
            logger.warning("invalid_json", error=str(e))
        except Exception as e:
            logger.error("process_error", error=str(e), exc_info=True)

    def get_stats(self) -> dict[str, Any]:
        """Get subscriber statistics."""
        return {
            "running": self._running,
            "message_count": self._message_count,
            "subscribed_events": list(self._handlers.keys()),
        }
```

**Effort**: 2 hours
**Priority**: CRITICAL

---

### Step 2.5: Create Basic Signal Processor

**File**: `src/signal_system/signal_generation/processor.py`

```python
"""Signal Generation Processor."""

from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SignalGenerationProcessor:
    """Generates trading signals from trader position data."""

    def __init__(self, symbol: str = "BTC") -> None:
        """Initialize the processor."""
        self.symbol = symbol
        self._trader_positions: dict[str, dict] = {}
        self._trader_scores: dict[str, float] = {}
        self._last_signal: dict | None = None
        self._signals_generated = 0

    async def process_position(self, event: dict) -> dict | None:
        """Process trader position event."""
        payload = event.get("payload", {})
        address = payload.get("address")

        if not address:
            return None

        # Store position
        self._trader_positions[address] = payload

        # Generate signal
        return self._generate_signal()

    async def process_scored_traders(self, event: dict) -> None:
        """Process scored traders event."""
        payload = event.get("payload", {})
        traders = payload.get("traders", [])

        for trader in traders:
            address = trader.get("address")
            score = trader.get("score", 50)
            if address:
                self._trader_scores[address] = score

    def _generate_signal(self) -> dict | None:
        """Generate aggregated signal."""
        if not self._trader_positions:
            return None

        long_score = 0.0
        short_score = 0.0
        total_weight = 0.0
        traders_long = 0
        traders_short = 0

        for address, position in self._trader_positions.items():
            score = self._trader_scores.get(address, 50)
            weight = score / 100

            # Get BTC position
            positions = position.get("positions", [])
            btc_position = None

            for pos in positions:
                pos_data = pos.get("position", pos)
                if pos_data.get("coin") == self.symbol:
                    btc_position = pos_data
                    break

            if btc_position:
                szi = float(btc_position.get("szi", 0))

                if szi > 0:
                    long_score += weight
                    traders_long += 1
                elif szi < 0:
                    short_score += weight
                    traders_short += 1

                total_weight += weight

        if total_weight == 0:
            return None

        long_bias = long_score / total_weight
        short_bias = short_score / total_weight
        net_bias = long_bias - short_bias

        # Determine action
        if net_bias > 0.2:
            action = "BUY"
        elif net_bias < -0.2:
            action = "SELL"
        else:
            action = "NEUTRAL"

        signal = {
            "symbol": self.symbol,
            "action": action,
            "confidence": min(abs(net_bias) * 2, 1.0),
            "long_bias": round(long_bias, 4),
            "short_bias": round(short_bias, 4),
            "net_bias": round(net_bias, 4),
            "traders_long": traders_long,
            "traders_short": traders_short,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Only emit if different from last signal
        if self._should_emit(signal):
            self._last_signal = signal
            self._signals_generated += 1
            return signal

        return None

    def _should_emit(self, signal: dict) -> bool:
        """Check if signal should be emitted."""
        if self._last_signal is None:
            return True

        if signal["action"] != self._last_signal.get("action"):
            return True

        bias_change = abs(signal["net_bias"] - self._last_signal.get("net_bias", 0))
        return bias_change >= 0.1

    def get_stats(self) -> dict[str, Any]:
        """Get processor statistics."""
        return {
            "signals_generated": self._signals_generated,
            "tracked_traders": len(self._trader_positions),
            "scored_traders": len(self._trader_scores),
        }
```

**Effort**: 2 hours
**Priority**: HIGH

---

### Phase 2 Deliverables

| Deliverable | Status | Verification |
|-------------|--------|--------------|
| Project initialized | ☐ | `uv run python -m signal_system` works |
| Event subscriber | ☐ | Receives events from Redis |
| Signal processor | ☐ | Generates signals |
| Tests passing | ☐ | pytest succeeds |

**Phase 2 Timeline**: 2-3 days
**Phase 2 Exit Criteria**: Signal system receives events and generates basic signals

---

## Phase 3: Multi-Dimensional Weighting (Week 2)

**Repository**: `smart-money-signal-system`
**Goal**: Implement advanced trader weighting engine

### Step 3.1: Create Weighting Configuration

**File**: `src/signal_system/weighting_engine/config.py`

```python
"""Weighting Configuration."""

from dataclasses import dataclass, field


@dataclass
class PerformanceWeightConfig:
    """Configuration for performance-based weighting."""
    sharpe_weight: float = 0.25
    sortino_weight: float = 0.20
    consistency_weight: float = 0.20
    max_drawdown_weight: float = 0.15
    win_rate_weight: float = 0.10
    profit_factor_weight: float = 0.10


@dataclass
class SizeWeightConfig:
    """Configuration for size-based weighting."""
    alpha_whale_threshold: float = 20_000_000
    whale_threshold: float = 10_000_000
    large_threshold: float = 5_000_000
    medium_threshold: float = 1_000_000
    standard_threshold: float = 100_000

    alpha_whale_weight: float = 3.0
    whale_weight: float = 2.5
    large_weight: float = 2.0
    medium_weight: float = 1.5
    standard_weight: float = 1.0
    small_weight: float = 0.5


@dataclass
class RecencyWeightConfig:
    """Configuration for recency-based weighting."""
    day_weight: float = 0.50
    week_weight: float = 0.30
    month_weight: float = 0.20
    min_recency: float = 0.5
    max_recency: float = 1.5


@dataclass
class WeightingConfig:
    """Master weighting configuration."""
    performance: PerformanceWeightConfig = field(default_factory=PerformanceWeightConfig)
    size: SizeWeightConfig = field(default_factory=SizeWeightConfig)
    recency: RecencyWeightConfig = field(default_factory=RecencyWeightConfig)

    performance_dimension_weight: float = 0.40
    size_dimension_weight: float = 0.30
    recency_dimension_weight: float = 0.20
    regime_dimension_weight: float = 0.10
```

**Effort**: 1 hour
**Priority**: HIGH

---

### Step 3.2: Create Weighting Engine

**File**: `src/signal_system/weighting_engine/engine.py`

(See IMPLEMENTATION_PLAN_V2.md for full 400-line implementation)

**Key Methods**:
- `calculate_weight(trader)` - Returns TraderWeight dataclass
- `_calc_performance_weight()` - Sharpe, Sortino, consistency
- `_calc_size_weight()` - Account value tiers
- `_calc_recency_weight()` - Day/week/month decay
- `_calc_regime_weight()` - Market condition alignment

**Effort**: 3 hours
**Priority**: HIGH

---

### Phase 3 Deliverables

| Deliverable | Status | Verification |
|-------------|--------|--------------|
| WeightingConfig | ☐ | Config loads correctly |
| TraderWeightingEngine | ☐ | Calculates weights |
| Integration | ☐ | Signals use weighted aggregation |

**Phase 3 Timeline**: 2-3 days
**Phase 3 Exit Criteria**: Multi-dimensional weighting active

---

## Phase 4: ML Components (Week 3-4)

**Repository**: `smart-money-signal-system`
**Goal**: Implement ML for feature discovery and regime detection

### Step 4.1: Feature Importance Analyzer

**File**: `src/signal_system/ml/feature_importance.py`

(See IMPLEMENTATION_PLAN_V2.md for full implementation)

**Key Features**:
- RandomForest for feature importance
- Cross-validation for robustness
- Model persistence with joblib

**Effort**: 2 hours
**Priority**: MEDIUM

---

### Step 4.2: Market Regime Detector

**File**: `src/signal_system/ml/regime_detection.py`

(See IMPLEMENTATION_PLAN_V2.md for full implementation)

**Key Features**:
- KMeans clustering for regime detection
- 6 regimes: deep_accumulation, early_bull, mid_bull, late_bull, distribution, bear
- Regime signal multipliers

**Effort**: 2 hours
**Priority**: MEDIUM

---

### Phase 4 Deliverables

| Deliverable | Status | Verification |
|-------------|--------|--------------|
| FeatureImportanceAnalyzer | ☐ | Trains and saves model |
| MarketRegimeDetector | ☐ | Detects regime |
| Training scripts | ☐ | Scripts run successfully |

**Phase 4 Timeline**: 3-4 days
**Phase 4 Exit Criteria**: ML models trained and integrated

---

## Phase 5: Whale Alert System (Week 4)

**Repository**: `smart-money-signal-system`
**Goal**: Real-time detection of whale position changes

### Step 5.1: Create Whale Alert Detector

**File**: `src/signal_system/whale_alerts/detector.py`

(See IMPLEMENTATION_PLAN_V2.md for full implementation)

**Alert Priorities**:
- CRITICAL: Alpha Whale ($20M+) position change
- HIGH: 2+ whales change within 5 min
- MEDIUM: Aggregate whale bias flips
- LOW: Elite consensus shifts 20%+

**Effort**: 2 hours
**Priority**: MEDIUM

---

### Phase 5 Deliverables

| Deliverable | Status | Verification |
|-------------|--------|--------------|
| WhaleAlertDetector | ☐ | Detects changes |
| Alert prioritization | ☐ | CRITICAL/HIGH/MEDIUM |
| Alert history API | ☐ | Recent alerts retrievable |

**Phase 5 Timeline**: 1-2 days
**Phase 5 Exit Criteria**: Whale alerts generated

---

## Phase 6: API and Integration (Week 5)

**Repository**: `smart-money-signal-system`
**Goal**: Expose signals and alerts via REST API

### Step 6.1: Create FastAPI Application

**File**: `src/signal_system/api/main.py`

```python
"""Signal System API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from signal_system.config import get_settings
from signal_system.api.routes import router as signals_router

settings = get_settings()

app = FastAPI(
    title="Smart Money Signal System",
    description="Real-time trading signals from whale position tracking",
    version="0.1.0",
)

# CORS - Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

**Effort**: 1 hour
**Priority**: HIGH

---

### Step 6.2: Create API Routes

**File**: `src/signal_system/api/routes.py`

**Endpoints**:
- `GET /api/v1/signals/latest` - Latest trading signal
- `GET /api/v1/signals/history` - Signal history
- `GET /api/v1/alerts/latest` - Latest whale alert
- `GET /api/v1/alerts/history` - Alert history

**Effort**: 1 hour
**Priority**: HIGH

---

### Phase 6 Deliverables

| Deliverable | Status | Verification |
|-------------|--------|--------------|
| FastAPI application | ☐ | Server starts |
| Signal endpoints | ☐ | GET /signals/latest works |
| Alert endpoints | ☐ | GET /alerts/latest works |
| Health check | ☐ | GET /health returns 200 |

**Phase 6 Timeline**: 1 day
**Phase 6 Exit Criteria**: API serving signals

---

## Summary

### Timeline Overview

| Phase | Duration | Repository | Key Deliverable | Status |
|-------|----------|------------|-----------------|--------|
| Phase 1 | ~~1-2 days~~ DONE | market-scraper | TraderWebSocket enabled | ✅ COMPLETE |
| Phase 2 | 2-3 days | smart-money-signal-system | Event subscriber | ☐ Pending |
| Phase 3 | 2-3 days | smart-money-signal-system | Weighting engine | ☐ Pending |
| Phase 4 | 3-4 days | smart-money-signal-system | ML components | ☐ Pending |
| Phase 5 | 1-2 days | smart-money-signal-system | Whale alerts | ☐ Pending |
| Phase 6 | 1 day | smart-money-signal-system | REST API | ☐ Pending |

**Total**: ~~5 weeks~~ 4 weeks remaining (Phase 1 complete)

### Critical Path

1. ~~**Phase 1** (market-scraper) - Must complete first~~ ✅ COMPLETE
2. **Phase 2** (signal-system) - Ready to start
3. **Phase 3-6** - Can proceed in parallel after Phase 2

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Signal Accuracy | >55% | Backtest vs historical |
| Alert Latency | <5 seconds | Time from change to alert |
| System Uptime | >99% | Health check monitoring |
| Trader Coverage | 300-500 | Active subscriptions |

### Phase 1 Completion Summary

**Completed:** 2026-02-24

**What was implemented:**
- `TraderWebSocketCollector` integrated into `lifecycle.py` (NOT `manager.py`)
- `get_tracked_addresses()` method added to `LeaderboardCollector`
- 500 traders subscribed via 5 WebSocket connections
- `trader_positions` events published to Redis channel `events:trader_positions`

**Key implementation notes:**
- Channel format is `events:{event_type}`, not `smart_money:{event_type}`
- `TraderWebSocketCollector` managed separately from `CollectorManager` due to different interface

---

*Final Implementation Plan V3.1*
*Updated: 2026-02-24*
*Phase 1 Complete - Ready for Phase 2*
*Ready for immediate implementation*
