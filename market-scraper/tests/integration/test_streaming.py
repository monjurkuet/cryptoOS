# tests/integration/test_streaming.py

"""Integration tests for WebSocket streaming."""

import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from market_scraper.core.events import EventType, MarketDataPayload, StandardEvent
from market_scraper.event_bus.memory_bus import MemoryEventBus
from market_scraper.streaming import WebSocketServer, SubscriptionManager


class TestStreamingIntegration:
    """Integration tests for streaming layer."""

    @pytest.fixture
    async def event_bus(self):
        """Create and start a memory event bus."""
        bus = MemoryEventBus()
        await bus.connect()
        yield bus
        await bus.disconnect()

    @pytest.fixture
    async def server(self, event_bus):
        """Create and start a WebSocket server."""
        srv = WebSocketServer(
            host="127.0.0.1",
            port=18765,  # Use different port to avoid conflicts
            event_bus=event_bus,
        )
        await srv.start()
        yield srv
        await srv.stop()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_server_starts_and_stops(self, event_bus: MemoryEventBus) -> None:
        """Test that server can start and stop correctly."""
        server = WebSocketServer(
            host="127.0.0.1",
            port=18766,
            event_bus=event_bus,
        )

        await server.start()
        assert server._running is True
        assert server._server is not None

        await server.stop()
        assert server._running is False

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_subscription_manager_integration(self) -> None:
        """Test subscription manager with multiple clients."""
        manager = SubscriptionManager()

        # Create mock websockets
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()

        # Subscribe clients
        manager.subscribe("client_1", ws1, "BTC-USD", "trade")
        manager.subscribe("client_1", ws1, "ETH-USD", "trade")
        manager.subscribe("client_2", ws2, "BTC-USD", "trade")
        manager.subscribe("client_3", ws3, "BTC-USD", "ticker")

        # Get subscribers for BTC-USD trades
        subscribers = manager.get_subscribers("BTC-USD", "trade")
        assert len(subscribers) == 2
        assert ws1 in subscribers
        assert ws2 in subscribers
        assert ws3 not in subscribers

        # Unsubscribe client_1
        manager.unsubscribe("client_1", "BTC-USD")
        subscribers = manager.get_subscribers("BTC-USD", "trade")
        assert len(subscribers) == 1
        assert ws1 not in subscribers

        # Remove all for client_2
        manager.remove_client("client_2")
        subscribers = manager.get_subscribers("BTC-USD", "trade")
        assert len(subscribers) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_event_broadcasting_flow(
        self,
        server: WebSocketServer,
        event_bus: MemoryEventBus,
    ) -> None:
        """Test end-to-end event broadcasting flow."""
        # Create mock client
        mock_ws = AsyncMock()
        client_id = str(id(mock_ws))

        # Subscribe to BTC-USD trades
        server._subscription_manager.subscribe(client_id, mock_ws, "BTC-USD", "trade")

        # Publish an event
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            volume=1.5,
            timestamp=datetime.utcnow(),
        )
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="test_exchange",
            payload=payload.model_dump(),
        )

        await event_bus.publish(event)

        # Give the event bus time to process
        await asyncio.sleep(0.1)

        # Verify the event was broadcast
        assert mock_ws.send.called
        sent_data = mock_ws.send.call_args[0][0]
        parsed = json.loads(sent_data)
        assert parsed["type"] == "event"
        assert parsed["data"]["event_type"] == "trade"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_wildcard_subscriptions(
        self,
        server: WebSocketServer,
        event_bus: MemoryEventBus,
    ) -> None:
        """Test wildcard subscription patterns."""
        mock_ws = AsyncMock()
        client_id = str(id(mock_ws))

        # Subscribe to all BTC events (wildcard event type)
        server._subscription_manager.subscribe(client_id, mock_ws, "BTC-USD", "*")

        # Publish different event types
        for event_type in [EventType.TRADE, EventType.TICKER, EventType.OHLCV]:
            event = StandardEvent.create(
                event_type=event_type,
                source="test",
                payload={"symbol": "BTC-USD", "price": 50000.0},
            )
            await event_bus.publish(event)

        await asyncio.sleep(0.1)

        # Should receive all 3 events
        assert mock_ws.send.call_count == 3

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_symbol_filtering(
        self,
        server: WebSocketServer,
        event_bus: MemoryEventBus,
    ) -> None:
        """Test that events are filtered by symbol correctly."""
        mock_ws = AsyncMock()
        client_id = str(id(mock_ws))

        # Subscribe only to BTC
        server._subscription_manager.subscribe(client_id, mock_ws, "BTC-USD", "trade")

        # Publish BTC event
        btc_event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload={"symbol": "BTC-USD", "price": 50000.0},
        )
        await event_bus.publish(btc_event)

        # Publish ETH event
        eth_event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload={"symbol": "ETH-USD", "price": 3000.0},
        )
        await event_bus.publish(eth_event)

        await asyncio.sleep(0.1)

        # Should only receive BTC event
        assert mock_ws.send.call_count == 1
        sent_data = json.loads(mock_ws.send.call_args[0][0])
        assert sent_data["data"]["payload"]["symbol"] == "BTC-USD"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_server_statistics(self, server: WebSocketServer) -> None:
        """Test server statistics collection."""
        # Add some subscriptions
        mock_ws = AsyncMock()
        server._subscription_manager.subscribe("c1", mock_ws, "BTC-USD", "trade")
        server._subscription_manager.subscribe("c1", mock_ws, "ETH-USD", "trade")
        server._subscription_manager.subscribe("c2", AsyncMock(), "BTC-USD", "ticker")

        stats = server.get_stats()

        assert stats["running"] is True
        assert stats["total_clients"] == 2
        assert stats["total_subscriptions"] == 3

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_message_protocol(self) -> None:
        """Test WebSocket message protocol parsing."""
        server = WebSocketServer()
        mock_ws = AsyncMock()

        # Test subscribe message
        await server._handle_message(
            mock_ws,
            json.dumps(
                {
                    "action": "subscribe",
                    "symbols": ["BTC-USD"],
                    "event_types": ["trade"],
                }
            ),
        )

        response = json.loads(mock_ws.send.call_args[0][0])
        assert response["type"] == "ack"
        assert response["action"] == "subscribed"

        # Test ping message
        mock_ws.reset_mock()
        await server._handle_message(mock_ws, json.dumps({"action": "ping"}))

        response = json.loads(mock_ws.send.call_args[0][0])
        assert response["type"] == "pong"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_subscriptions(self) -> None:
        """Test handling of concurrent subscription operations."""
        manager = SubscriptionManager()
        clients = []
        num_clients = 10

        # Create multiple clients
        for i in range(num_clients):
            ws = AsyncMock()
            clients.append((f"client_{i}", ws))
            manager.subscribe(f"client_{i}", ws, "BTC-USD", "trade")

        # Verify all subscriptions
        subscribers = manager.get_subscribers("BTC-USD", "trade")
        assert len(subscribers) == num_clients

        # Concurrently unsubscribe half (unsubscribe is sync)
        for i in range(0, num_clients, 2):
            manager.unsubscribe(f"client_{i}", "BTC-USD")

        subscribers = manager.get_subscribers("BTC-USD", "trade")
        assert len(subscribers) == num_clients // 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_broadcast_with_failed_clients(
        self,
        server: WebSocketServer,
        event_bus: MemoryEventBus,
    ) -> None:
        """Test broadcasting when some clients fail."""
        # Create one good client and one failing client
        good_ws = AsyncMock()
        bad_ws = AsyncMock()
        bad_ws.send = AsyncMock(side_effect=Exception("Connection failed"))

        server._subscription_manager.subscribe("good", good_ws, "BTC-USD", "trade")
        server._subscription_manager.subscribe("bad", bad_ws, "BTC-USD", "trade")

        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload={"symbol": "BTC-USD", "price": 50000.0},
        )

        await event_bus.publish(event)
        await asyncio.sleep(0.1)

        # Good client should still receive the message
        assert good_ws.send.called
