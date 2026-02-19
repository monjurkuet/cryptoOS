# src/market_scraper/connectors/hyperliquid/collectors/trader_orders.py

"""Trader Orders WebSocket Collector.

Collects real-time order data for tracked traders.
Orders come from webData2 subscription (same as positions).
"""

import asyncio
from datetime import datetime
from typing import Any

import structlog

from market_scraper.core.config import HyperliquidSettings
from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus

logger = structlog.get_logger(__name__)


class TraderOrdersCollector:
    """Collects real-time trader orders via WebSocket.

    Orders are extracted from webData2 messages which contain
    both positions and orders data.

    Features:
    - Extracts orders from webData2 messages
    - Filters by configured symbol
    - Tracks order state changes (open, filled, cancelled)
    """

    def __init__(
        self,
        event_bus: EventBus,
        config: HyperliquidSettings,
    ) -> None:
        """Initialize the orders collector.

        Args:
            event_bus: Event bus for publishing events
            config: Hyperliquid settings
        """
        self.event_bus = event_bus
        self.config = config

        # Order state tracking per trader
        self._order_states: dict[str, dict[int, dict]] = {}  # address -> oid -> order

        # Stats
        self._orders_processed = 0
        self._orders_emitted = 0

    def process_orders(
        self,
        address: str,
        orders_data: list[dict],
    ) -> list[StandardEvent]:
        """Process orders from webData2 message.

        Args:
            address: Trader Ethereum address
            orders_data: List of order data from clearinghouse

        Returns:
            List of order events
        """
        events = []

        # Get previous order state for this trader
        prev_orders = self._order_states.get(address, {})
        curr_orders = {}

        for order in orders_data:
            order_data = order.get("order", order)
            oid = order_data.get("oid")

            if oid is None:
                continue

            coin = order_data.get("coin", "")

            # Filter by configured symbol
            if coin != self.config.symbol:
                continue

            curr_orders[oid] = order_data
            self._orders_processed += 1

            # Detect order changes
            prev_order = prev_orders.get(oid)

            if prev_order is None:
                # New order
                event = self._create_order_event(
                    address=address,
                    order=order_data,
                    action="new",
                )
                if event:
                    events.append(event)
                    self._orders_emitted += 1

            else:
                # Check for status changes
                prev_status = prev_order.get("orderStatus", prev_order.get("status", ""))
                curr_status = order_data.get("orderStatus", order_data.get("status", ""))

                if prev_status != curr_status:
                    event = self._create_order_event(
                        address=address,
                        order=order_data,
                        action=curr_status,  # "filled", "cancelled", etc.
                    )
                    if event:
                        events.append(event)
                        self._orders_emitted += 1

        # Check for cancelled/closed orders (in prev but not in curr)
        for oid, prev_order in prev_orders.items():
            if oid not in curr_orders:
                event = self._create_order_event(
                    address=address,
                    order=prev_order,
                    action="closed",
                )
                if event:
                    events.append(event)
                    self._orders_emitted += 1

        # Update state
        self._order_states[address] = curr_orders

        return events

    def _create_order_event(
        self,
        address: str,
        order: dict,
        action: str,
    ) -> StandardEvent | None:
        """Create an order event.

        Args:
            address: Trader address
            order: Order data
            action: Action type (new, filled, cancelled, closed)

        Returns:
            StandardEvent or None
        """
        try:
            return StandardEvent.create(
                event_type="trader_order",
                source="hyperliquid_trader_ws",
                payload={
                    "address": address,
                    "symbol": order.get("coin", self.config.symbol),
                    "order_id": order.get("oid"),
                    "side": order.get("side", ""),  # "B" or "A"
                    "price": float(order.get("limitPx", 0)),
                    "size": float(order.get("origSz", 0)),
                    "filled_size": float(order.get("sz", 0)),  # Remaining size
                    "action": action,
                    "order_type": order.get("orderType", ""),
                    "timestamp": datetime.utcnow().isoformat(),
                    "reduce_only": order.get("reduceOnly", False),
                    "trigger_condition": order.get("trigger", {}).get("triggerType") if order.get("trigger") else None,
                },
            )
        except Exception as e:
            logger.warning(
                "order_event_create_error",
                error=str(e),
                order=order,
            )
            return None

    def get_stats(self) -> dict[str, Any]:
        """Get collector statistics.

        Returns:
            Stats dictionary
        """
        return {
            "orders_processed": self._orders_processed,
            "orders_emitted": self._orders_emitted,
            "tracked_traders": len(self._order_states),
            "total_tracked_orders": sum(len(o) for o in self._order_states.values()),
        }

    def clear_trader(self, address: str) -> None:
        """Clear order state for a trader.

        Args:
            address: Trader address
        """
        if address in self._order_states:
            del self._order_states[address]
