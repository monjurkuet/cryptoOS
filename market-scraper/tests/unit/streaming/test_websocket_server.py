# tests/unit/streaming/test_websocket_server.py

"""Test suite for WebSocketServer."""

import asyncio
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import websockets

from market_scraper.core.events import EventType, MarketDataPayload, StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.streaming.websocket_server import WebSocketServer


class MockWebSocket:
    """Mock WebSocket protocol for testing."""

    def __init__(self) -> None:
        self.sent_messages: list[str] = []
        self.remote_address = ("127.0.0.1", 12345)
        self._closed = False

    async def send(self, message: str) -> None:
        """Record sent messages."""
        if self._closed:
            raise Exception("WebSocket closed")
        self.sent_messages.append(message)

    async def __aiter__(self):
        """Make async iterable."""
        return self

    async def __anext__(self):
        """Async iterator."""
        raise StopAsyncIteration

    def close(self) -> None:
        """Close the mock websocket."""
        self._closed = True


class TestWebSocketServer:
    """Test suite for WebSocketServer."""

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        """Create a mock event bus."""
        bus = MagicMock(spec=EventBus)
        bus.subscribe = AsyncMock()
        return bus

    @pytest.fixture
    def server(self, mock_event_bus: MagicMock) -> WebSocketServer:
        """Create a WebSocket server instance."""
        return WebSocketServer(
            host="127.0.0.1",
            port=8765,
            event_bus=mock_event_bus,
        )

    @pytest.fixture
    def sample_event(self) -> StandardEvent:
        """Create a sample event for testing."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            timestamp=datetime.utcnow(),
        )
        return StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload=payload.model_dump(),
        )

    @pytest.mark.asyncio
    async def test_init(self, server: WebSocketServer) -> None:
        """Test server initialization."""
        assert server._host == "127.0.0.1"
        assert server._port == 8765
        assert server._running is False
        assert server._event_bus is not None
        assert server._subscription_manager is not None

    @pytest.mark.asyncio
    async def test_init_without_event_bus(self) -> None:
        """Test server initialization without event bus."""
        server = WebSocketServer()
        assert server._event_bus is None

    @pytest.mark.asyncio
    async def test_start_stop(
        self,
        server: WebSocketServer,
        mock_event_bus: MagicMock,
    ) -> None:
        """Test server start and stop lifecycle."""
        mock_server = AsyncMock()
        mock_serve = AsyncMock(return_value=mock_server)

        with patch("websockets.serve", mock_serve):
            await server.start()
            assert server._running is True
            mock_event_bus.subscribe.assert_called_once()

            await server.stop()
            assert server._running is False
            mock_server.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_without_event_bus(self) -> None:
        """Test server start without event bus."""
        server = WebSocketServer()
        mock_server = AsyncMock()
        mock_serve = AsyncMock(return_value=mock_server)

        with patch("websockets.serve", mock_serve):
            await server.start()
            assert server._running is True
            # Should not fail without event bus

    @pytest.mark.asyncio
    async def test_handle_subscribe_message(self, server: WebSocketServer) -> None:
        """Test handling subscribe message."""
        websocket = MockWebSocket()
        message = json.dumps(
            {
                "action": "subscribe",
                "symbols": ["BTC-USD"],
                "event_types": ["trade"],
            }
        )

        await server._handle_message(websocket, message)

        assert len(websocket.sent_messages) == 1
        response = json.loads(websocket.sent_messages[0])
        assert response["type"] == "ack"
        assert response["action"] == "subscribed"
        assert "BTC-USD" in response["data"]["symbols"]

    @pytest.mark.asyncio
    async def test_handle_subscribe_no_symbols(self, server: WebSocketServer) -> None:
        """Test handling subscribe message without symbols."""
        websocket = MockWebSocket()
        message = json.dumps(
            {
                "action": "subscribe",
            }
        )

        await server._handle_message(websocket, message)

        assert len(websocket.sent_messages) == 1
        response = json.loads(websocket.sent_messages[0])
        assert response["type"] == "error"

    @pytest.mark.asyncio
    async def test_handle_unsubscribe_message(self, server: WebSocketServer) -> None:
        """Test handling unsubscribe message."""
        websocket = MockWebSocket()
        client_id = str(id(websocket))

        # First subscribe
        server._subscription_manager.subscribe(client_id, websocket, "BTC-USD", "trade")

        # Then unsubscribe
        message = json.dumps(
            {
                "action": "unsubscribe",
                "symbols": ["BTC-USD"],
            }
        )

        await server._handle_message(websocket, message)

        assert len(websocket.sent_messages) == 1
        response = json.loads(websocket.sent_messages[0])
        assert response["type"] == "ack"
        assert response["action"] == "unsubscribed"
        assert response["data"]["removed_count"] == 1

    @pytest.mark.asyncio
    async def test_handle_ping_message(self, server: WebSocketServer) -> None:
        """Test handling ping message."""
        websocket = MockWebSocket()
        message = json.dumps({"action": "ping"})

        await server._handle_message(websocket, message)

        assert len(websocket.sent_messages) == 1
        response = json.loads(websocket.sent_messages[0])
        assert response["type"] == "pong"

    @pytest.mark.asyncio
    async def test_handle_unknown_action(self, server: WebSocketServer) -> None:
        """Test handling unknown action."""
        websocket = MockWebSocket()
        message = json.dumps({"action": "unknown"})

        await server._handle_message(websocket, message)

        assert len(websocket.sent_messages) == 1
        response = json.loads(websocket.sent_messages[0])
        assert response["type"] == "error"
        assert "unknown" in response["error"].lower()

    @pytest.mark.asyncio
    async def test_handle_invalid_json(self, server: WebSocketServer) -> None:
        """Test handling invalid JSON."""
        websocket = MockWebSocket()
        message = "not valid json"

        await server._handle_message(websocket, message)

        assert len(websocket.sent_messages) == 1
        response = json.loads(websocket.sent_messages[0])
        assert response["type"] == "error"
        assert "json" in response["error"].lower()

    @pytest.mark.asyncio
    async def test_on_event_broadcast(
        self,
        server: WebSocketServer,
        sample_event: StandardEvent,
    ) -> None:
        """Test event broadcasting to subscribers."""
        server._running = True
        websocket = MockWebSocket()
        client_id = str(id(websocket))

        # Subscribe to BTC-USD trades
        server._subscription_manager.subscribe(client_id, websocket, "BTC-USD", "trade")

        # Broadcast event
        await server._on_event(sample_event)

        assert len(websocket.sent_messages) == 1
        response = json.loads(websocket.sent_messages[0])
        assert response["type"] == "event"
        assert response["data"]["event_type"] == "trade"

    @pytest.mark.asyncio
    async def test_on_event_no_subscribers(
        self,
        server: WebSocketServer,
        sample_event: StandardEvent,
    ) -> None:
        """Test event broadcasting with no subscribers."""
        server._running = True
        websocket = MockWebSocket()
        client_id = str(id(websocket))

        # Subscribe to different symbol
        server._subscription_manager.subscribe(client_id, websocket, "ETH-USD", "trade")

        # Broadcast BTC event (should not be received)
        await server._on_event(sample_event)

        assert len(websocket.sent_messages) == 0

    @pytest.mark.asyncio
    async def test_on_event_not_running(
        self,
        server: WebSocketServer,
        sample_event: StandardEvent,
    ) -> None:
        """Test event broadcasting when server not running."""
        server._running = False
        websocket = MockWebSocket()
        client_id = str(id(websocket))

        server._subscription_manager.subscribe(client_id, websocket, "BTC-USD", "trade")

        await server._on_event(sample_event)

        assert len(websocket.sent_messages) == 0

    @pytest.mark.asyncio
    async def test_send_ack(self, server: WebSocketServer) -> None:
        """Test sending acknowledgment."""
        websocket = MockWebSocket()

        await server._send_ack(websocket, "test_action", {"key": "value"})

        assert len(websocket.sent_messages) == 1
        response = json.loads(websocket.sent_messages[0])
        assert response["type"] == "ack"
        assert response["action"] == "test_action"
        assert response["data"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_send_error(self, server: WebSocketServer) -> None:
        """Test sending error message."""
        websocket = MockWebSocket()

        await server._send_error(websocket, "Test error message")

        assert len(websocket.sent_messages) == 1
        response = json.loads(websocket.sent_messages[0])
        assert response["type"] == "error"
        assert response["error"] == "Test error message"

    @pytest.mark.asyncio
    async def test_handle_connection_cleanup(
        self,
        server: WebSocketServer,
    ) -> None:
        """Test connection cleanup on disconnect."""
        websocket = MockWebSocket()
        client_id = str(id(websocket))

        # Add subscription before connection
        server._subscription_manager.subscribe(client_id, websocket, "BTC-USD", "trade")
        assert len(server._subscription_manager._subscriptions[client_id]) == 1

        # Simulate connection with immediate disconnect
        async def mock_message_iterator():
            raise websockets.exceptions.ConnectionClosed(None, None)

        websocket.__aiter__ = mock_message_iterator

        with patch.object(
            websocket, "__aiter__", side_effect=websockets.exceptions.ConnectionClosed(None, None)
        ):
            # Connection handler should clean up
            try:
                await server._handle_connection(websocket, "/")
            except Exception:
                pass

        # Subscription should be cleaned up
        assert client_id not in server._subscription_manager._subscriptions

    def test_get_stats(self, server: WebSocketServer) -> None:
        """Test getting server statistics."""
        stats = server.get_stats()

        assert stats["running"] is False
        assert stats["host"] == "127.0.0.1"
        assert stats["port"] == 8765
        assert "total_clients" in stats
        assert "total_subscriptions" in stats
