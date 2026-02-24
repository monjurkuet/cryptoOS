# src/market_scraper/processors/signal_generation.py

"""Signal Generation Processor.

Generates trading signals from aggregated trader position data.
Calculates long/short bias, net exposure, and recommendations.
"""

import time
from typing import Any

import structlog

from market_scraper.core.config import HyperliquidSettings
from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.processors.base import Processor
from market_scraper.utils.safe_convert import safe_float

logger = structlog.get_logger(__name__)

# Default TTL for trader data (24 hours in seconds)
TRADER_TTL_SECONDS = 86400
# Maximum number of traders to track
MAX_TRACKED_TRADERS = 10000


def determine_recommendation(long_bias: float, short_bias: float) -> str:
    """Determine trading recommendation from biases.

    Args:
        long_bias: Weighted long bias (0-1)
        short_bias: Weighted short bias (0-1)

    Returns:
        Recommendation: "BUY", "SELL", or "NEUTRAL"
    """
    net_bias = long_bias - short_bias

    if net_bias > 0.2:
        return "BUY"
    elif net_bias < -0.2:
        return "SELL"
    else:
        return "NEUTRAL"


def calculate_confidence(
    long_bias: float,
    short_bias: float,
    total_weight: float,
    traders_involved: int,
) -> float:
    """Calculate signal confidence.

    Args:
        long_bias: Weighted long bias
        short_bias: Weighted short bias
        total_weight: Total weight from all traders
        traders_involved: Number of traders with positions

    Returns:
        Confidence score (0-1)
    """
    # Agreement factor: higher when one side dominates
    agreement = abs(long_bias - short_bias)

    # Participation factor: more traders = more confidence
    participation = min(traders_involved / 100, 1.0)  # 100 traders = max

    # Weight factor: more total weight = more confidence
    weight_factor = min(total_weight / 100, 1.0)  # 100 weight = max

    # Combined confidence
    confidence = (agreement * 0.5) + (participation * 0.3) + (weight_factor * 0.2)

    return min(confidence, 1.0)


class SignalGenerationProcessor(Processor):
    """Processor that generates trading signals from trader position data.

    Aggregates positions across all tracked traders to calculate:
    - Long/short bias
    - Net exposure
    - Trading recommendation
    - Confidence score

    Implements TTL-based cleanup to prevent unbounded memory growth.
    Traders that haven't been updated in 24 hours are automatically removed.
    """

    def __init__(
        self,
        event_bus: EventBus,
        config: HyperliquidSettings | None = None,
        trader_ttl_seconds: int = TRADER_TTL_SECONDS,
        max_traders: int = MAX_TRACKED_TRADERS,
    ) -> None:
        """Initialize the processor.

        Args:
            event_bus: Event bus for publishing events
            config: Optional Hyperliquid settings
            trader_ttl_seconds: TTL for trader data in seconds
            max_traders: Maximum number of traders to track
        """
        super().__init__(event_bus)
        self._config = config
        self._symbol = config.symbol if config else "BTC"
        self._trader_ttl = trader_ttl_seconds
        self._max_traders = max_traders

        # State tracking with TTL: address -> (state, last_access_time)
        self._trader_states: dict[str, tuple[dict[str, Any], float]] = {}
        self._trader_scores: dict[str, float] = {}
        self._current_price: float = 0.0
        self._last_signal: dict[str, Any] | None = None

        # Stats
        self._signals_generated = 0

    @property
    def name(self) -> str:
        """Processor name."""
        return "signal_generation"

    async def process(self, event: StandardEvent) -> StandardEvent | None:
        """Process events and generate signals.

        Args:
            event: Event to process

        Returns:
            Signal event or None
        """
        # Update internal state based on event type
        if event.event_type == "trader_positions":
            await self._update_trader_positions(event)
        elif event.event_type == "scored_traders":
            await self._update_trader_scores(event)
        elif event.event_type == "mark_price":
            await self._update_price(event)

        # Generate signal from current state
        return self._generate_signal()

    async def _update_trader_positions(self, event: StandardEvent) -> None:
        """Update trader position state.

        Args:
            event: Event containing position data
        """
        payload = event.payload
        if not isinstance(payload, dict):
            return

        address = payload.get("address") or payload.get("ethAddress")
        if not address:
            return

        # Store with timestamp for TTL tracking
        self._trader_states[address] = (payload, time.time())

        # Cleanup stale traders periodically
        self._cleanup_stale_traders()

    async def _update_trader_scores(self, event: StandardEvent) -> None:
        """Update trader scores.

        Args:
            event: Event containing scored traders
        """
        payload = event.payload
        if not isinstance(payload, dict):
            return

        traders = payload.get("traders", [])
        for trader in traders:
            address = trader.get("address")
            score = trader.get("score", 50)
            if address:
                self._trader_scores[address] = score

    def _cleanup_stale_traders(self) -> None:
        """Remove traders that haven't been updated recently.

        Called on each position update to ensure memory doesn't grow unbounded.
        """
        now = time.time()
        cutoff = now - self._trader_ttl

        # Remove stale traders
        stale_addresses = [
            addr for addr, (_, last_access) in self._trader_states.items()
            if last_access < cutoff
        ]

        for addr in stale_addresses:
            del self._trader_states[addr]
            self._trader_scores.pop(addr, None)

        if stale_addresses:
            logger.debug(
                "trader_cleanup",
                removed=len(stale_addresses),
                remaining=len(self._trader_states),
            )

        # Enforce max size limit (LRU eviction)
        if len(self._trader_states) > self._max_traders:
            sorted_items = sorted(
                self._trader_states.items(),
                key=lambda x: x[1][1],  # Sort by last_access time
            )
            for addr, _ in sorted_items[:len(self._trader_states) - self._max_traders]:
                del self._trader_states[addr]
                self._trader_scores.pop(addr, None)

    async def _update_price(self, event: StandardEvent) -> None:
        """Update current price.

        Args:
            event: Event containing price data
        """
        payload = event.payload
        if isinstance(payload, dict):
            self._current_price = payload.get("mark_price", 0)

    def _generate_signal(self) -> StandardEvent | None:
        """Generate aggregated signal from current state.

        Returns:
            Signal event or None if insufficient data
        """
        if not self._trader_states:
            return None

        long_score = 0.0
        short_score = 0.0
        total_weight = 0.0
        traders_long = 0
        traders_short = 0
        traders_flat = 0
        net_exposure = 0.0

        for address, (state, _) in self._trader_states.items():
            score = self._trader_scores.get(address, 50)
            weight = score / 100  # Normalize to 0-1

            # Get position for configured symbol
            positions = state.get("assetPositions", [])
            if not positions:
                positions = state.get("positions", [])

            target_position = None
            for pos in positions:
                pos_data = pos.get("position", pos)
                if pos_data.get("coin") == self._symbol:
                    target_position = pos_data
                    break

            if target_position:
                szi = safe_float(target_position.get("szi"), 0)

                # Weighted exposure
                exposure = szi * weight
                net_exposure += exposure

                if szi > 0:
                    long_score += weight
                    traders_long += 1
                elif szi < 0:
                    short_score += weight
                    traders_short += 1
                else:
                    traders_flat += 1
            else:
                traders_flat += 1

            total_weight += weight

        # Calculate biases
        if total_weight > 0:
            long_bias = long_score / total_weight
            short_bias = short_score / total_weight
        else:
            return None

        # Determine recommendation
        recommendation = determine_recommendation(long_bias, short_bias)

        # Calculate confidence
        confidence = calculate_confidence(
            long_bias=long_bias,
            short_bias=short_bias,
            total_weight=total_weight,
            traders_involved=traders_long + traders_short,
        )

        signal_data = {
            "symbol": self._symbol,
            "longScore": round(long_score, 4),
            "shortScore": round(short_score, 4),
            "totalWeight": round(total_weight, 4),
            "tradersLong": traders_long,
            "tradersShort": traders_short,
            "tradersFlat": traders_flat,
            "netExposure": round(net_exposure, 4),
            "longBias": round(long_bias, 4),
            "shortBias": round(short_bias, 4),
            "recommendation": recommendation,
            "confidence": round(confidence, 4),
            "price": self._current_price,
        }

        # Only emit if significantly different from last signal
        if self._should_emit_signal(signal_data):
            self._last_signal = signal_data
            self._signals_generated += 1

            return StandardEvent.create(
                event_type="trading_signal",
                source="signal_generation",
                payload=signal_data,
            )

        return None

    def _should_emit_signal(self, signal: dict[str, Any]) -> bool:
        """Check if signal should be emitted.

        Args:
            signal: New signal data

        Returns:
            True if signal should be emitted
        """
        if self._last_signal is None:
            return True

        # Emit if recommendation changed
        if signal["recommendation"] != self._last_signal.get("recommendation"):
            return True

        # Emit if bias changed significantly
        bias_change = abs(signal["longBias"] - self._last_signal.get("longBias", 0))
        if bias_change >= 0.1:  # 10% change
            return True

        # Emit if confidence is very high
        return signal["confidence"] >= 0.7

    def get_stats(self) -> dict[str, Any]:
        """Get processor statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "signals_generated": self._signals_generated,
            "tracked_traders": len(self._trader_states),
            "scored_traders": len(self._trader_scores),
            "current_price": self._current_price,
        }
