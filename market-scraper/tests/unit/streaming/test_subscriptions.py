# tests/unit/streaming/test_subscriptions.py

"""Test suite for SubscriptionManager."""

from unittest.mock import MagicMock

import pytest

from market_scraper.streaming.subscriptions import SubscriptionManager


class TestSubscriptionManager:
    """Test suite for subscription management."""

    @pytest.fixture
    def manager(self) -> SubscriptionManager:
        """Create a fresh subscription manager."""
        return SubscriptionManager()

    @pytest.fixture
    def mock_websocket(self) -> MagicMock:
        """Create a mock websocket connection."""
        return MagicMock()

    def test_init(self, manager: SubscriptionManager) -> None:
        """Test subscription manager initialization."""
        assert manager._subscriptions == {}
        assert manager._subscribers == {}
        assert manager._client_websockets == {}

    def test_subscribe_single(
        self,
        manager: SubscriptionManager,
        mock_websocket: MagicMock,
    ) -> None:
        """Test subscribing a client to a single symbol."""
        client_id = "client_1"
        symbol = "BTC-USD"
        event_type = "trade"

        result = manager.subscribe(client_id, mock_websocket, symbol, event_type)

        assert result is True
        assert (symbol.upper(), event_type) in manager._subscriptions[client_id]
        assert mock_websocket in manager._subscribers[(symbol.upper(), event_type)]
        assert manager._client_websockets[client_id] == mock_websocket

    def test_subscribe_duplicate(
        self,
        manager: SubscriptionManager,
        mock_websocket: MagicMock,
    ) -> None:
        """Test subscribing twice to same symbol returns False."""
        client_id = "client_1"
        symbol = "BTC-USD"
        event_type = "trade"

        manager.subscribe(client_id, mock_websocket, symbol, event_type)
        result = manager.subscribe(client_id, mock_websocket, symbol, event_type)

        assert result is False
        assert len(manager._subscriptions[client_id]) == 1

    def test_subscribe_multiple_symbols(
        self,
        manager: SubscriptionManager,
        mock_websocket: MagicMock,
    ) -> None:
        """Test subscribing to multiple symbols."""
        client_id = "client_1"
        symbols = ["BTC-USD", "ETH-USD", "SOL-USD"]

        for symbol in symbols:
            manager.subscribe(client_id, mock_websocket, symbol, "trade")

        assert len(manager._subscriptions[client_id]) == 3

    def test_subscribe_multiple_event_types(
        self,
        manager: SubscriptionManager,
        mock_websocket: MagicMock,
    ) -> None:
        """Test subscribing to multiple event types for same symbol."""
        client_id = "client_1"
        symbol = "BTC-USD"
        event_types = ["trade", "ticker", "order_book"]

        for event_type in event_types:
            manager.subscribe(client_id, mock_websocket, symbol, event_type)

        assert len(manager._subscriptions[client_id]) == 3

    def test_unsubscribe_single(
        self,
        manager: SubscriptionManager,
        mock_websocket: MagicMock,
    ) -> None:
        """Test unsubscribing from a symbol."""
        client_id = "client_1"
        symbol = "BTC-USD"
        event_type = "trade"

        manager.subscribe(client_id, mock_websocket, symbol, event_type)
        removed = manager.unsubscribe(client_id, symbol)

        assert removed == 1
        assert (symbol.upper(), event_type) not in manager._subscriptions[client_id]
        assert mock_websocket not in manager._subscribers[(symbol.upper(), event_type)]

    def test_unsubscribe_specific_event_type(
        self,
        manager: SubscriptionManager,
        mock_websocket: MagicMock,
    ) -> None:
        """Test unsubscribing from specific event type only."""
        client_id = "client_1"
        symbol = "BTC-USD"

        manager.subscribe(client_id, mock_websocket, symbol, "trade")
        manager.subscribe(client_id, mock_websocket, symbol, "ticker")

        removed = manager.unsubscribe(client_id, symbol, "trade")

        assert removed == 1
        assert len(manager._subscriptions[client_id]) == 1
        assert (symbol.upper(), "ticker") in manager._subscriptions[client_id]

    def test_unsubscribe_all(
        self,
        manager: SubscriptionManager,
        mock_websocket: MagicMock,
    ) -> None:
        """Test unsubscribing from all symbols."""
        client_id = "client_1"
        symbols = ["BTC-USD", "ETH-USD", "SOL-USD"]

        for symbol in symbols:
            manager.subscribe(client_id, mock_websocket, symbol, "trade")

        removed = manager.unsubscribe_all(client_id)

        assert removed == 3
        assert client_id not in manager._subscriptions
        assert client_id not in manager._client_websockets

    def test_unsubscribe_nonexistent_client(self, manager: SubscriptionManager) -> None:
        """Test unsubscribing from non-existent client returns 0."""
        removed = manager.unsubscribe("nonexistent", "BTC-USD")
        assert removed == 0

    def test_get_subscribers_exact_match(
        self,
        manager: SubscriptionManager,
        mock_websocket: MagicMock,
    ) -> None:
        """Test getting subscribers with exact symbol and event type match."""
        client_id = "client_1"
        symbol = "BTC-USD"
        event_type = "trade"

        manager.subscribe(client_id, mock_websocket, symbol, event_type)
        subscribers = manager.get_subscribers(symbol, event_type)

        assert len(subscribers) == 1
        assert mock_websocket in subscribers

    def test_get_subscribers_wildcard_symbol(
        self,
        manager: SubscriptionManager,
        mock_websocket: MagicMock,
    ) -> None:
        """Test getting subscribers with wildcard symbol."""
        client_id = "client_1"

        manager.subscribe(client_id, mock_websocket, "*", "trade")
        subscribers = manager.get_subscribers("BTC-USD", "trade")

        assert len(subscribers) == 1
        assert mock_websocket in subscribers

    def test_get_subscribers_wildcard_event(
        self,
        manager: SubscriptionManager,
        mock_websocket: MagicMock,
    ) -> None:
        """Test getting subscribers with wildcard event type."""
        client_id = "client_1"

        manager.subscribe(client_id, mock_websocket, "BTC-USD", "*")
        subscribers = manager.get_subscribers("BTC-USD", "trade")

        assert len(subscribers) == 1
        assert mock_websocket in subscribers

    def test_get_subscribers_wildcard_both(
        self,
        manager: SubscriptionManager,
        mock_websocket: MagicMock,
    ) -> None:
        """Test getting subscribers with both wildcards."""
        client_id = "client_1"

        manager.subscribe(client_id, mock_websocket, "*", "*")
        subscribers = manager.get_subscribers("BTC-USD", "trade")

        assert len(subscribers) == 1
        assert mock_websocket in subscribers

    def test_get_subscribers_multiple_clients(
        self,
        manager: SubscriptionManager,
    ) -> None:
        """Test getting subscribers with multiple clients."""
        ws1 = MagicMock()
        ws2 = MagicMock()
        ws3 = MagicMock()

        manager.subscribe("client_1", ws1, "BTC-USD", "trade")
        manager.subscribe("client_2", ws2, "BTC-USD", "trade")
        manager.subscribe("client_3", ws3, "ETH-USD", "trade")

        subscribers = manager.get_subscribers("BTC-USD", "trade")

        assert len(subscribers) == 2
        assert ws1 in subscribers
        assert ws2 in subscribers
        assert ws3 not in subscribers

    def test_get_client_subscriptions(
        self,
        manager: SubscriptionManager,
        mock_websocket: MagicMock,
    ) -> None:
        """Test getting client subscriptions."""
        client_id = "client_1"
        symbols = ["BTC-USD", "ETH-USD"]

        for symbol in symbols:
            manager.subscribe(client_id, mock_websocket, symbol, "trade")

        subscriptions = manager.get_client_subscriptions(client_id)

        assert len(subscriptions) == 2
        assert ("BTC-USD", "trade") in subscriptions
        assert ("ETH-USD", "trade") in subscriptions

    def test_remove_client(
        self,
        manager: SubscriptionManager,
        mock_websocket: MagicMock,
    ) -> None:
        """Test removing a client."""
        client_id = "client_1"

        manager.subscribe(client_id, mock_websocket, "BTC-USD", "trade")
        manager.subscribe(client_id, mock_websocket, "ETH-USD", "trade")

        removed = manager.remove_client(client_id)

        assert removed == 2
        assert client_id not in manager._subscriptions
        assert client_id not in manager._client_websockets

    def test_symbol_normalization(
        self,
        manager: SubscriptionManager,
        mock_websocket: MagicMock,
    ) -> None:
        """Test that symbols are normalized to uppercase."""
        client_id = "client_1"

        manager.subscribe(client_id, mock_websocket, "btc-usd", "trade")
        subscribers = manager.get_subscribers("BTC-USD", "trade")

        assert len(subscribers) == 1
        assert mock_websocket in subscribers

    def test_get_stats(
        self,
        manager: SubscriptionManager,
        mock_websocket: MagicMock,
    ) -> None:
        """Test getting subscription statistics."""
        manager.subscribe("client_1", mock_websocket, "BTC-USD", "trade")
        manager.subscribe("client_1", mock_websocket, "ETH-USD", "trade")
        manager.subscribe("client_2", MagicMock(), "BTC-USD", "trade")

        stats = manager.get_stats()

        assert stats["total_clients"] == 2
        assert stats["total_subscriptions"] == 3
        assert stats["unique_symbol_event_pairs"] == 2
        assert stats["avg_subscriptions_per_client"] == 1.5

    def test_get_stats_empty(self, manager: SubscriptionManager) -> None:
        """Test getting stats with no subscriptions."""
        stats = manager.get_stats()

        assert stats["total_clients"] == 0
        assert stats["total_subscriptions"] == 0
        assert stats["avg_subscriptions_per_client"] == 0
