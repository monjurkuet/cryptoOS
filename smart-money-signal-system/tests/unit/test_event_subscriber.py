"""Tests for EventSubscriber."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from signal_system.event_subscriber import EventSubscriber


class TestEventSubscriber:
    """Tests for EventSubscriber class."""

    def test_init(self) -> None:
        """Test initialization."""
        config = MagicMock()
        config.url = "redis://localhost:6379"

        subscriber = EventSubscriber(config)
        assert subscriber._redis_url == "redis://localhost:6379"
        assert subscriber._handlers == {}

    def test_subscribe(self) -> None:
        """Test subscribing to event types."""
        config = MagicMock()
        config.url = "redis://localhost:6379"
        subscriber = EventSubscriber(config)

        handler = MagicMock()
        subscriber.subscribe("trader_positions", handler)

        assert "trader_positions" in subscriber._handlers
        assert handler in subscriber._handlers["trader_positions"]

    def test_subscribe_multiple_handlers(self) -> None:
        """Test subscribing multiple handlers to same event type."""
        config = MagicMock()
        config.url = "redis://localhost:6379"
        subscriber = EventSubscriber(config)

        handler1 = MagicMock()
        handler2 = MagicMock()
        subscriber.subscribe("trader_positions", handler1)
        subscriber.subscribe("trader_positions", handler2)

        assert len(subscriber._handlers["trader_positions"]) == 2

    def test_get_stats(self) -> None:
        """Test getting stats."""
        config = MagicMock()
        config.url = "redis://localhost:6379"
        subscriber = EventSubscriber(config)

        subscriber.subscribe("event1", MagicMock())
        subscriber.subscribe("event2", MagicMock())

        stats = subscriber.get_stats()
        assert stats["subscriptions"] == 2
        assert stats["connected"] is False

    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        """Test successful connection."""
        config = MagicMock()
        config.url = "redis://localhost:6379"
        subscriber = EventSubscriber(config)

        with patch("redis.asyncio.from_url") as mock_redis:
            mock_client = AsyncMock()
            mock_redis.return_value = mock_client

            await subscriber.connect()

            mock_redis.assert_called_once_with("redis://localhost:6379")
            mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self) -> None:
        """Test disconnection."""
        config = MagicMock()
        config.url = "redis://localhost:6379"
        subscriber = EventSubscriber(config)

        # Mock connected state
        subscriber._redis = AsyncMock()

        await subscriber.disconnect()

        subscriber._redis.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message(self) -> None:
        """Test message handling."""
        config = MagicMock()
        config.url = "redis://localhost:6379"
        subscriber = EventSubscriber(config)

        handler = AsyncMock()
        subscriber.subscribe("trader_positions", handler)

        # Simulate message
        message = {
            "channel": b"events:trader_positions",
            "data": b'{"event_type": "trader_positions", "payload": {"test": true}}',
        }

        await subscriber._handle_message(message)

        handler.assert_called_once()
        call_arg = handler.call_args[0][0]
        assert call_arg["event_type"] == "trader_positions"
        assert call_arg["payload"]["test"] is True

    @pytest.mark.asyncio
    async def test_handle_message_json_error(self) -> None:
        """Test handling malformed JSON message."""
        config = MagicMock()
        config.url = "redis://localhost:6379"
        subscriber = EventSubscriber(config)

        handler = AsyncMock()
        subscriber.subscribe("trader_positions", handler)

        # Simulate malformed message
        message = {
            "channel": b"events:trader_positions",
            "data": b'not valid json',
        }

        # Should not raise, just log and skip
        await subscriber._handle_message(message)

        handler.assert_not_called()
