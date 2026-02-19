# src/market_scraper/processors/position_detection.py

"""Position Detection Processor.

Detects and analyzes position changes between state snapshots.
"""

from datetime import datetime
from typing import Any

import structlog

from market_scraper.core.config import HyperliquidSettings
from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.processors.base import Processor

logger = structlog.get_logger(__name__)


def detect_position_changes(
    prev_state: dict[str, Any] | None,
    curr_state: dict[str, Any],
) -> list[dict[str, Any]]:
    """Detect position changes between two state snapshots.

    Args:
        prev_state: Previous clearinghouse state (can be None for first snapshot)
        curr_state: Current clearinghouse state

    Returns:
        List of position change dictionaries
    """
    changes = []

    # Get positions from both states
    prev_positions = _extract_positions(prev_state)
    curr_positions = _extract_positions(curr_state)

    # Get all coins from both states
    all_coins = set(prev_positions.keys()) | set(curr_positions.keys())

    for coin in all_coins:
        prev_pos = prev_positions.get(coin)
        curr_pos = curr_positions.get(coin)

        prev_size = float(prev_pos.get("szi", 0)) if prev_pos else 0
        curr_size = float(curr_pos.get("szi", 0)) if curr_pos else 0

        if prev_size != curr_size:
            change = {
                "coin": coin,
                "prev_size": prev_size,
                "curr_size": curr_size,
                "delta": curr_size - prev_size,
                "direction": _get_direction(curr_size),
                "action": _get_action(prev_size, curr_size),
                "timestamp": datetime.utcnow(),
            }

            # Add position details if not closed
            if curr_pos:
                change["entry_price"] = float(curr_pos.get("entryPx", 0))
                change["position_value"] = float(curr_pos.get("positionValue", 0))
                change["unrealized_pnl"] = float(curr_pos.get("unrealizedPnl", 0))
                change["leverage"] = _get_leverage(curr_pos)

            changes.append(change)

    return changes


def _extract_positions(state: dict[str, Any] | None) -> dict[str, dict]:
    """Extract positions from a clearinghouse state.

    Args:
        state: Clearinghouse state dictionary

    Returns:
        Dictionary mapping coin to position details
    """
    positions = {}

    if not state:
        return positions

    asset_positions = state.get("assetPositions", [])
    if not asset_positions:
        asset_positions = state.get("positions", [])

    for pos in asset_positions:
        position = pos.get("position", pos)
        coin = position.get("coin")
        if coin:
            positions[coin] = position

    return positions


def _get_direction(size: float) -> str:
    """Get position direction from size."""
    if size > 0:
        return "long"
    elif size < 0:
        return "short"
    return "flat"


def _get_action(prev_size: float, curr_size: float) -> str:
    """Get action type from position size changes."""
    if prev_size == 0 and curr_size != 0:
        return "open"
    elif prev_size != 0 and curr_size == 0:
        return "close"
    elif prev_size != 0 and curr_size != 0:
        # Check if increased or decreased
        if abs(curr_size) > abs(prev_size):
            return "increase"
        elif abs(curr_size) < abs(prev_size):
            return "decrease"
        else:
            return "modify"  # Same size, might be entry price change
    return "unknown"


def _get_leverage(position: dict) -> float:
    """Extract leverage from position."""
    leverage = position.get("leverage", {})
    if isinstance(leverage, dict):
        return float(leverage.get("value", 0))
    return float(leverage) if leverage else 0


class PositionDetectionProcessor(Processor):
    """Processor that detects position changes from trader state updates.

    Emits 'position_change' events when a trader's position changes:
    - open: New position opened
    - close: Position closed
    - increase: Position size increased
    - decrease: Position size decreased
    """

    def __init__(
        self,
        event_bus: EventBus,
        config: HyperliquidSettings | None = None,
    ) -> None:
        """Initialize the processor.

        Args:
            event_bus: Event bus for publishing events
            config: Optional Hyperliquid settings
        """
        super().__init__(event_bus)
        self._config = config
        self._symbol = config.symbol if config else "BTC"

        # Track previous state per trader
        self._prev_states: dict[str, dict] = {}

        # Stats
        self._processed = 0
        self._changes_detected = 0

    @property
    def name(self) -> str:
        """Processor name."""
        return "position_detection"

    async def process(self, event: StandardEvent) -> StandardEvent | None:
        """Process trader positions event and detect changes.

        Args:
            event: Event containing trader position data

        Returns:
            Position change event or None
        """
        if event.event_type != "trader_positions":
            return None

        self._processed += 1

        payload = event.payload
        if not isinstance(payload, dict):
            return None

        address = payload.get("address")
        if not address:
            return None

        # Get current positions
        curr_positions = payload.get("positions", [])
        curr_state = {"assetPositions": curr_positions}

        # Get previous state
        prev_state = self._prev_states.get(address)

        # Detect changes
        changes = detect_position_changes(prev_state, curr_state)

        # Filter for configured symbol
        symbol_changes = [c for c in changes if c.get("coin") == self._symbol]

        # Update previous state
        self._prev_states[address] = curr_state

        if not symbol_changes:
            return None

        self._changes_detected += len(symbol_changes)

        # Create change event
        return StandardEvent.create(
            event_type="position_change",
            source="position_detection",
            payload={
                "address": address,
                "symbol": self._symbol,
                "changes": symbol_changes,
                "change_count": len(symbol_changes),
            },
        )

    def get_stats(self) -> dict[str, Any]:
        """Get processor statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "processed": self._processed,
            "changes_detected": self._changes_detected,
            "tracked_traders": len(self._prev_states),
        }

    def clear_trader(self, address: str) -> None:
        """Clear previous state for a trader.

        Args:
            address: Trader address
        """
        if address in self._prev_states:
            del self._prev_states[address]
