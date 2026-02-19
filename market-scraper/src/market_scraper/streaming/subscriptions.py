# src/market_scraper/streaming/subscriptions.py

"""Subscription management for WebSocket streaming."""

from collections import defaultdict
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SubscriptionManager:
    """Manages WebSocket client subscriptions for market data streaming.

    Provides efficient tracking of which clients are subscribed to which
    symbols and event types for targeted broadcasting.

    Data Structures:
        - _subscriptions: Maps client_id to list of (symbol, event_type) tuples
        - _subscribers: Maps (symbol, event_type) to set of websocket connections
        - _client_websockets: Maps client_id to websocket connection
    """

    def __init__(self) -> None:
        """Initialize the subscription manager."""
        # client_id -> [(symbol, event_type), ...]
        self._subscriptions: dict[str, list[tuple[str, str]]] = defaultdict(list)

        # (symbol, event_type) -> {websocket1, websocket2, ...}
        self._subscribers: dict[tuple[str, str], set[object]] = defaultdict(set)

        # client_id -> websocket connection
        self._client_websockets: dict[str, object] = {}

        self._logger = logger.bind(component="subscription_manager")

    def subscribe(
        self,
        client_id: str,
        websocket: object,
        symbol: str,
        event_type: str = "*",
    ) -> bool:
        """Subscribe a client to a symbol and event type.

        Args:
            client_id: Unique client identifier
            websocket: WebSocket connection object
            symbol: Trading symbol (e.g., "BTC-USD")
            event_type: Event type filter (e.g., "trade", "ticker", "*" for all)

        Returns:
            True if subscription was added, False if already subscribed
        """
        # Store websocket reference for this client
        self._client_websockets[client_id] = websocket

        # Normalize symbol
        symbol = symbol.upper()

        # Check if already subscribed
        subscription = (symbol, event_type)
        if subscription in self._subscriptions[client_id]:
            self._logger.debug(
                "Client already subscribed",
                client_id=client_id,
                symbol=symbol,
                event_type=event_type,
            )
            return False

        # Add subscription
        self._subscriptions[client_id].append(subscription)
        self._subscribers[subscription].add(websocket)

        self._logger.debug(
            "Client subscribed",
            client_id=client_id,
            symbol=symbol,
            event_type=event_type,
            total_subscriptions=len(self._subscriptions[client_id]),
        )

        return True

    def unsubscribe(
        self,
        client_id: str,
        symbol: str,
        event_type: str | None = None,
    ) -> int:
        """Unsubscribe a client from a symbol.

        Args:
            client_id: Unique client identifier
            symbol: Trading symbol to unsubscribe from
            event_type: Specific event type to unsubscribe, or None for all types

        Returns:
            Number of subscriptions removed
        """
        if client_id not in self._subscriptions:
            return 0

        # Normalize symbol
        symbol = symbol.upper()

        removed = 0
        websocket = self._client_websockets.get(client_id)

        # Find matching subscriptions
        to_remove = []
        for sub in self._subscriptions[client_id]:
            sub_symbol, sub_event_type = sub
            if sub_symbol == symbol and (event_type is None or sub_event_type == event_type):
                to_remove.append(sub)

        # Remove subscriptions
        for sub in to_remove:
            self._subscriptions[client_id].remove(sub)
            if websocket:
                self._subscribers[sub].discard(websocket)
                # Clean up empty subscriber sets
                if not self._subscribers[sub]:
                    del self._subscribers[sub]
            removed += 1

        if removed > 0:
            self._logger.debug(
                "Client unsubscribed",
                client_id=client_id,
                symbol=symbol,
                event_type=event_type,
                removed_count=removed,
            )

        return removed

    def unsubscribe_all(self, client_id: str) -> int:
        """Remove all subscriptions for a client.

        Args:
            client_id: Unique client identifier

        Returns:
            Number of subscriptions removed
        """
        if client_id not in self._subscriptions:
            return 0

        websocket = self._client_websockets.get(client_id)
        subscriptions = self._subscriptions[client_id].copy()

        # Remove from subscribers index
        for sub in subscriptions:
            if websocket:
                self._subscribers[sub].discard(websocket)
                if not self._subscribers[sub]:
                    del self._subscribers[sub]

        # Remove from client subscriptions
        count = len(self._subscriptions[client_id])
        del self._subscriptions[client_id]

        # Clean up websocket reference
        if client_id in self._client_websockets:
            del self._client_websockets[client_id]

        self._logger.debug(
            "Client unsubscribed from all",
            client_id=client_id,
            removed_count=count,
        )

        return count

    def get_subscribers(
        self,
        symbol: str | None,
        event_type: str,
    ) -> list[object]:
        """Get all websocket connections subscribed to a symbol and event type.

        This method also includes wildcard subscribers:
        - Subscribers with symbol="*" receive all symbols
        - Subscribers with event_type="*" receive all event types

        Args:
            symbol: Trading symbol (normalized to uppercase)
            event_type: Event type

        Returns:
            List of websocket connections that should receive this event
        """
        if symbol:
            symbol = symbol.upper()

        subscribers: set[object] = set()

        # Direct match
        if symbol and event_type:
            direct_key = (symbol, event_type)
            if direct_key in self._subscribers:
                subscribers.update(self._subscribers[direct_key])

        # Wildcard symbol with specific event type
        if event_type:
            wildcard_symbol_key = ("*", event_type)
            if wildcard_symbol_key in self._subscribers:
                subscribers.update(self._subscribers[wildcard_symbol_key])

        # Specific symbol with wildcard event type
        if symbol:
            wildcard_event_key = (symbol, "*")
            if wildcard_event_key in self._subscribers:
                subscribers.update(self._subscribers[wildcard_event_key])

        # Both wildcards
        full_wildcard_key = ("*", "*")
        if full_wildcard_key in self._subscribers:
            subscribers.update(self._subscribers[full_wildcard_key])

        return list(subscribers)

    def get_client_subscriptions(self, client_id: str) -> list[tuple[str, str]]:
        """Get all subscriptions for a specific client.

        Args:
            client_id: Unique client identifier

        Returns:
            List of (symbol, event_type) tuples
        """
        return self._subscriptions.get(client_id, []).copy()

    def remove_client(self, client_id: str) -> int:
        """Remove a client and all their subscriptions.

        Alias for unsubscribe_all for API consistency.

        Args:
            client_id: Unique client identifier

        Returns:
            Number of subscriptions removed
        """
        return self.unsubscribe_all(client_id)

    def get_stats(self) -> dict[str, Any]:
        """Get subscription manager statistics.

        Returns:
            Dictionary with subscription statistics
        """
        total_subscriptions = sum(len(subs) for subs in self._subscriptions.values())

        return {
            "total_clients": len(self._subscriptions),
            "total_subscriptions": total_subscriptions,
            "unique_symbol_event_pairs": len(self._subscribers),
            "avg_subscriptions_per_client": (
                total_subscriptions / len(self._subscriptions) if self._subscriptions else 0
            ),
        }
