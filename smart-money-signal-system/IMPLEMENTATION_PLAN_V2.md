# Smart Money Signal System - Implementation Plan V2

**Project**: Smart Money Signal System for BTC Trading
**Architecture**: Two-Repository (Data + Intelligence Separation)
**Timeline**: 5 Weeks
**Start Date**: 2026-02-24
**Status**: Ready for Implementation

---

## Executive Summary

This revised implementation plan adopts a **two-repository architecture** aligned with 2026 industry best practices (Nansen, Glassnode):

| Repository | Purpose | Dependencies |
|------------|---------|--------------|
| `market-scraper` | Data Infrastructure | `aiohttp`, `websockets`, `redis`, `motor` |
| `smart-money-signal-system` | Intelligence Layer | `scikit-learn`, `pandas`, `redis`, `fastapi` |

**Communication**: Redis Event Bus (publish/subscribe pattern)

**Key Benefits**:
- Independent deployment cycles
- ML iteration without affecting data pipeline
- Clean separation of concerns
- Easier A/B testing of models

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    market-scraper (Data Layer)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Hyperliquid  │  │   CBBI +     │  │   Event Publisher    │  │
│  │  WebSocket   │  │  On-Chain    │  │  (Redis Event Bus)   │  │
│  │  Collector   │  │  Connectors  │  │                      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Redis Pub/Sub
                              │ Events: trader_positions,
                              │         leaderboard, candles
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│             smart-money-signal-system (Intelligence Layer)      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Event      │  │   Weighting  │  │    ML Inference      │  │
│  │  Subscriber  │  │    Engine    │  │  (Regime, Features)  │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Signal     │  │   Whale      │  │      REST API        │  │
│  │  Generation  │  │   Alerts     │  │  (Signal Delivery)   │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │
                              ▼
                    ┌──────────────────┐
                    │  Trading API /   │
                    │    Dashboard     │
                    └──────────────────┘
```

---

## Phase 1: Data Infrastructure (Week 1)

**Repository**: `market-scraper`
**Goal**: Enable real-time trader position data publishing via Redis

### Step 1.1: Enable TraderWebSocketCollector

**File**: `market-scraper/src/market_scraper/connectors/hyperliquid/collectors/manager.py`

**Changes**:

```python
# Line 17-18: Add import
from market_scraper.connectors.hyperliquid.collectors.trader_ws import TraderWebSocketCollector

# Line 66-70: Register collector
collector_classes = {
    "candles": CandlesCollector,
    "trader_ws": TraderWebSocketCollector,  # NEW
}

# Line 220-250: Add channel mapping for trader_ws
channel_map = {
    "candle": "candles",
    "webData2": "trader_ws",  # NEW
}
```

**Testing**:
```bash
cd /home/muham/development/cryptodata/market-scraper
uv run pytest tests/connectors/hyperliquid/collectors/test_trader_ws.py -v
```

**Effort**: 2 hours
**Priority**: CRITICAL

---

### Step 1.2: Add get_tracked_addresses to LeaderboardCollector

**File**: `market-scraper/src/market_scraper/connectors/hyperliquid/collectors/leaderboard.py`

**Add Method** (after line 520):

```python
async def get_tracked_addresses(self) -> list[str]:
    """Get list of tracked trader addresses from database.

    Returns:
        List of Ethereum addresses currently being tracked
    """
    if self._db is None:
        # Fallback to in-memory tracked traders if no DB
        return list(self._tracked_traders.keys()) if hasattr(self, '_tracked_traders') else []
    
    try:
        from market_scraper.storage.models import CollectionName
        
        cursor = self._db[CollectionName.TRACKED_TRADERS].find(
            {"active": True},
            {"eth": 1, "_id": 0}
        )
        return [doc["eth"] async for doc in cursor]
    except Exception as e:
        logger.error("get_tracked_addresses_error", error=str(e))
        return []
```

**Testing**:
```bash
uv run pytest tests/connectors/hyperliquid/collectors/test_leaderboard.py::test_get_tracked_addresses -v
```

**Effort**: 1 hour
**Priority**: CRITICAL

---

### Step 1.3: Update Lifecycle Manager for Trader Subscription

**File**: `market-scraper/src/market_scraper/orchestration/lifecycle.py`

**Change 1** (Line 443): Enable trader_ws collector

```python
# Before
collectors=["candles"],

# After
collectors=["candles", "trader_ws"],
```

**Change 2** (After line 459): Add trader subscription

```python
# 6. Initialize Leaderboard Collector
await self._init_leaderboard_collector()
logger.info("leaderboard_collector_initialized")

# 6.1 Subscribe traders to position tracking (NEW)
await self._subscribe_tracked_traders()
logger.info("trader_position_subscriptions_complete")
```

**Change 3** (Add new method after line 465):

```python
async def _subscribe_tracked_traders(self) -> None:
    """Subscribe TraderWebSocket to leaderboard's tracked traders."""
    if not self._collector_manager or not self._leaderboard_collector:
        logger.warning("cannot_subscribe_traders_missing_components")
        return

    # Get tracked addresses from leaderboard collector
    tracked = await self._leaderboard_collector.get_tracked_addresses()

    if tracked:
        logger.info("subscribing_tracked_traders", count=len(tracked))
        
        # Get trader_ws collector from manager
        trader_ws_collector = None
        for collector in self._collector_manager._collectors.values():
            if collector.__class__.__name__ == "TraderWebSocketCollector":
                trader_ws_collector = collector
                break
        
        if trader_ws_collector:
            await trader_ws_collector.start(tracked)
            logger.info("trader_websocket_started", traders=len(tracked))
        else:
            logger.warning("trader_ws_collector_not_found")
```

**Testing**:
```bash
uv run pytest tests/orchestration/test_lifecycle.py -v
```

**Effort**: 2 hours
**Priority**: CRITICAL

---

### Step 1.4: Verify Redis Event Bus Configuration

**File**: `market-scraper/.env`

**Ensure Redis is configured**:

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# If Redis not available, falls back to MemoryEventBus
```

**Install Redis** (if not present):

```bash
sudo apt update
sudo apt install redis-server
sudo systemctl enable redis
sudo systemctl start redis
```

**Testing**:
```bash
redis-cli ping
# Should return: PONG
```

**Effort**: 30 minutes
**Priority**: CRITICAL

---

### Step 1.5: Test End-to-End Data Flow

**Test Script**: `market-scraper/scripts/test_data_flow.py`

```python
#!/usr/bin/env python3
"""Test end-to-end data flow from WebSocket to Redis."""

import asyncio
import redis.asyncio as redis

async def test_data_flow():
    # Subscribe to trader_positions channel
    r = redis.from_url("redis://localhost:6379/0")
    pubsub = r.pubsub()
    await pubsub.subscribe("trader_positions")
    
    print("Listening for trader_positions events...")
    
    # Wait for messages (timeout 60s)
    async for message in pubsub.listen():
        if message["type"] == "message":
            print(f"Received: {message['data']}")
            break
    
    await pubsub.unsubscribe("trader_positions")
    await r.close()

if __name__ == "__main__":
    asyncio.run(test_data_flow())
```

**Run Test**:
```bash
cd market-scraper
uv run python scripts/test_data_flow.py
```

**Expected Output**:
```
Listening for trader_positions events...
Received: {"event_type": "trader_positions", "payload": {...}}
```

**Effort**: 1 hour
**Priority**: HIGH

---

### Phase 1 Deliverables

| Deliverable | Status | Verification |
|-------------|--------|--------------|
| TraderWebSocketCollector enabled | ☐ | Collector starts without errors |
| Trader subscription from leaderboard | ☐ | 100+ traders subscribed |
| Redis event publishing | ☐ | trader_positions events visible in Redis |
| End-to-end test passing | ☐ | test_data_flow.py succeeds |

**Phase 1 Timeline**: 1-2 days
**Phase 1 Exit Criteria**: Real-time trader positions flowing to Redis

---

## Phase 2: Signal System Foundation (Week 1-2)

**Repository**: `smart-money-signal-system`
**Goal**: Create new repository with event subscription and basic signal generation

### Step 2.1: Initialize Project Structure

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

### Step 2.2: Create Project Structure

**Directory Structure**:

```
smart-money-signal-system/
├── pyproject.toml
├── .env
├── .env.example
├── src/signal_system/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── event_subscriber.py
│   ├── signal_store.py
│   ├── weighting_engine/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── engine.py
│   ├── signal_generation/
│   │   ├── __init__.py
│   │   └── processor.py
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── feature_importance.py
│   │   └── regime_detection.py
│   └── api/
│       ├── __init__.py
│       ├── main.py
│       └── routes.py
├── tests/
│   ├── __init__.py
│   ├── test_event_subscriber.py
│   ├── test_weighting_engine.py
│   └── test_signal_generation.py
└── scripts/
    ├── train_features.py
    └── train_regime.py
```

**Effort**: 1 hour
**Priority**: CRITICAL

---

### Step 2.3: Create Configuration

**File**: `src/signal_system/config.py`

```python
"""Signal System Configuration."""

from pydantic_settings import BaseSettings
from pydantic import Field


class RedisSettings(BaseSettings):
    """Redis configuration."""
    
    url: str = Field(default="redis://localhost:6379/0")
    channel_prefix: str = Field(default="smart_money")
    
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
REDIS_CHANNEL_PREFIX=smart_money

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
    """Subscribes to market-scraper events via Redis."""

    def __init__(self, settings: RedisSettings) -> None:
        """Initialize the subscriber.

        Args:
            settings: Redis configuration
        """
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
            event_type: Event type to subscribe to
            handler: Async callback function
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info("event_subscribed", event_type=event_type)

    async def start(self) -> None:
        """Start listening for events."""
        if not self._pubsub:
            raise RuntimeError("Not connected to Redis")

        self._running = True

        # Subscribe to all channels
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
        """Process incoming message.

        Args:
            message: Redis message
        """
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
        """Initialize the processor.

        Args:
            symbol: Trading symbol
        """
        self.symbol = symbol
        self._trader_positions: dict[str, dict] = {}
        self._trader_scores: dict[str, float] = {}
        self._last_signal: dict | None = None
        self._signals_generated = 0

    async def process_position(self, event: dict) -> dict | None:
        """Process trader position event.

        Args:
            event: Event data

        Returns:
            Signal dict or None
        """
        payload = event.get("payload", {})
        address = payload.get("address")

        if not address:
            return None

        # Store position
        self._trader_positions[address] = payload

        # Generate signal
        return self._generate_signal()

    async def process_scored_traders(self, event: dict) -> None:
        """Process scored traders event.

        Args:
            event: Event data
        """
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
| Project initialized with uv | ☐ | `uv run python -m signal_system` works |
| Event subscriber working | ☐ | Receives events from Redis |
| Basic signal processor | ☐ | Generates signals from positions |
| Tests passing | ☐ | pytest succeeds |

**Phase 2 Timeline**: 2-3 days
**Phase 2 Exit Criteria**: Signal system receives events and generates basic signals

---

## Phase 3: Multi-Dimensional Weighting (Week 2-3)

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

    # Dimension weights in composite
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

```python
"""Trader Weighting Engine."""

from dataclasses import dataclass
from typing import Any

import structlog

from signal_system.weighting_engine.config import WeightingConfig

logger = structlog.get_logger(__name__)


@dataclass
class TraderWeight:
    """Multi-dimensional trader weight."""

    performance: float  # 0-100 scale
    size: float  # 0.5-3.0 scale
    recency: float  # 0.5-1.5 scale
    regime: float  # 0.8-1.2 scale
    composite: float  # Final combined weight
    tier: str  # Classification
    score: float  # Original score


class TraderWeightingEngine:
    """Calculate multi-dimensional trader weights."""

    def __init__(self, config: WeightingConfig | None = None) -> None:
        """Initialize the weighting engine."""
        self.config = config or WeightingConfig()
        self._market_regime = "unknown"
        self._trader_weights: dict[str, TraderWeight] = {}

    def set_market_regime(self, regime: str) -> None:
        """Update current market regime."""
        self._market_regime = regime
        self._trader_weights.clear()

    def calculate_weight(self, trader: dict[str, Any]) -> TraderWeight:
        """Calculate all weight dimensions for a trader."""
        address = trader.get("ethAddress", "")

        if address in self._trader_weights:
            return self._trader_weights[address]

        # Calculate each dimension
        performance = self._calc_performance_weight(trader)
        size = self._calc_size_weight(trader)
        recency = self._calc_recency_weight(trader)
        regime = self._calc_regime_weight(trader)

        # Calculate composite
        composite = (
            performance * self.config.performance_dimension_weight
            + size * self.config.size_dimension_weight
            + recency * self.config.recency_dimension_weight
            + regime * self.config.regime_dimension_weight
        )

        # Determine tier
        tier = self._classify_tier(size, performance)

        weight = TraderWeight(
            performance=performance,
            size=size,
            recency=recency,
            regime=regime,
            composite=composite,
            tier=tier,
            score=trader.get("score", 50),
        )

        self._trader_weights[address] = weight
        return weight

    def _calc_performance_weight(self, trader: dict) -> float:
        """Calculate risk-adjusted performance score (0-100)."""
        cfg = self.config.performance

        sharpe = self._estimate_sharpe(trader)
        sortino = self._estimate_sortino(trader)
        consistency = self._calc_consistency(trader)
        max_dd = self._estimate_max_drawdown(trader)
        win_rate = self._estimate_win_rate(trader)
        profit_factor = self._estimate_profit_factor(trader)

        score = (
            sharpe * cfg.sharpe_weight
            + sortino * cfg.sortino_weight
            + consistency * cfg.consistency_weight
            + (1 - min(max_dd, 1.0)) * cfg.max_drawdown_weight
            + win_rate * cfg.win_rate_weight
            + profit_factor * cfg.profit_factor_weight
        )

        return min(max(score * 100, 0), 100)

    def _calc_size_weight(self, trader: dict) -> float:
        """Calculate size-based weight multiplier (0.5-3.0)."""
        cfg = self.config.size
        account_value = float(trader.get("accountValue", 0))

        if account_value >= cfg.alpha_whale_threshold:
            return cfg.alpha_whale_weight
        elif account_value >= cfg.whale_threshold:
            return cfg.whale_weight
        elif account_value >= cfg.large_threshold:
            return cfg.large_weight
        elif account_value >= cfg.medium_threshold:
            return cfg.medium_weight
        elif account_value >= cfg.standard_threshold:
            return cfg.standard_weight
        else:
            return cfg.small_weight

    def _calc_recency_weight(self, trader: dict) -> float:
        """Calculate recency-based weight (0.5-1.5)."""
        cfg = self.config.recency

        performances = trader.get("performances", {})

        day_roi = performances.get("day", {}).get("roi", 0)
        week_roi = performances.get("week", {}).get("roi", 0)
        month_roi = performances.get("month", {}).get("roi", 0)

        recency_score = (
            day_roi * cfg.day_weight
            + week_roi * cfg.week_weight
            + month_roi * cfg.month_weight
        )

        normalized = min(abs(recency_score), 1.0)
        return cfg.min_recency + (normalized * (cfg.max_recency - cfg.min_recency))

    def _calc_regime_weight(self, trader: dict) -> float:
        """Calculate regime alignment weight (0.8-1.2)."""
        base = 1.0

        if self._market_regime == "high_volatility":
            consistency = self._calc_consistency(trader)
            base = 0.8 + (consistency * 0.4)
        elif self._market_regime == "trending":
            performances = trader.get("performances", {})
            trend_score = performances.get("month", {}).get("roi", 0)
            base = 0.8 + min(abs(trend_score) * 0.4, 0.4)
        elif self._market_regime == "ranging":
            base = 0.9

        return min(max(base, 0.8), 1.2)

    def _classify_tier(self, size_weight: float, performance: float) -> str:
        """Classify trader into tier."""
        if size_weight >= 3.0 and performance >= 80:
            return "alpha_whale"
        elif size_weight >= 2.5 and performance >= 70:
            return "whale"
        elif size_weight >= 2.0 and performance >= 65:
            return "large"
        elif performance >= 60:
            return "elite"
        elif performance >= 50:
            return "standard"
        else:
            return "small"

    # --- Estimation methods ---

    def _estimate_sharpe(self, trader: dict) -> float:
        """Estimate Sharpe ratio from available data."""
        performances = trader.get("performances", {})

        returns = [
            performances.get("day", {}).get("roi", 0),
            performances.get("week", {}).get("roi", 0) / 7,
            performances.get("month", {}).get("roi", 0) / 30,
        ]

        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        volatility = variance**0.5 if variance > 0 else 0.01

        return avg_return / volatility if volatility > 0 else 0

    def _estimate_sortino(self, trader: dict) -> float:
        """Estimate Sortino ratio (downside deviation)."""
        performances = trader.get("performances", {})

        returns = [
            performances.get("day", {}).get("roi", 0),
            performances.get("week", {}).get("roi", 0) / 7,
            performances.get("month", {}).get("roi", 0) / 30,
        ]

        avg_return = sum(returns) / len(returns)
        negative_returns = [r for r in returns if r < 0]

        if negative_returns:
            downside_variance = sum(r**2 for r in negative_returns) / len(negative_returns)
            downside_dev = downside_variance**0.5
        else:
            downside_dev = 0.01

        return avg_return / downside_dev if downside_dev > 0 else 1.0

    def _calc_consistency(self, trader: dict) -> float:
        """Calculate consistency score (0-1)."""
        performances = trader.get("performances", {})

        timeframes = ["day", "week", "month", "allTime"]
        positive_count = sum(
            1 for tf in timeframes if performances.get(tf, {}).get("roi", 0) > 0
        )

        return positive_count / len(timeframes)

    def _estimate_max_drawdown(self, trader: dict) -> float:
        """Estimate max drawdown from available data."""
        score = trader.get("score", 50)

        if score >= 90:
            return 0.10
        elif score >= 80:
            return 0.15
        elif score >= 70:
            return 0.20
        elif score >= 60:
            return 0.25
        else:
            return 0.30

    def _estimate_win_rate(self, trader: dict) -> float:
        """Estimate win rate from ROI patterns."""
        performances = trader.get("performances", {})

        day_roi = performances.get("day", {}).get("roi", 0)
        week_roi = performances.get("week", {}).get("roi", 0)

        if day_roi > 0 and week_roi > 0:
            return 0.55 + min(abs(day_roi) * 2, 0.35)
        elif day_roi > 0 or week_roi > 0:
            return 0.50
        else:
            return 0.45

    def _estimate_profit_factor(self, trader: dict) -> float:
        """Estimate profit factor."""
        performances = trader.get("performances", {})
        all_time_roi = performances.get("allTime", {}).get("roi", 0)

        if all_time_roi > 1:
            return 2.0
        elif all_time_roi > 0.5:
            return 1.5
        elif all_time_roi > 0:
            return 1.2
        else:
            return 0.8
```

**Effort**: 3 hours
**Priority**: HIGH

---

### Phase 3 Deliverables

| Deliverable | Status | Verification |
|-------------|--------|--------------|
| WeightingConfig dataclasses | ☐ | Config loads correctly |
| TraderWeightingEngine | ☐ | Calculates weights for test traders |
| Integration with signal processor | ☐ | Signals use weighted aggregation |
| Unit tests | ☐ | All tests passing |

**Phase 3 Timeline**: 2-3 days
**Phase 3 Exit Criteria**: Multi-dimensional weighting active in signal generation

---

## Phase 4: ML Components (Week 3-4)

**Repository**: `smart-money-signal-system`
**Goal**: Implement ML for feature discovery and regime detection

### Step 4.1: Create Feature Importance Analyzer

**File**: `src/signal_system/ml/feature_importance.py`

```python
"""Feature Importance Analyzer."""

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import structlog
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

logger = structlog.get_logger(__name__)


class FeatureImportanceAnalyzer:
    """Analyzes which trader metrics are most predictive of success."""

    FEATURE_NAMES = [
        "sharpe_ratio",
        "sortino_ratio",
        "max_drawdown",
        "win_rate",
        "profit_factor",
        "consistency_score",
        "avg_leverage",
        "position_concentration",
        "day_roi",
        "week_roi",
        "month_roi",
        "all_time_roi",
        "account_value",
        "total_volume",
        "trade_frequency",
    ]

    def __init__(self, model_path: Path | None = None) -> None:
        """Initialize the analyzer."""
        self.model_path = model_path
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
        )
        self.scaler = StandardScaler()
        self._trained = False
        self._feature_importance: pd.Series | None = None

    def prepare_features(self, traders: list[dict]) -> np.ndarray:
        """Extract feature matrix from trader data."""
        features = []

        for trader in traders:
            performances = trader.get("performances", {})
            row = [
                self._calc_sharpe(trader),
                self._calc_sortino(trader),
                self._estimate_max_dd(trader),
                self._estimate_win_rate(trader),
                self._estimate_profit_factor(trader),
                self._calc_consistency(trader),
                trader.get("avg_leverage", 1),
                trader.get("position_concentration", 0.5),
                performances.get("day", {}).get("roi", 0),
                performances.get("week", {}).get("roi", 0),
                performances.get("month", {}).get("roi", 0),
                performances.get("allTime", {}).get("roi", 0),
                np.log1p(trader.get("accountValue", 0)),
                np.log1p(trader.get("totalVolume", 0)),
                trader.get("tradeCount", 0) / max(trader.get("tradingDays", 1), 1),
            ]
            features.append(row)

        return np.array(features)

    def train(
        self,
        traders: list[dict],
        labels: list[int],
        test_size: float = 0.2,
    ) -> dict[str, Any]:
        """Train the feature importance model."""
        X = self.prepare_features(traders)
        y = np.array(labels)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )

        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        self.model.fit(X_train_scaled, y_train)
        self._trained = True

        self._feature_importance = pd.Series(
            self.model.feature_importances_,
            index=self.FEATURE_NAMES,
        ).sort_values(ascending=False)

        cv_scores = cross_val_score(
            self.model, X_train_scaled, y_train, cv=5, scoring="roc_auc"
        )

        test_score = self.model.score(X_test_scaled, y_test)

        metrics = {
            "train_accuracy": float(self.model.score(X_train_scaled, y_train)),
            "test_accuracy": float(test_score),
            "cv_auc_mean": float(cv_scores.mean()),
            "cv_auc_std": float(cv_scores.std()),
            "feature_importance": self._feature_importance.to_dict(),
        }

        logger.info(
            "feature_importance_trained",
            test_accuracy=round(test_score, 3),
            cv_auc=round(cv_scores.mean(), 3),
        )

        if self.model_path:
            self._save_model()

        return metrics

    def get_feature_importance(self) -> pd.Series:
        """Get feature importance rankings."""
        if self._feature_importance is None:
            raise ValueError("Model not trained yet")
        return self._feature_importance

    def _save_model(self) -> None:
        """Save trained model to disk."""
        if self.model_path:
            joblib.dump(
                {"model": self.model, "scaler": self.scaler},
                self.model_path,
            )
            logger.info("model_saved", path=str(self.model_path))

    def load_model(self) -> None:
        """Load trained model from disk."""
        if self.model_path and self.model_path.exists():
            data = joblib.load(self.model_path)
            self.model = data["model"]
            self.scaler = data["scaler"]
            self._trained = True
            logger.info("model_loaded", path=str(self.model_path))

    # Helper methods (same as weighting engine)
    def _calc_sharpe(self, trader: dict) -> float:
        """Estimate Sharpe ratio."""
        performances = trader.get("performances", {})
        returns = [
            performances.get("day", {}).get("roi", 0),
            performances.get("week", {}).get("roi", 0) / 7,
            performances.get("month", {}).get("roi", 0) / 30,
        ]
        avg_return = np.mean(returns)
        volatility = np.std(returns) if np.std(returns) > 0 else 0.01
        return avg_return / volatility

    def _calc_sortino(self, trader: dict) -> float:
        """Estimate Sortino ratio."""
        performances = trader.get("performances", {})
        returns = [
            performances.get("day", {}).get("roi", 0),
            performances.get("week", {}).get("roi", 0) / 7,
            performances.get("month", {}).get("roi", 0) / 30,
        ]
        avg_return = np.mean(returns)
        negative = [r for r in returns if r < 0]
        if negative:
            downside = np.sqrt(np.mean([r**2 for r in negative]))
        else:
            downside = 0.01
        return avg_return / downside

    def _estimate_max_dd(self, trader: dict) -> float:
        """Estimate max drawdown."""
        score = trader.get("score", 50)
        if score >= 90:
            return 0.1
        elif score >= 70:
            return 0.2
        else:
            return 0.3

    def _estimate_win_rate(self, trader: dict) -> float:
        """Estimate win rate."""
        performances = trader.get("performances", {})
        day_roi = performances.get("day", {}).get("roi", 0)
        week_roi = performances.get("week", {}).get("roi", 0)
        if day_roi > 0 and week_roi > 0:
            return 0.55 + min(abs(day_roi) * 2, 0.35)
        return 0.5

    def _estimate_profit_factor(self, trader: dict) -> float:
        """Estimate profit factor."""
        performances = trader.get("performances", {})
        roi = performances.get("allTime", {}).get("roi", 0)
        if roi > 1:
            return 2.0
        elif roi > 0.5:
            return 1.5
        elif roi > 0:
            return 1.2
        return 0.8

    def _calc_consistency(self, trader: dict) -> float:
        """Calculate consistency."""
        performances = trader.get("performances", {})
        timeframes = ["day", "week", "month", "allTime"]
        positive = sum(1 for tf in timeframes if performances.get(tf, {}).get("roi", 0) > 0)
        return positive / len(timeframes)
```

**Effort**: 2 hours
**Priority**: MEDIUM

---

### Step 4.2: Create Market Regime Detector

**File**: `src/signal_system/ml/regime_detection.py`

```python
"""Market Regime Detection."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import structlog
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = structlog.get_logger(__name__)


class MarketRegimeDetector:
    """Identifies market regime from on-chain and price metrics."""

    REGIME_LABELS = {
        0: "deep_accumulation",
        1: "early_bull",
        2: "mid_bull",
        3: "late_bull",
        4: "distribution",
        5: "bear",
    }

    REGIME_SIGNALS = {
        "deep_accumulation": 1.5,
        "early_bull": 1.0,
        "mid_bull": 0.5,
        "late_bull": 0.0,
        "distribution": -1.0,
        "bear": -0.5,
    }

    def __init__(self, n_regimes: int = 6, model_path: Path | None = None) -> None:
        """Initialize the detector."""
        self.n_regimes = n_regimes
        self.model_path = model_path

        self.model = KMeans(
            n_clusters=n_regimes,
            random_state=42,
            n_init=10,
        )
        self.scaler = StandardScaler()

        self._trained = False
        self._current_regime = "unknown"
        self._cluster_to_regime: dict[int, str] = {}

    def prepare_features(self, data: list[dict]) -> np.ndarray:
        """Extract regime features from on-chain data."""
        features = []

        for d in data:
            row = [
                d.get("cbbi", 0.5),
                d.get("fear_greed", 50) / 100,
                d.get("sopr", 1.0),
                d.get("mvrv", 1.0),
                d.get("nupl", 0),
                d.get("volatility_30d", 0.02),
                d.get("exchange_netflow_ratio", 0),
                d.get("sth_sopr", 1.0),
                d.get("lth_sopr", 1.0),
            ]
            features.append(row)

        return np.array(features)

    def train(self, historical_data: list[dict]) -> dict[str, Any]:
        """Train regime detection model."""
        X = self.prepare_features(historical_data)
        X_scaled = self.scaler.fit_transform(X)

        self.model.fit(X_scaled)
        self._trained = True

        self._label_clusters(X_scaled)

        metrics = {
            "n_samples": len(X),
            "cluster_centers": self.model.cluster_centers_.tolist(),
            "labels": self.model.labels_.tolist(),
        }

        logger.info("regime_detector_trained", n_samples=len(X))

        if self.model_path:
            self._save_model()

        return metrics

    def _label_clusters(self, X_scaled: np.ndarray) -> None:
        """Assign meaningful labels to clusters."""
        centers = self.scaler.inverse_transform(self.model.cluster_centers_)
        cbbi_values = centers[:, 0]
        sorted_indices = np.argsort(cbbi_values)

        self._cluster_to_regime = {}
        for label, idx in enumerate(sorted_indices):
            if label < 6:
                self._cluster_to_regime[idx] = self.REGIME_LABELS[label]

    def detect_regime(self, current_data: dict) -> str:
        """Identify current market regime."""
        if not self._trained:
            raise ValueError("Model not trained yet")

        X = self.prepare_features([current_data])
        X_scaled = self.scaler.transform(X)

        cluster = self.model.predict(X_scaled)[0]
        regime = self._cluster_to_regime.get(cluster, "unknown")

        self._current_regime = regime
        return regime

    def get_regime_signal(self, regime: str | None = None) -> float:
        """Get signal multiplier for regime."""
        regime = regime or self._current_regime
        return self.REGIME_SIGNALS.get(regime, 0.0)

    def _save_model(self) -> None:
        """Save trained model to disk."""
        if self.model_path:
            joblib.dump(
                {
                    "model": self.model,
                    "scaler": self.scaler,
                    "cluster_to_regime": self._cluster_to_regime,
                },
                self.model_path,
            )
            logger.info("model_saved", path=str(self.model_path))

    def load_model(self) -> None:
        """Load trained model from disk."""
        if self.model_path and self.model_path.exists():
            data = joblib.load(self.model_path)
            self.model = data["model"]
            self.scaler = data["scaler"]
            self._cluster_to_regime = data["cluster_to_regime"]
            self._trained = True
            logger.info("model_loaded", path=str(self.model_path))
```

**Effort**: 2 hours
**Priority**: MEDIUM

---

### Step 4.3: Create Training Scripts

**File**: `scripts/train_features.py`

```python
#!/usr/bin/env python3
"""Train feature importance model."""

import asyncio
from pathlib import Path

import structlog

from signal_system.ml.feature_importance import FeatureImportanceAnalyzer
from signal_system.config import get_settings

logger = structlog.get_logger(__name__)


async def main():
    """Main training function."""
    settings = get_settings()

    # Load historical trader data from MongoDB
    # This is a placeholder - implement based on your data storage
    traders = []  # Load from database
    labels = []  # Generate labels (1 = profitable next period)

    if not traders:
        logger.warning("no_training_data")
        return

    # Initialize analyzer
    model_dir = Path("models")
    model_dir.mkdir(exist_ok=True)

    analyzer = FeatureImportanceAnalyzer(model_path=model_dir / "feature_importance.joblib")

    # Train model
    metrics = analyzer.train(traders, labels, test_size=0.2)

    logger.info(
        "training_complete",
        test_accuracy=metrics["test_accuracy"],
        cv_auc=metrics["cv_auc_mean"],
    )

    # Log top features
    top_features = analyzer.get_top_features(n=5)
    for feature, importance in top_features:
        logger.info("top_feature", feature=feature, importance=importance)


if __name__ == "__main__":
    asyncio.run(main())
```

**Effort**: 1 hour
**Priority**: MEDIUM

---

### Phase 4 Deliverables

| Deliverable | Status | Verification |
|-------------|--------|--------------|
| FeatureImportanceAnalyzer | ☐ | Trains and saves model |
| MarketRegimeDetector | ☐ | Detects regime from data |
| Training scripts | ☐ | Scripts run successfully |
| Model registry | ☐ | Models saved and loadable |

**Phase 4 Timeline**: 3-4 days
**Phase 4 Exit Criteria**: ML models trained and integrated into weighting engine

---

## Phase 5: Whale Alert System (Week 4-5)

**Repository**: `smart-money-signal-system`
**Goal**: Real-time detection of significant whale position changes

### Step 5.1: Create Whale Alert Detector

**File**: `src/signal_system/whale_alerts/detector.py`

```python
"""Whale Alert Detection System."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class WhaleAlert:
    """Whale alert data."""

    alert_type: str
    priority: str
    timestamp: datetime
    trader_address: str
    trader_name: str | None
    tier: str
    account_value: float
    coin: str
    previous_direction: str
    current_direction: str
    previous_size: float
    current_size: float
    change_type: str
    market_context: dict
    recommendation: str


class WhaleAlertDetector:
    """Detects significant whale position changes."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the detector."""
        self._config = config or {}

        self._alpha_whale_threshold = self._config.get("alpha_whale_threshold", 20_000_000)
        self._whale_threshold = self._config.get("whale_threshold", 10_000_000)
        self._elite_threshold = self._config.get("elite_threshold", 80)

        self._last_positions: dict[str, dict] = {}
        self._recent_alerts: list[WhaleAlert] = []
        self._alerts_generated = 0

    def process_position(self, payload: dict, trader_data: dict) -> WhaleAlert | None:
        """Process position update and detect whale alerts."""
        address = payload.get("address")

        if not address:
            return None

        current = self._extract_btc_position(payload)
        account_value = float(trader_data.get("accountValue", 0))
        score = trader_data.get("score", 0)

        is_alpha_whale = account_value >= self._alpha_whale_threshold
        is_whale = account_value >= self._whale_threshold
        is_elite = score >= self._elite_threshold

        if not (is_whale or is_elite):
            self._last_positions[address] = current
            return None

        previous = self._last_positions.get(address)

        if previous and self._is_significant_change(previous, current):
            alert = self._create_alert(
                address=address,
                trader_data=trader_data,
                previous=previous,
                current=current,
                is_alpha_whale=is_alpha_whale,
                is_whale=is_whale,
                is_elite=is_elite,
            )

            if alert:
                self._alerts_generated += 1
                self._recent_alerts.append(alert)
                self._prune_old_alerts()
                return alert

        self._last_positions[address] = current
        return None

    def _extract_btc_position(self, payload: dict) -> dict:
        """Extract BTC position."""
        positions = payload.get("positions", [])

        for pos in positions:
            pos_data = pos.get("position", pos)
            if pos_data.get("coin") == "BTC":
                szi = float(pos_data.get("szi", 0))
                return {
                    "direction": "LONG" if szi > 0 else ("SHORT" if szi < 0 else "NEUTRAL"),
                    "size": abs(szi),
                    "value": float(pos_data.get("positionValue", 0)),
                }

        return {"direction": "NEUTRAL", "size": 0, "value": 0}

    def _is_significant_change(self, previous: dict, current: dict) -> bool:
        """Check if position change is significant."""
        if previous["direction"] != current["direction"]:
            return True

        if previous["size"] > 0 and current["size"] > 0:
            size_change = abs(current["size"] - previous["size"]) / previous["size"]
            if size_change > 0.2:
                return True

        if previous["direction"] == "NEUTRAL" and current["direction"] != "NEUTRAL":
            return True

        if previous["direction"] != "NEUTRAL" and current["direction"] == "NEUTRAL":
            return True

        return False

    def _create_alert(
        self,
        address: str,
        trader_data: dict,
        previous: dict,
        current: dict,
        is_alpha_whale: bool,
        is_whale: bool,
        is_elite: bool,
    ) -> WhaleAlert:
        """Create whale alert."""
        if is_alpha_whale:
            priority = "CRITICAL"
        elif is_whale:
            priority = "HIGH"
        else:
            priority = "MEDIUM"

        if previous["direction"] != current["direction"]:
            if previous["direction"] == "NEUTRAL":
                change_type = "ENTRY"
            elif current["direction"] == "NEUTRAL":
                change_type = "EXIT"
            else:
                change_type = "REVERSAL"
        else:
            change_type = "SIZE_CHANGE"

        recommendation = self._generate_recommendation(priority, change_type, current["direction"])

        return WhaleAlert(
            alert_type="WHALE_POSITION_CHANGE",
            priority=priority,
            timestamp=datetime.now(UTC),
            trader_address=address,
            trader_name=trader_data.get("displayName"),
            tier="alpha_whale" if is_alpha_whale else ("whale" if is_whale else "elite"),
            account_value=account_value,
            coin="BTC",
            previous_direction=previous["direction"],
            current_direction=current["direction"],
            previous_size=previous["size"],
            current_size=current["size"],
            change_type=change_type,
            market_context=self._calculate_market_context(),
            recommendation=recommendation,
        )

    def _generate_recommendation(self, priority: str, change_type: str, direction: str) -> str:
        """Generate action recommendation."""
        if priority == "CRITICAL":
            if change_type == "REVERSAL":
                return f"STRONG {'BUY' if direction == 'LONG' else 'SELL'} - Alpha whale reversed"
            elif change_type == "ENTRY":
                return f"ALERT - Alpha whale entered {direction}"
            elif change_type == "EXIT":
                return "ALERT - Alpha whale exited position"
        elif priority == "HIGH":
            return f"Whale {'BUY' if direction == 'LONG' else 'SELL'} signal"
        return f"Monitor - Elite trader {change_type.lower()}"

    def _calculate_market_context(self) -> dict:
        """Calculate current market context."""
        whale_long = sum(1 for p in self._last_positions.values() if p["direction"] == "LONG")
        whale_short = sum(1 for p in self._last_positions.values() if p["direction"] == "SHORT")
        total = whale_long + whale_short
        whale_bias = (whale_long - whale_short) / total if total > 0 else 0

        return {
            "whale_bias": round(whale_bias, 3),
            "whales_long": whale_long,
            "whales_short": whale_short,
        }

    def _prune_old_alerts(self, max_age_hours: int = 24) -> None:
        """Remove old alerts."""
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        self._recent_alerts = [a for a in self._recent_alerts if a.timestamp > cutoff]

    def get_recent_alerts(self, hours: int = 24, priority: str | None = None) -> list[dict]:
        """Get recent alerts."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)

        alerts = [
            {
                "alert_type": a.alert_type,
                "priority": a.priority,
                "timestamp": a.timestamp.isoformat(),
                "trader_address": a.trader_address,
                "trader_name": a.trader_name,
                "tier": a.tier,
                "account_value": a.account_value,
                "coin": a.coin,
                "change_type": a.change_type,
                "previous_direction": a.previous_direction,
                "current_direction": a.current_direction,
                "recommendation": a.recommendation,
            }
            for a in self._recent_alerts
            if a.timestamp > cutoff
        ]

        if priority:
            alerts = [a for a in alerts if a["priority"] == priority]

        return sorted(alerts, key=lambda x: x["timestamp"], reverse=True)
```

**Effort**: 2 hours
**Priority**: MEDIUM

---

### Phase 5 Deliverables

| Deliverable | Status | Verification |
|-------------|--------|--------------|
| WhaleAlertDetector | ☐ | Detects whale position changes |
| Alert prioritization | ☐ | CRITICAL/HIGH/MEDIUM working |
| Alert history API | ☐ | Recent alerts retrievable |
| Integration with signal system | ☐ | Alerts emitted via Redis |

**Phase 5 Timeline**: 1-2 days
**Phase 5 Exit Criteria**: Whale alerts generated and accessible via API

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

# CORS - Allow all origins (per requirements)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(signals_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Smart Money Signal System",
        "version": "0.1.0",
        "docs": "/docs",
    }
```

**Effort**: 1 hour
**Priority**: HIGH

---

### Step 6.2: Create API Routes

**File**: `src/signal_system/api/routes.py`

```python
"""API Routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Global state (in production, use database)
_signals = []
_alerts = []


class SignalResponse(BaseModel):
    """Signal response model."""

    symbol: str
    action: str
    confidence: float
    long_bias: float
    short_bias: float
    net_bias: float
    traders_long: int
    traders_short: int
    timestamp: str


class AlertResponse(BaseModel):
    """Alert response model."""

    alert_type: str
    priority: str
    timestamp: str
    trader_address: str
    tier: str
    change_type: str
    recommendation: str


@router.get("/signals/latest", response_model=SignalResponse)
async def get_latest_signal():
    """Get latest trading signal."""
    if not _signals:
        raise HTTPException(status_code=404, detail="No signals available")
    return _signals[-1]


@router.get("/signals/history", response_model=list[SignalResponse])
async def get_signal_history(limit: int = 100):
    """Get signal history."""
    return _signals[-limit:]


@router.get("/alerts/latest", response_model=AlertResponse)
async def get_latest_alert(priority: str | None = None):
    """Get latest whale alert."""
    if not _alerts:
        raise HTTPException(status_code=404, detail="No alerts available")

    if priority:
        filtered = [a for a in _alerts if a["priority"] == priority]
        if not filtered:
            raise HTTPException(status_code=404, detail=f"No {priority} alerts available")
        return filtered[-1]

    return _alerts[-1]


@router.get("/alerts/history", response_model=list[AlertResponse])
async def get_alert_history(limit: int = 100, priority: str | None = None):
    """Get alert history."""
    if priority:
        filtered = [a for a in _alerts if a["priority"] == priority]
        return filtered[-limit:]
    return _alerts[-limit:]
```

**Effort**: 1 hour
**Priority**: HIGH

---

### Phase 6 Deliverables

| Deliverable | Status | Verification |
|-------------|--------|--------------|
| FastAPI application | ☐ | Server starts successfully |
| Signal endpoints | ☐ | GET /api/v1/signals/latest works |
| Alert endpoints | ☐ | GET /api/v1/alerts/latest works |
| CORS configured | ☐ | Cross-origin requests allowed |
| Health check | ☐ | GET /health returns 200 |

**Phase 6 Timeline**: 1 day
**Phase 6 Exit Criteria**: API serving signals and alerts

---

## Summary

### Timeline Overview

| Phase | Duration | Repository | Key Deliverable |
|-------|----------|------------|-----------------|
| Phase 1: Data Infrastructure | 1-2 days | market-scraper | TraderWebSocket enabled |
| Phase 2: Signal Foundation | 2-3 days | smart-money-signal-system | Event subscriber working |
| Phase 3: Weighting Engine | 2-3 days | smart-money-signal-system | Multi-dimensional weights |
| Phase 4: ML Components | 3-4 days | smart-money-signal-system | Feature importance + regime |
| Phase 5: Whale Alerts | 1-2 days | smart-money-signal-system | Alert detector working |
| Phase 6: API | 1 day | smart-money-signal-system | REST API serving signals |

**Total Timeline**: 5 weeks (including buffer and testing)

### Critical Path

1. **Phase 1** (market-scraper) - Must complete first
2. **Phase 2** (signal-system) - Depends on Phase 1
3. **Phase 3-6** - Can proceed in parallel after Phase 2

### Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Signal Accuracy | >55% | Backtest vs historical data |
| Alert Latency | <5 seconds | Time from position change to alert |
| System Uptime | >99% | Health check monitoring |
| Trader Coverage | 300-500 | Count of active subscriptions |

---

*Implementation Plan V2 - Two-Repository Architecture*
*Aligned with 2026 industry best practices*
