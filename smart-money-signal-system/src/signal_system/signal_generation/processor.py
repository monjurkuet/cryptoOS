"""Signal Generation Processor."""

import time
from datetime import datetime, timezone
from typing import Any

import structlog

from signal_system.utils.safe_convert import safe_float

logger = structlog.get_logger(__name__)

# Default TTL for trader data (24 hours in seconds)
TRADER_TTL_SECONDS = 86400
# Maximum number of traders to track
MAX_TRACKED_TRADERS = 10000


class SignalGenerationProcessor:
    """Generates trading signals from trader position data.

    Implements TTL-based cleanup to prevent unbounded memory growth.
    Traders that haven't been updated in 24 hours are automatically removed.
    """

    def __init__(
        self,
        symbol: str = "BTC",
        trader_ttl_seconds: int = TRADER_TTL_SECONDS,
        max_traders: int = MAX_TRACKED_TRADERS,
    ) -> None:
        """Initialize the processor.

        Args:
            symbol: Trading symbol to generate signals for
            trader_ttl_seconds: TTL for trader data in seconds
            max_traders: Maximum number of traders to track
        """
        self.symbol = symbol
        self._trader_ttl = trader_ttl_seconds
        self._max_traders = max_traders

        # State with TTL tracking: address -> (data, last_access_time)
        self._trader_positions: dict[str, tuple[dict, float]] = {}
        self._trader_scores: dict[str, float] = {}
        self._last_signal: dict | None = None
        self._signals_generated = 0

    async def process_position(self, event: dict) -> dict | None:
        """Process trader position event.

        Args:
            event: Raw event from market-scraper

        Returns:
            Generated signal if significant change, else None
        """
        payload = event.get("payload", {})
        address = payload.get("address")

        if not address:
            return None

        # Store position with timestamp
        self._trader_positions[address] = (payload, time.time())

        # Cleanup stale traders periodically
        self._cleanup_stale_traders()

        # Generate signal
        return self._generate_signal()

    async def process_scored_traders(self, event: dict) -> None:
        """Process scored traders event.

        Args:
            event: Event containing trader scores
        """
        payload = event.get("payload", {})
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
            addr for addr, (_, last_access) in self._trader_positions.items()
            if last_access < cutoff
        ]

        for addr in stale_addresses:
            del self._trader_positions[addr]
            # Also remove scores for stale traders
            self._trader_scores.pop(addr, None)

        if stale_addresses:
            logger.debug(
                "trader_cleanup",
                removed=len(stale_addresses),
                remaining=len(self._trader_positions),
            )

        # Enforce max size limit (LRU eviction)
        if len(self._trader_positions) > self._max_traders:
            sorted_items = sorted(
                self._trader_positions.items(),
                key=lambda x: x[1][1],  # Sort by last_access time
            )
            for addr, _ in sorted_items[:len(self._trader_positions) - self._max_traders]:
                del self._trader_positions[addr]
                self._trader_scores.pop(addr, None)

    def _generate_signal(self) -> dict | None:
        """Generate aggregated signal.

        Returns:
            Signal dict if significant, else None
        """
        if not self._trader_positions:
            return None

        long_score = 0.0
        short_score = 0.0
        total_weight = 0.0
        traders_long = 0
        traders_short = 0

        for address, (position, _) in self._trader_positions.items():
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
                szi = safe_float(btc_position.get("szi"), 0)

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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Only emit if different from last signal
        if self._should_emit(signal):
            self._last_signal = signal
            self._signals_generated += 1
            return signal

        return None

    def _should_emit(self, signal: dict) -> bool:
        """Check if signal should be emitted.

        Args:
            signal: New signal to check

        Returns:
            True if signal should be emitted
        """
        if self._last_signal is None:
            return True

        if signal["action"] != self._last_signal.get("action"):
            return True

        bias_change = abs(signal["net_bias"] - self._last_signal.get("net_bias", 0))
        return bias_change >= 0.1

    def get_stats(self) -> dict[str, Any]:
        """Get processor statistics.

        Returns:
            Dict with processor stats
        """
        return {
            "signals_generated": self._signals_generated,
            "tracked_traders": len(self._trader_positions),
            "scored_traders": len(self._trader_scores),
        }

    def get_latest_signal(self) -> dict | None:
        """Get the latest generated signal.

        Returns:
            Latest signal or None
        """
        return self._last_signal
