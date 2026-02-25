# Smart Money Signal System - Implementation Plan

**Project**: Smart Money Signal System for BTC Trading
**Timeline**: 5 Weeks
**Start Date**: 2026-02-24

---

## Overview

This document provides a detailed, step-by-step implementation plan for building a comprehensive signal generation system that tracks real trader positions from Hyperliquid and generates actionable trading signals.

---

## Phase 1: Foundation (Week 1-2)

### Goal
Enable real-time position tracking and establish the event flow for signal generation.

### Step 1.1: Enable TraderWebSocketCollector

**File**: `src/market_scraper/connectors/hyperliquid/collectors/manager.py`

**Current Code**:
```python
collector_classes = {
    "candles": CandlesCollector,
}
```

**Updated Code**:
```python
from market_scraper.connectors.hyperliquid.collectors.trader_ws import TraderWebSocketCollector

collector_classes = {
    "candles": CandlesCollector,
    "trader_ws": TraderWebSocketCollector,
}
```

**Additional Changes to manager.py**:
```python
async def subscribe_traders(self, addresses: list[str]) -> None:
    """Subscribe to trader position updates.

    Args:
        addresses: List of Ethereum addresses to track
    """
    if "trader_ws" in self._collectors:
        await self._collectors["trader_ws"].start(addresses)

async def add_trader_subscription(self, address: str) -> None:
    """Add a single trader to tracking.

    Args:
        address: Ethereum address to track
    """
    if "trader_ws" in self._collectors:
        await self._collectors["trader_ws"].add_trader(address)

async def remove_trader_subscription(self, address: str) -> None:
    """Remove a trader from tracking.

    Args:
        address: Ethereum address to remove
    """
    if "trader_ws" in self._collectors:
        await self._collectors["trader_ws"].remove_trader(address)
```

---

### Step 1.2: Update Lifecycle Manager

**File**: `src/market_scraper/orchestration/lifecycle.py`

**Change 1**: Enable trader_ws collector (around line 443)

```python
# Before
collectors=["candles"],

# After
collectors=["candles", "trader_ws"],
```

**Change 2**: Add method to subscribe tracked traders

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
        await self._collector_manager.subscribe_traders(tracked)
```

**Change 3**: Call subscription after leaderboard init

In `startup()` method, after `_init_leaderboard_collector()`:

```python
# 6. Initialize Leaderboard Collector
await self._init_leaderboard_collector()
logger.info("leaderboard_collector_initialized")

# 6.1 Subscribe traders to position tracking
await self._subscribe_tracked_traders()
logger.info("trader_position_subscriptions_complete")
```

---

### Step 1.3: Add Method to LeaderboardCollector

**File**: `src/market_scraper/connectors/hyperliquid/collectors/leaderboard.py`

Add method to expose tracked addresses:

```python
async def get_tracked_addresses(self) -> list[str]:
    """Get list of tracked trader addresses.

    Returns:
        List of Ethereum addresses currently being tracked
    """
    return list(self._tracked_traders.keys())
```

---

### Step 1.4: Wire Signal Generation

**File**: `src/market_scraper/orchestration/lifecycle.py`

Update `_init_processors()` to subscribe signal processor to `trader_positions` events:

```python
# Signal Generation Processor
signal_generation = SignalGenerationProcessor(
    event_bus=self._event_bus,
    config=config,
    weighting_engine=self._weighting_engine,  # Will create this
)
await signal_generation.start()
self._processors.append(signal_generation)

# Subscribe to trader_positions events (REAL DATA NOW!)
async def signal_handler(event: StandardEvent) -> None:
    if event.event_type == "trader_positions":
        result = await signal_generation.process(event)
        if result and self._event_bus:
            await self._event_bus.publish(result)

await self._event_bus.subscribe("trader_positions", signal_handler)
```

---

## Phase 2: Weighting System (Week 2-3)

### Goal
Implement multi-dimensional trader weighting system.

### Step 2.1: Create Weight Configuration

**New File**: `src/market_scraper/config/weighting_config.py`

```python
from dataclasses import dataclass, field
from typing import Any


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

---

### Step 2.2: Create Weighting Engine

**New File**: `src/market_scraper/processing/trader_weighting.py`

```python
"""Trader Weighting Engine.

Multi-dimensional weighting system for signal generation.
"""

from dataclasses import dataclass
from typing import Any

import structlog

from market_scraper.config.weighting_config import WeightingConfig
from market_scraper.utils.hyperliquid import parse_window_performances

logger = structlog.get_logger(__name__)


@dataclass
class TraderWeight:
    """Multi-dimensional trader weight."""
    performance: float  # 0-100 scale
    size: float         # 0.5-3.0 scale
    recency: float      # 0.5-1.5 scale
    regime: float       # 0.8-1.2 scale
    composite: float    # Final combined weight

    tier: str           # Classification
    score: float        # Original score


class TraderWeightingEngine:
    """Calculate multi-dimensional trader weights for signal aggregation.

    Weighting Dimensions:
    1. Performance: Risk-adjusted returns (Sharpe, Sortino, etc.)
    2. Size: Account value and market impact
    3. Recency: Recent performance weighted higher
    4. Regime: Performance in current market conditions
    """

    def __init__(self, config: WeightingConfig | None = None) -> None:
        """Initialize the weighting engine.

        Args:
            config: Weighting configuration (uses defaults if not provided)
        """
        self.config = config or WeightingConfig()
        self._market_regime = "unknown"
        self._trader_weights: dict[str, TraderWeight] = {}

    def set_market_regime(self, regime: str) -> None:
        """Update current market regime.

        Args:
            regime: Current market regime name
        """
        self._market_regime = regime
        # Clear cached weights since regime affects calculation
        self._trader_weights.clear()

    def calculate_weight(self, trader: dict[str, Any]) -> TraderWeight:
        """Calculate all weight dimensions for a trader.

        Args:
            trader: Trader data from leaderboard

        Returns:
            TraderWeight with all dimensions calculated
        """
        address = trader.get("ethAddress", "")

        # Check cache
        if address in self._trader_weights:
            return self._trader_weights[address]

        # Calculate each dimension
        performance = self._calc_performance_weight(trader)
        size = self._calc_size_weight(trader)
        recency = self._calc_recency_weight(trader)
        regime = self._calc_regime_weight(trader)

        # Calculate composite
        composite = (
            performance * self.config.performance_dimension_weight +
            size * self.config.size_dimension_weight +
            recency * self.config.recency_dimension_weight +
            regime * self.config.regime_dimension_weight
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
            score=trader.get("score", 50)
        )

        # Cache
        self._trader_weights[address] = weight

        return weight

    def _calc_performance_weight(self, trader: dict) -> float:
        """Calculate risk-adjusted performance score (0-100)."""
        cfg = self.config.performance

        # Get performance metrics
        sharpe = self._estimate_sharpe(trader)
        sortino = self._estimate_sortino(trader)
        consistency = self._calc_consistency(trader)
        max_dd = self._estimate_max_drawdown(trader)
        win_rate = self._estimate_win_rate(trader)
        profit_factor = self._estimate_profit_factor(trader)

        # Weighted combination
        score = (
            sharpe * cfg.sharpe_weight +
            sortino * cfg.sortino_weight +
            consistency * cfg.consistency_weight +
            (1 - min(max_dd, 1.0)) * cfg.max_drawdown_weight +
            win_rate * cfg.win_rate_weight +
            profit_factor * cfg.profit_factor_weight
        )

        # Scale to 0-100
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

        performances = parse_window_performances(
            trader.get("windowPerformances", {})
        )

        day_roi = performances.get("day", {}).get("roi", 0)
        week_roi = performances.get("week", {}).get("roi", 0)
        month_roi = performances.get("month", {}).get("roi", 0)

        # Weighted recency score
        recency_score = (
            day_roi * cfg.day_weight +
            week_roi * cfg.week_weight +
            month_roi * cfg.month_weight
        )

        # Map to range
        normalized = min(abs(recency_score), 1.0)
        return cfg.min_recency + (normalized * (cfg.max_recency - cfg.min_recency))

    def _calc_regime_weight(self, trader: dict) -> float:
        """Calculate regime alignment weight (0.8-1.2)."""
        # Base weight
        base = 1.0

        # Adjust based on regime and trader characteristics
        if self._market_regime == "high_volatility":
            # Favor traders with consistent performance in vol
            consistency = self._calc_consistency(trader)
            base = 0.8 + (consistency * 0.4)

        elif self._market_regime == "trending":
            # Favor momentum traders
            performances = parse_window_performances(
                trader.get("windowPerformances", {})
            )
            trend_score = performances.get("month", {}).get("roi", 0)
            base = 0.8 + min(abs(trend_score) * 0.4, 0.4)

        elif self._market_regime == "ranging":
            # Lower weight for trend followers
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
        performances = parse_window_performances(
            trader.get("windowPerformances", {})
        )

        # Use ROI as return proxy
        returns = [
            performances.get("day", {}).get("roi", 0),
            performances.get("week", {}).get("roi", 0) / 7,  # Daily average
            performances.get("month", {}).get("roi", 0) / 30,
        ]

        avg_return = sum(returns) / len(returns)

        # Estimate volatility from ROI variance
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        volatility = variance ** 0.5 if variance > 0 else 0.01

        # Sharpe approximation
        return avg_return / volatility if volatility > 0 else 0

    def _estimate_sortino(self, trader: dict) -> float:
        """Estimate Sortino ratio (downside deviation)."""
        performances = parse_window_performances(
            trader.get("windowPerformances", {})
        )

        returns = [
            performances.get("day", {}).get("roi", 0),
            performances.get("week", {}).get("roi", 0) / 7,
            performances.get("month", {}).get("roi", 0) / 30,
        ]

        avg_return = sum(returns) / len(returns)

        # Downside deviation
        negative_returns = [r for r in returns if r < 0]
        if negative_returns:
            downside_variance = sum(r ** 2 for r in negative_returns) / len(negative_returns)
            downside_dev = downside_variance ** 0.5
        else:
            downside_dev = 0.01

        return avg_return / downside_dev if downside_dev > 0 else 1.0

    def _calc_consistency(self, trader: dict) -> float:
        """Calculate consistency score (0-1)."""
        performances = parse_window_performances(
            trader.get("windowPerformances", {})
        )

        timeframes = ["day", "week", "month", "allTime"]
        positive_count = sum(
            1 for tf in timeframes
            if performances.get(tf, {}).get("roi", 0) > 0
        )

        return positive_count / len(timeframes)

    def _estimate_max_drawdown(self, trader: dict) -> float:
        """Estimate max drawdown from available data."""
        # Use score volatility as proxy
        score = trader.get("score", 50)

        # Higher scores typically have better risk management
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
        performances = parse_window_performances(
            trader.get("windowPerformances", {})
        )

        # Positive ROI implies more wins than losses
        day_roi = performances.get("day", {}).get("roi", 0)
        week_roi = performances.get("week", {}).get("roi", 0)

        # Rough estimation
        if day_roi > 0 and week_roi > 0:
            return 0.55 + min(abs(day_roi) * 2, 0.35)
        elif day_roi > 0 or week_roi > 0:
            return 0.50
        else:
            return 0.45

    def _estimate_profit_factor(self, trader: dict) -> float:
        """Estimate profit factor."""
        performances = parse_window_performances(
            trader.get("windowPerformances", {})
        )

        all_time_roi = performances.get("allTime", {}).get("roi", 0)

        # Profit factor approximation from ROI
        if all_time_roi > 1:
            return 2.0
        elif all_time_roi > 0.5:
            return 1.5
        elif all_time_roi > 0:
            return 1.2
        else:
            return 0.8

    def get_cached_weights(self) -> dict[str, TraderWeight]:
        """Get all cached weights."""
        return self._trader_weights.copy()

    def clear_cache(self) -> None:
        """Clear weight cache."""
        self._trader_weights.clear()
```

---

### Step 2.3: Update Signal Generation Processor

**File**: `src/market_scraper/processors/signal_generation.py`

Replace the existing processor with weighted version:

```python
"""Signal Generation Processor.

Generates trading signals from aggregated trader position data.
"""

from datetime import UTC, datetime
from typing import Any

import structlog

from market_scraper.core.config import HyperliquidSettings
from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.processors.base import Processor
from market_scraper.processing.trader_weighting import TraderWeightingEngine

logger = structlog.get_logger(__name__)


class SignalGenerationProcessor(Processor):
    """Processor that generates trading signals from real trader positions.

    Uses TraderWeightingEngine for multi-dimensional weight calculation.
    Emits 'smart_money_signal' events.
    """

    def __init__(
        self,
        event_bus: EventBus,
        config: HyperliquidSettings | None = None,
        weighting_engine: TraderWeightingEngine | None = None,
    ) -> None:
        """Initialize the processor.

        Args:
            event_bus: Event bus for publishing events
            config: Hyperliquid settings
            weighting_engine: Trader weighting engine
        """
        super().__init__(event_bus)
        self._config = config
        self._symbol = config.symbol if config else "BTC"
        self._weighting = weighting_engine or TraderWeightingEngine()

        # State: trader positions and metadata
        self._positions: dict[str, dict] = {}
        self._trader_data: dict[str, dict] = {}

        # Stats
        self._signals_generated = 0
        self._positions_processed = 0

    @property
    def name(self) -> str:
        """Processor name."""
        return "signal_generation"

    async def process(self, event: StandardEvent) -> StandardEvent | None:
        """Process position update and generate signal.

        Args:
            event: Event containing trader position data

        Returns:
            Signal event or None
        """
        if event.event_type != "trader_positions":
            return None

        self._positions_processed += 1

        payload = event.payload
        address = payload.get("address")

        if not address:
            return None

        # Extract BTC position
        btc_position = self._extract_btc_position(payload)

        # Store position
        self._positions[address] = btc_position

        # Store trader metadata for weighting
        if "trader_metadata" in payload:
            self._trader_data[address] = payload["trader_metadata"]

        # Generate aggregate signal
        return self._generate_signal()

    def _extract_btc_position(self, payload: dict) -> dict:
        """Extract BTC position from payload."""
        positions = payload.get("positions", [])

        for pos in positions:
            pos_data = pos.get("position", pos)
            if pos_data.get("coin") == self._symbol:
                return {
                    "szi": float(pos_data.get("szi", 0)),
                    "entry_px": float(pos_data.get("entryPx", 0)),
                    "position_value": float(pos_data.get("positionValue", 0)),
                    "unrealized_pnl": float(pos_data.get("unrealizedPnl", 0)),
                    "leverage": pos_data.get("leverage", {}).get("value", 1),
                }

        return {"szi": 0, "position_value": 0}

    def _generate_signal(self) -> StandardEvent | None:
        """Generate weighted aggregate signal."""
        if not self._positions:
            return None

        weighted_long = 0.0
        weighted_short = 0.0
        total_weight = 0.0

        traders_long = 0
        traders_short = 0
        traders_neutral = 0

        whale_breakdown = {
            "alpha_whales": {"long": 0, "short": 0, "neutral": 0},
            "whales": {"long": 0, "short": 0, "neutral": 0},
            "elite": {"long": 0, "short": 0, "neutral": 0},
            "standard": {"long": 0, "short": 0, "neutral": 0},
        }

        top_positions = []

        for address, position in self._positions.items():
            szi = position.get("szi", 0)
            position_value = position.get("position_value", 0)

            # Get trader weight
            trader_data = self._trader_data.get(address, {})
            weight = self._weighting.calculate_weight(trader_data)

            # Skip if no position
            if szi == 0:
                traders_neutral += 1
                continue

            # Calculate effective weight (composite x position size)
            size_factor = position_value / 1_000_000  # Per $1M
            effective_weight = weight.composite * size_factor

            direction = "LONG" if szi > 0 else "SHORT"

            if szi > 0:
                weighted_long += effective_weight
                traders_long += 1
            else:
                weighted_short += effective_weight
                traders_short += 1

            # Update breakdown
            self._update_breakdown(whale_breakdown, weight.tier, direction)

            # Track top positions
            top_positions.append({
                "address": address,
                "tier": weight.tier,
                "direction": direction,
                "size_btc": abs(szi),
                "value_usd": position_value,
                "weight": weight.composite,
            })

            total_weight += effective_weight

        if total_weight == 0:
            return None

        # Calculate biases
        long_bias = weighted_long / total_weight
        short_bias = weighted_short / total_weight
        net_bias = long_bias - short_bias

        # Determine action
        if net_bias > 0.2:
            action = "BUY"
        elif net_bias < -0.2:
            action = "SELL"
        else:
            action = "NEUTRAL"

        # Calculate confidence
        confidence = self._calc_confidence(
            net_bias=net_bias,
            traders_active=traders_long + traders_short,
            total_weight=total_weight
        )

        # Sort top positions by weight
        top_positions.sort(key=lambda x: x["weight"], reverse=True)

        self._signals_generated += 1

        return StandardEvent.create(
            event_type="smart_money_signal",
            source="signal_generation",
            payload={
                "action": action,
                "confidence": confidence,
                "net_bias": round(net_bias, 4),
                "long_bias": round(long_bias, 4),
                "short_bias": round(short_bias, 4),
                "traders_long": traders_long,
                "traders_short": traders_short,
                "traders_neutral": traders_neutral,
                "weighted_long_value": round(weighted_long * 1_000_000, 2),
                "weighted_short_value": round(weighted_short * 1_000_000, 2),
                "whale_breakdown": whale_breakdown,
                "top_positions": top_positions[:10],
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    def _update_breakdown(self, breakdown: dict, tier: str, direction: str) -> None:
        """Update whale breakdown counts."""
        tier_key = tier if tier in breakdown else "standard"
        breakdown[tier_key][direction.lower()] += 1

    def _calc_confidence(
        self,
        net_bias: float,
        traders_active: int,
        total_weight: float
    ) -> float:
        """Calculate signal confidence."""
        # Agreement factor
        agreement = abs(net_bias)

        # Participation factor (more traders = more confidence)
        participation = min(traders_active / 100, 1.0)

        # Weight factor (more total weight = more confidence)
        weight_factor = min(total_weight / 100, 1.0)

        # Combined
        confidence = (
            agreement * 0.5 +
            participation * 0.3 +
            weight_factor * 0.2
        )

        return min(confidence, 1.0)

    def get_stats(self) -> dict[str, Any]:
        """Get processor statistics."""
        return {
            "signals_generated": self._signals_generated,
            "positions_processed": self._positions_processed,
            "tracked_traders": len(self._positions),
        }
```

---

## Phase 3: Whale Alert System (Week 3)

### Goal
Real-time detection and alerting of significant whale position changes.

### Step 3.1: Create Whale Alert Detector

**New File**: `src/market_scraper/processors/whale_alerts.py`

```python
"""Whale Alert Detection System.

Detects and alerts on significant whale position changes.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.processors.base import Processor
from market_scraper.processing.trader_weighting import TraderWeightingEngine

logger = structlog.get_logger(__name__)


@dataclass
class WhaleAlert:
    """Whale alert data."""
    alert_type: str
    priority: str  # CRITICAL, HIGH, MEDIUM, LOW
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
    change_type: str  # REVERSAL, ENTRY, EXIT, SIZE_CHANGE
    market_context: dict
    recommendation: str


class WhaleAlertDetector(Processor):
    """Detects significant whale position changes.

    Alert Priorities:
    - CRITICAL: Alpha Whale ($20M+) position change
    - HIGH: 2+ whales change within 5 min
    - MEDIUM: Aggregate whale bias flips
    - LOW: Elite consensus shifts 20%+
    """

    def __init__(
        self,
        event_bus: EventBus,
        weighting_engine: TraderWeightingEngine,
        config: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the detector.

        Args:
            event_bus: Event bus for publishing alerts
            weighting_engine: Trader weighting engine
            config: Alert configuration
        """
        super().__init__(event_bus)
        self._weighting = weighting_engine
        self._config = config or {}

        # Thresholds
        self._alpha_whale_threshold = self._config.get("alpha_whale_threshold", 20_000_000)
        self._whale_threshold = self._config.get("whale_threshold", 10_000_000)
        self._elite_threshold = self._config.get("elite_threshold", 80)

        # State
        self._last_positions: dict[str, dict] = {}
        self._recent_alerts: list[WhaleAlert] = []
        self._whale_bias_history: list[dict] = []

        # Stats
        self._alerts_generated = 0

    @property
    def name(self) -> str:
        return "whale_alert_detector"

    async def process(self, event: StandardEvent) -> StandardEvent | None:
        """Process position update and detect whale alerts."""
        if event.event_type != "trader_positions":
            return None

        payload = event.payload
        address = payload.get("address")

        # Get current position
        current = self._extract_btc_position(payload)
        trader_data = payload.get("trader_metadata", {})

        # Check if this is a whale
        account_value = float(trader_data.get("accountValue", 0))
        score = trader_data.get("score", 0)

        is_alpha_whale = account_value >= self._alpha_whale_threshold
        is_whale = account_value >= self._whale_threshold
        is_elite = score >= self._elite_threshold

        if not (is_whale or is_elite):
            # Update state but don't generate alert
            self._last_positions[address] = current
            return None

        # Get previous position
        previous = self._last_positions.get(address)

        # Detect change
        if previous and self._is_significant_change(previous, current):
            # Create alert
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

                # Keep only recent alerts
                self._prune_old_alerts()

                # Emit alert event
                return self._alert_to_event(alert)

        # Update state
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
        # Direction change
        if previous["direction"] != current["direction"]:
            return True

        # Size change > 20%
        if previous["size"] > 0 and current["size"] > 0:
            size_change = abs(current["size"] - previous["size"]) / previous["size"]
            if size_change > 0.2:
                return True

        # Entry (was neutral, now has position)
        if previous["direction"] == "NEUTRAL" and current["direction"] != "NEUTRAL":
            return True

        # Exit (had position, now neutral)
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
    ) -> WhaleAlert | None:
        """Create whale alert."""
        # Determine priority
        if is_alpha_whale:
            priority = "CRITICAL"
        elif is_whale:
            priority = "HIGH"
        elif is_elite:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        # Determine change type
        if previous["direction"] != current["direction"]:
            if previous["direction"] == "NEUTRAL":
                change_type = "ENTRY"
            elif current["direction"] == "NEUTRAL":
                change_type = "EXIT"
            else:
                change_type = "REVERSAL"
        else:
            change_type = "SIZE_CHANGE"

        # Calculate whale bias context
        market_context = self._calculate_market_context()

        # Generate recommendation
        recommendation = self._generate_recommendation(
            priority, change_type, current["direction"]
        )

        return WhaleAlert(
            alert_type="WHALE_POSITION_CHANGE",
            priority=priority,
            timestamp=datetime.now(UTC),
            trader_address=address,
            trader_name=trader_data.get("displayName"),
            tier="alpha_whale" if is_alpha_whale else ("whale" if is_whale else "elite"),
            account_value=float(trader_data.get("accountValue", 0)),
            coin="BTC",
            previous_direction=previous["direction"],
            current_direction=current["direction"],
            previous_size=previous["size"],
            current_size=current["size"],
            change_type=change_type,
            market_context=market_context,
            recommendation=recommendation,
        )

    def _calculate_market_context(self) -> dict:
        """Calculate current market context for alerts."""
        # Aggregate whale bias
        whale_long = 0
        whale_short = 0

        for address, position in self._last_positions.items():
            if position["direction"] == "LONG":
                whale_long += 1
            elif position["direction"] == "SHORT":
                whale_short += 1

        total = whale_long + whale_short
        whale_bias = (whale_long - whale_short) / total if total > 0 else 0

        return {
            "whale_bias": round(whale_bias, 3),
            "whales_long": whale_long,
            "whales_short": whale_short,
        }

    def _generate_recommendation(
        self,
        priority: str,
        change_type: str,
        direction: str
    ) -> str:
        """Generate action recommendation."""
        if priority == "CRITICAL":
            if change_type == "REVERSAL":
                return f"STRONG {'BUY' if direction == 'LONG' else 'SELL'} SIGNAL - Alpha whale reversed"
            elif change_type == "ENTRY":
                return f"ALERT - Alpha whale entered {direction}"
            elif change_type == "EXIT":
                return "ALERT - Alpha whale exited position"

        elif priority == "HIGH":
            return f"Whale {'BUY' if direction == 'LONG' else 'SELL'} signal"

        return f"Monitor - Elite trader {change_type.lower()}"

    def _alert_to_event(self, alert: WhaleAlert) -> StandardEvent:
        """Convert alert to event."""
        return StandardEvent.create(
            event_type="whale_alert",
            source="whale_alert_detector",
            payload={
                "alert_type": alert.alert_type,
                "priority": alert.priority,
                "timestamp": alert.timestamp.isoformat(),
                "trader": {
                    "address": alert.trader_address,
                    "name": alert.trader_name,
                    "tier": alert.tier,
                    "account_value": alert.account_value,
                },
                "position_change": {
                    "coin": alert.coin,
                    "previous_direction": alert.previous_direction,
                    "current_direction": alert.current_direction,
                    "previous_size": alert.previous_size,
                    "current_size": alert.current_size,
                    "change_type": alert.change_type,
                },
                "market_context": alert.market_context,
                "recommendation": alert.recommendation,
            }
        )

    def _prune_old_alerts(self, max_age_hours: int = 24) -> None:
        """Remove old alerts."""
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        self._recent_alerts = [
            a for a in self._recent_alerts
            if a.timestamp > cutoff
        ]

    def get_recent_alerts(self, hours: int = 24, priority: str | None = None) -> list[dict]:
        """Get recent alerts.

        Args:
            hours: Hours to look back
            priority: Filter by priority (optional)

        Returns:
            List of alert dictionaries
        """
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

    def get_stats(self) -> dict[str, Any]:
        """Get detector statistics."""
        return {
            "alerts_generated": self._alerts_generated,
            "tracked_whales": len(self._last_positions),
            "recent_alerts": len(self._recent_alerts),
        }
```

---

## Phase 4: ML Components (Week 4)

### Goal
Implement ML for feature discovery and regime detection.

### Step 4.1: Feature Importance Analyzer

**New File**: `src/market_scraper/ml/feature_importance.py`

```python
"""Feature Importance Analyzer.

Uses ML to discover which metrics predict trader success.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import structlog
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

logger = structlog.get_logger(__name__)


class FeatureImportanceAnalyzer:
    """Analyzes which trader metrics are most predictive of success.

    Uses RandomForest for feature importance and cross-validation
    to ensure robustness.
    """

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
        """Initialize the analyzer.

        Args:
            model_path: Path to save/load trained model
        """
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
        """Extract feature matrix from trader data.

        Args:
            traders: List of trader dictionaries

        Returns:
            Feature matrix (n_samples, n_features)
        """
        features = []

        for trader in traders:
            row = [
                self._calc_sharpe(trader),
                self._calc_sortino(trader),
                self._estimate_max_dd(trader),
                self._estimate_win_rate(trader),
                self._estimate_profit_factor(trader),
                self._calc_consistency(trader),
                trader.get("avg_leverage", 1),
                trader.get("position_concentration", 0.5),
                trader.get("day_roi", 0),
                trader.get("week_roi", 0),
                trader.get("month_roi", 0),
                trader.get("all_time_roi", 0),
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
    ) -> dict:
        """Train the feature importance model.

        Args:
            traders: List of trader data
            labels: Binary labels (1 = profitable next period, 0 = not)
            test_size: Fraction for test set

        Returns:
            Training metrics
        """
        X = self.prepare_features(traders)
        y = np.array(labels)

        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y
        )

        # Scale
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train
        self.model.fit(X_train_scaled, y_train)
        self._trained = True

        # Calculate importance
        self._feature_importance = pd.Series(
            self.model.feature_importances_,
            index=self.FEATURE_NAMES
        ).sort_values(ascending=False)

        # Cross-validation
        cv_scores = cross_val_score(
            self.model, X_train_scaled, y_train, cv=5, scoring="roc_auc"
        )

        # Test metrics
        test_score = self.model.score(X_test_scaled, y_test)

        metrics = {
            "train_accuracy": self.model.score(X_train_scaled, y_train),
            "test_accuracy": test_score,
            "cv_auc_mean": cv_scores.mean(),
            "cv_auc_std": cv_scores.std(),
            "feature_importance": self._feature_importance.to_dict(),
        }

        logger.info(
            "feature_importance_trained",
            test_accuracy=round(test_score, 3),
            cv_auc=round(cv_scores.mean(), 3),
        )

        # Save model if path provided
        if self.model_path:
            self._save_model()

        return metrics

    def get_feature_importance(self) -> pd.Series:
        """Get feature importance rankings.

        Returns:
            Series of feature importance values sorted descending
        """
        if self._feature_importance is None:
            raise ValueError("Model not trained yet")

        return self._feature_importance

    def predict_success_probability(self, trader: dict) -> float:
        """Predict probability of trader being profitable.

        Args:
            trader: Single trader data

        Returns:
            Probability (0-1)
        """
        if not self._trained:
            raise ValueError("Model not trained yet")

        X = self.prepare_features([trader])
        X_scaled = self.scaler.transform(X)

        return self.model.predict_proba(X_scaled)[0][1]

    def get_top_features(self, n: int = 5) -> list[tuple[str, float]]:
        """Get top N most important features.

        Args:
            n: Number of features to return

        Returns:
            List of (feature_name, importance) tuples
        """
        importance = self.get_feature_importance()
        return list(importance.head(n).items())

    def _save_model(self) -> None:
        """Save trained model to disk."""
        import joblib

        if self.model_path:
            joblib.dump(
                {"model": self.model, "scaler": self.scaler},
                self.model_path
            )
            logger.info("model_saved", path=str(self.model_path))

    def load_model(self) -> None:
        """Load trained model from disk."""
        import joblib

        if self.model_path and self.model_path.exists():
            data = joblib.load(self.model_path)
            self.model = data["model"]
            self.scaler = data["scaler"]
            self._trained = True
            logger.info("model_loaded", path=str(self.model_path))

    # --- Helper methods (same as in weighting engine) ---

    def _calc_sharpe(self, trader: dict) -> float:
        """Estimate Sharpe ratio."""
        returns = [
            trader.get("day_roi", 0),
            trader.get("week_roi", 0) / 7,
            trader.get("month_roi", 0) / 30,
        ]
        avg_return = np.mean(returns)
        volatility = np.std(returns) if np.std(returns) > 0 else 0.01
        return avg_return / volatility

    def _calc_sortino(self, trader: dict) -> float:
        """Estimate Sortino ratio."""
        returns = [
            trader.get("day_roi", 0),
            trader.get("week_roi", 0) / 7,
            trader.get("month_roi", 0) / 30,
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
        day_roi = trader.get("day_roi", 0)
        week_roi = trader.get("week_roi", 0)
        if day_roi > 0 and week_roi > 0:
            return 0.55 + min(abs(day_roi) * 2, 0.35)
        return 0.5

    def _estimate_profit_factor(self, trader: dict) -> float:
        """Estimate profit factor."""
        roi = trader.get("all_time_roi", 0)
        if roi > 1:
            return 2.0
        elif roi > 0.5:
            return 1.5
        elif roi > 0:
            return 1.2
        return 0.8

    def _calc_consistency(self, trader: dict) -> float:
        """Calculate consistency."""
        timeframes = ["day_roi", "week_roi", "month_roi", "all_time_roi"]
        positive = sum(1 for tf in timeframes if trader.get(tf, 0) > 0)
        return positive / len(timeframes)
```

---

### Step 4.2: Market Regime Detector

**New File**: `src/market_scraper/ml/regime_detection.py`

```python
"""Market Regime Detection.

Uses unsupervised learning to identify market phases.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import structlog
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = structlog.get_logger(__name__)


class MarketRegimeDetector:
    """Identifies market regime from on-chain and price metrics.

    Regimes:
    - deep_accumulation: CBBI < 0.2, Fear < 20
    - early_bull: CBBI 0.2-0.4, improving sentiment
    - mid_bull: CBBI 0.4-0.6, neutral sentiment
    - late_bull: CBBI 0.6-0.8, greed emerging
    - distribution: CBBI > 0.8, extreme greed
    - bear: Declining CBBI, fear dominant
    """

    REGIME_LABELS = {
        0: "deep_accumulation",
        1: "early_bull",
        2: "mid_bull",
        3: "late_bull",
        4: "distribution",
        5: "bear",
    }

    REGIME_SIGNALS = {
        "deep_accumulation": 1.5,   # Strong buy
        "early_bull": 1.0,          # Buy
        "mid_bull": 0.5,            # Hold/buy
        "late_bull": 0.0,           # Neutral
        "distribution": -1.0,       # Sell
        "bear": -0.5,               # Reduce
    }

    def __init__(self, n_regimes: int = 6, model_path: Path | None = None) -> None:
        """Initialize the detector.

        Args:
            n_regimes: Number of regime clusters
            model_path: Path to save/load model
        """
        self.n_regimes = n_regimes
        self.model_path = model_path

        self.model = KMeans(
            n_clusters=n_regimes,
            random_state=42,
            n_init=10
        )
        self.scaler = StandardScaler()

        self._trained = False
        self._current_regime = "unknown"
        self._regime_history: list[dict] = []

    def prepare_features(self, data: list[dict]) -> np.ndarray:
        """Extract regime features from on-chain data.

        Args:
            data: List of on-chain metric dictionaries

        Returns:
            Feature matrix
        """
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

    def train(self, historical_data: list[dict]) -> dict:
        """Train regime detection model.

        Args:
            historical_data: Historical on-chain metrics

        Returns:
            Training metrics
        """
        X = self.prepare_features(historical_data)
        X_scaled = self.scaler.fit_transform(X)

        # Fit clustering
        self.model.fit(X_scaled)
        self._trained = True

        # Label clusters based on characteristics
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
        # Analyze cluster characteristics
        centers = self.scaler.inverse_transform(self.model.cluster_centers_)

        # Sort by CBBI (primary indicator)
        cbbi_values = centers[:, 0]
        sorted_indices = np.argsort(cbbi_values)

        # Map indices to regime names
        self._cluster_to_regime = {}
        for label, idx in enumerate(sorted_indices):
            if label < 6:  # We have 6 regime names
                self._cluster_to_regime[idx] = self.REGIME_LABELS[label]

    def detect_regime(self, current_data: dict) -> str:
        """Identify current market regime.

        Args:
            current_data: Current on-chain metrics

        Returns:
            Regime name
        """
        if not self._trained:
            # Use rule-based fallback
            return self._rule_based_regime(current_data)

        X = self.prepare_features([current_data])
        X_scaled = self.scaler.transform(X)

        cluster = self.model.predict(X_scaled)[0]
        regime = self._cluster_to_regime.get(cluster, "unknown")

        self._current_regime = regime

        # Store history
        self._regime_history.append({
            "timestamp": datetime.now(UTC).isoformat(),
            "regime": regime,
            "cluster": int(cluster),
        })

        # Prune history
        if len(self._regime_history) > 1000:
            self._regime_history = self._regime_history[-500:]

        return regime

    def _rule_based_regime(self, data: dict) -> str:
        """Fallback rule-based regime detection."""
        cbbi = data.get("cbbi", 0.5)
        fg = data.get("fear_greed", 50)

        if cbbi < 0.2 and fg < 25:
            return "deep_accumulation"
        elif cbbi < 0.4:
            return "early_bull"
        elif cbbi < 0.6:
            return "mid_bull"
        elif cbbi < 0.8:
            return "late_bull"
        elif cbbi >= 0.8 or fg >= 80:
            return "distribution"
        else:
            return "bear"

    def get_regime_signal(self, regime: str) -> float:
        """Get trading signal for regime.

        Args:
            regime: Regime name

        Returns:
            Signal (-1.5 to 1.5)
        """
        return self.REGIME_SIGNALS.get(regime, 0)

    def get_regime_adjustment(self) -> float:
        """Get weight adjustment factor for current regime.

        Returns:
            Adjustment factor (0.8-1.2)
        """
        signal = self.get_regime_signal(self._current_regime)

        # Convert signal to adjustment
        if signal > 0:
            return 0.8 + (signal * 0.2)  # 0.8 to 1.2
        else:
            return 0.8 + (signal * 0.2)  # 0.6 to 0.8

    def get_current_regime(self) -> str:
        """Get current regime name."""
        return self._current_regime

    def get_regime_history(self, hours: int = 24) -> list[dict]:
        """Get regime history.

        Args:
            hours: Hours to look back

        Returns:
            List of regime records
        """
        cutoff = datetime.now(UTC) - timedelta(hours=hours)

        return [
            r for r in self._regime_history
            if datetime.fromisoformat(r["timestamp"]) > cutoff
        ]

    def _save_model(self) -> None:
        """Save model to disk."""
        import joblib

        if self.model_path:
            joblib.dump(
                {"model": self.model, "scaler": self.scaler},
                self.model_path
            )

    def load_model(self) -> None:
        """Load model from disk."""
        import joblib

        if self.model_path and self.model_path.exists():
            data = joblib.load(self.model_path)
            self.model = data["model"]
            self.scaler = data["scaler"]
            self._trained = True
```

---

## Phase 5: API Endpoints (Week 5)

### Goal
Expose signals via REST API and WebSocket.

### Step 5.1: Signal Endpoints

**File**: `src/market_scraper/api/routes/signals.py` (Update existing)

```python
# Add new endpoints

@router.get("/composite")
async def get_composite_signal(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, Any]:
    """Get full composite signal with all components."""
    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    # Get latest signals from each component
    smart_money = await _get_smart_money_signal(lifecycle)
    on_chain = await _get_on_chain_signal(lifecycle)
    sentiment = await _get_sentiment_signal(lifecycle)

    # Calculate ensemble
    ensemble = _calculate_ensemble(smart_money, on_chain, sentiment)

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "ensemble": ensemble,
        "components": {
            "smart_money": smart_money,
            "on_chain": on_chain,
            "sentiment": sentiment,
        },
    }


@router.get("/whale-alerts")
async def get_whale_alerts(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
    hours: int = Query(default=24, ge=1, le=168),
    priority: str | None = Query(default=None, pattern="^(CRITICAL|HIGH|MEDIUM|LOW)$"),
) -> dict[str, Any]:
    """Get recent whale position change alerts."""
    whale_detector = lifecycle.whale_detector
    if not whale_detector:
        raise HTTPException(status_code=503, detail="Whale detector not available")

    alerts = whale_detector.get_recent_alerts(hours=hours, priority=priority)

    return {
        "alerts": alerts,
        "count": len(alerts),
        "query": {"hours": hours, "priority": priority},
    }


@router.get("/traders/{address}/weight")
async def get_trader_weight(
    address: str,
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, Any]:
    """Get detailed weight breakdown for a trader."""
    if not _validate_eth_address(address):
        raise HTTPException(
            status_code=400,
            detail="Invalid Ethereum address format"
        )

    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    trader = await repository.get_trader(address)
    if not trader:
        raise HTTPException(status_code=404, detail="Trader not found")

    weighting_engine = lifecycle.weighting_engine
    weight = weighting_engine.calculate_weight(trader)

    return {
        "address": address,
        "display_name": trader.get("displayName"),
        "score": trader.get("score"),
        "account_value": trader.get("accountValue"),
        "weight": {
            "performance": round(weight.performance, 2),
            "size": round(weight.size, 2),
            "recency": round(weight.recency, 2),
            "regime": round(weight.regime, 2),
            "composite": round(weight.composite, 3),
        },
        "tier": weight.tier,
        "tags": trader.get("tags", []),
    }


@router.get("/weights/distribution")
async def get_weight_distribution(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, Any]:
    """Get weight distribution across tracked traders."""
    repository = lifecycle.repository
    if not repository:
        raise HTTPException(status_code=503, detail="Repository not available")

    traders = await repository.get_traders(limit=500)
    weighting_engine = lifecycle.weighting_engine

    distribution = {
        "alpha_whales": [],
        "whales": [],
        "elite": [],
        "standard": [],
        "small": [],
    }

    for trader in traders:
        weight = weighting_engine.calculate_weight(trader)
        distribution[weight.tier].append({
            "address": trader.get("ethAddress"),
            "composite": round(weight.composite, 3),
            "account_value": trader.get("accountValue"),
        })

    return {
        "distribution": {
            tier: {
                "count": len(traders),
                "avg_weight": np.mean([t["composite"] for t in traders]) if traders else 0,
                "total_value": sum(t["account_value"] for t in traders),
            }
            for tier, traders in distribution.items()
        },
        "total_traders": len(traders),
    }
```

---

## Testing Strategy

### Unit Tests

**File**: `tests/unit/processing/test_weighting.py`

```python
import pytest

from market_scraper.processing.trader_weighting import (
    TraderWeightingEngine,
    TraderWeight,
)
from market_scraper.config.weighting_config import WeightingConfig


class TestTraderWeightingEngine:

    @pytest.fixture
    def engine(self):
        return TraderWeightingEngine()

    @pytest.fixture
    def sample_trader(self):
        return {
            "ethAddress": "0x" + "a" * 40,
            "accountValue": 15_000_000,
            "score": 95,
            "windowPerformances": {
                "day": {"roi": 0.02},
                "week": {"roi": 0.15},
                "month": {"roi": 0.45},
                "allTime": {"roi": 2.5},
            },
        }

    def test_calculate_weight_returns_trader_weight(self, engine, sample_trader):
        weight = engine.calculate_weight(sample_trader)

        assert isinstance(weight, TraderWeight)
        assert 0 <= weight.performance <= 100
        assert 0.5 <= weight.size <= 3.0
        assert 0.5 <= weight.recency <= 1.5
        assert 0.8 <= weight.regime <= 1.2

    def test_whale_gets_higher_size_weight(self, engine, sample_trader):
        weight_whale = engine.calculate_weight(sample_trader)

        sample_trader["accountValue"] = 50_000
        weight_small = engine.calculate_weight(sample_trader)

        assert weight_whale.size > weight_small.size

    def test_consistent_performer_gets_higher_performance_weight(self, engine):
        consistent_trader = {
            "ethAddress": "0x" + "b" * 40,
            "accountValue": 1_000_000,
            "score": 90,
            "windowPerformances": {
                "day": {"roi": 0.01},
                "week": {"roi": 0.05},
                "month": {"roi": 0.15},
                "allTime": {"roi": 1.5},
            },
        }

        inconsistent_trader = {
            "ethAddress": "0x" + "c" * 40,
            "accountValue": 1_000_000,
            "score": 70,
            "windowPerformances": {
                "day": {"roi": -0.02},
                "week": {"roi": 0.10},
                "month": {"roi": -0.05},
                "allTime": {"roi": 0.5},
            },
        }

        weight_consistent = engine.calculate_weight(consistent_trader)
        weight_inconsistent = engine.calculate_weight(inconsistent_trader)

        assert weight_consistent.performance > weight_inconsistent.performance

    def test_caching_works(self, engine, sample_trader):
        weight1 = engine.calculate_weight(sample_trader)
        weight2 = engine.calculate_weight(sample_trader)

        # Should return same object from cache
        assert weight1 is weight2

    def test_regime_affects_weight(self, engine, sample_trader):
        engine.set_market_regime("high_volatility")
        weight_vol = engine.calculate_weight(sample_trader)

        engine.set_market_regime("trending")
        weight_trend = engine.calculate_weight(sample_trader)

        # Regime weight should differ
        assert weight_vol.regime != weight_trend.regime
```

### Integration Tests

**File**: `tests/integration/test_signal_flow.py`

```python
import pytest

from market_scraper.core.events import StandardEvent
from market_scraper.processors.signal_generation import SignalGenerationProcessor
from market_scraper.processing.trader_weighting import TraderWeightingEngine


class TestSignalFlow:

    @pytest.fixture
    def processor(self, event_bus):
        engine = TraderWeightingEngine()
        return SignalGenerationProcessor(
            event_bus=event_bus,
            weighting_engine=engine,
        )

    @pytest.mark.asyncio
    async def test_position_update_generates_signal(self, processor):
        # Create mock position event
        event = StandardEvent.create(
            event_type="trader_positions",
            source="test",
            payload={
                "address": "0x" + "a" * 40,
                "positions": [{
                    "position": {
                        "coin": "BTC",
                        "szi": "10.5",
                        "positionValue": "650000",
                    }
                }],
                "trader_metadata": {
                    "accountValue": 5_000_000,
                    "score": 85,
                },
            },
        )

        result = await processor.process(event)

        assert result is not None
        assert result.event_type == "smart_money_signal"
        assert "action" in result.payload
        assert "net_bias" in result.payload
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Weight distribution reviewed
- [ ] Alert thresholds calibrated
- [ ] ML models trained on recent data
- [ ] API documentation updated

### Deployment

- [ ] Deploy to staging environment
- [ ] Verify WebSocket connections stable
- [ ] Monitor event flow for 24 hours
- [ ] Verify signals being generated
- [ ] Test alert delivery

### Post-Deployment

- [ ] Monitor signal accuracy daily
- [ ] Review whale alerts for noise
- [ ] Track weight effectiveness
- [ ] Retrain ML models monthly

---

## Timeline Summary

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | Foundation | Trader WS enabled, event flow working |
| 2 | Weighting | Multi-dimensional weights implemented |
| 3 | Alerts | Whale alert system operational |
| 4 | ML | Feature importance, regime detection |
| 5 | API | Endpoints exposed, tests passing |

---

## Success Criteria

1. **Signal Accuracy**: >55% directional accuracy over 30 days
2. **Alert Timeliness**: <5 seconds from whale action to alert
3. **System Uptime**: >99% for signal generation
4. **Coverage**: >400 traders with active position tracking
