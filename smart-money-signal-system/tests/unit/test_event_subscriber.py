"""Tests for EventSubscriber."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from signal_system.event_subscriber import EventSubscriber
from signal_system.config import RedisSettings


class TestEventSubscriber:
    """Tests for EventSubscriber class."""

    def test_init(self) -> None:
        """Test initialization."""
        settings = RedisSettings(url="redis://localhost:6379")

        subscriber = EventSubscriber(settings)
        assert subscriber.settings.url == "redis://localhost:6379"
        assert subscriber._handlers == {}
        assert subscriber._running is False

    def test_subscribe(self) -> None:
        """Test subscribing to event types."""
        settings = RedisSettings()
        subscriber = EventSubscriber(settings)

        async def handler(event: dict) -> None:
            pass

        subscriber.subscribe("trader_positions", handler)

        assert "trader_positions" in subscriber._handlers
        assert handler in subscriber._handlers["trader_positions"]

    def test_subscribe_multiple_handlers(self) -> None:
        """Test subscribing multiple handlers to same event type."""
        settings = RedisSettings()
        subscriber = EventSubscriber(settings)

        async def handler1(event: dict) -> None:
            pass

        async def handler2(event: dict) -> None:
            pass

        subscriber.subscribe("trader_positions", handler1)
        subscriber.subscribe("trader_positions", handler2)

        assert len(subscriber._handlers["trader_positions"]) == 2

    def test_get_stats(self) -> None:
        """Test getting stats."""
        settings = RedisSettings()
        subscriber = EventSubscriber(settings)

        async def handler(event: dict) -> None:
            pass

        subscriber.subscribe("event1", handler)
        subscriber.subscribe("event2", handler)

        stats = subscriber.get_stats()
        assert "event1" in stats["subscribed_events"]
        assert "event2" in stats["subscribed_events"]
        assert stats["running"] is False

    @pytest.mark.asyncio
    async def test_connect_success(self) -> None:
        """Test successful connection."""
        settings = RedisSettings(url="redis://localhost:6379")
        subscriber = EventSubscriber(settings)

        with patch("redis.asyncio.from_url") as mock_redis:
            mock_client = AsyncMock()
            mock_pubsub = AsyncMock()
            mock_client.pubsub.return_value = mock_pubsub
            mock_redis.return_value = mock_client

            await subscriber.connect()

            mock_redis.assert_called_once_with("redis://localhost:6379")

    @pytest.mark.asyncio
    async def test_disconnect(self) -> None:
        """Test disconnection."""
        settings = RedisSettings()
        subscriber = EventSubscriber(settings)

        # Mock connected state
        subscriber._redis = AsyncMock()
        subscriber._pubsub = AsyncMock()

        await subscriber.disconnect()

        subscriber._pubsub.unsubscribe.assert_called_once()
        subscriber._redis.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message(self) -> None:
        """Test message processing."""
        settings = RedisSettings()
        subscriber = EventSubscriber(settings)

        handler = AsyncMock()
        subscriber.subscribe("trader_positions", handler)

        # Simulate message
        message = {
            "channel": b"events:trader_positions",
            "data": b'{"event_type": "trader_positions", "payload": {"test": true}}',
        }

        await subscriber._process_message(message)

        handler.assert_called_once()
        call_arg = handler.call_args[0][0]
        assert call_arg["event_type"] == "trader_positions"
        assert call_arg["payload"]["test"] is True

    @pytest.mark.asyncio
    async def test_process_message_json_error(self) -> None:
        """Test handling malformed JSON message."""
        settings = RedisSettings()
        subscriber = EventSubscriber(settings)

        handler = AsyncMock()
        subscriber.subscribe("trader_positions", handler)

        # Simulate malformed message
        message = {
            "channel": b"events:trader_positions",
            "data": b"not valid json",
        }

        # Should not raise, just log and skip
        await subscriber._process_message(message)

        handler.assert_not_called()
