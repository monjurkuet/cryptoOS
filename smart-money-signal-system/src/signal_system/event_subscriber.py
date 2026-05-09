"""Event Subscriber for market-scraper events."""

import asyncio
from datetime import datetime, timezone
import inspect
import json
from typing import Any, Callable

import redis.asyncio as redis
import structlog

from signal_system.config import RedisSettings

logger = structlog.get_logger(__name__)


class EventSubscriber:
    """Subscribes to market-scraper events via Redis.

    Channel format: "events:{event_type}"
    Example: "events:trader_positions"
    """

    def __init__(self, settings: RedisSettings) -> None:
        """Initialize the subscriber.

        Args:
            settings: Redis configuration settings
        """
        self.settings = settings
        self._redis: redis.Redis | None = None
        self._pubsub: redis.client.PubSub | None = None
        self._running = False
        self._handlers: dict[str, list[Callable]] = {}
        self._message_count = 0
        self._channel_counts: dict[str, int] = {}
        self._last_message_at: str | None = None
        self._last_payload_timestamp: str | None = None
        self._last_payload_lag_ms: float | None = None
        self._connect_attempts = 0
        self._last_error: str | None = None

    async def connect(self) -> None:
        """Connect to Redis."""
        self._connect_attempts += 1
        self._redis = redis.from_url(self.settings.url)
        self._pubsub = self._redis.pubsub()
        logger.info("redis_connected", url=self.settings.url)

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        self._running = False
        if self._pubsub:
            await self._pubsub.unsubscribe()
            if hasattr(self._pubsub, "aclose"):
                await self._pubsub.aclose()
            else:
                await self._pubsub.close()
        if self._redis:
            if hasattr(self._redis, "aclose"):
                await self._redis.aclose()
            else:
                await self._redis.close()
        logger.info("redis_disconnected")

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to an event type.

        Args:
            event_type: Event type (e.g., "trader_positions")
            handler: Async function to handle the event
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug("handler_registered", event_type=event_type, handler=handler.__name__)

    async def start(self) -> None:
        """Start listening for events."""
        if not self._pubsub:
            raise RuntimeError("Not connected to Redis")

        self._running = True

        # Subscribe to channels: "events:{event_type}"
        # Uses pattern subscribe to match "events:trader_positions" etc.
        channels = [
            f"{self.settings.channel_prefix}:{event_type}" for event_type in self._handlers.keys()
        ]
        await self._pubsub.psubscribe(*channels)
        logger.info("channels_subscribed", channels=channels)

        # Start listening
        await self._listen_loop()

    async def _listen_loop(self) -> None:
        """Listen for Redis messages."""
        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )

                if message and message["type"] == "pmessage":
                    await self._process_message(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._last_error = str(e)
                logger.error("listen_error", error=str(e), exc_info=True)
                await asyncio.sleep(1.0)

    async def _process_message(self, message: dict) -> None:
        """Process incoming message.

        Args:
            message: Raw Redis pub/sub message
        """
        try:
            channel = message["channel"]
            data = json.loads(message["data"])

            # Extract event type from channel
            if isinstance(channel, bytes):
                channel = channel.decode()
            event_type = channel.split(":")[-1]

            self._message_count += 1
            self._channel_counts[event_type] = self._channel_counts.get(event_type, 0) + 1
            self._last_message_at = datetime.now(timezone.utc).isoformat()
            self._last_error = None
            payload_timestamp = data.get("timestamp") if isinstance(data, dict) else None
            if isinstance(payload_timestamp, str):
                try:
                    parsed_ts = datetime.fromisoformat(payload_timestamp.replace("Z", "+00:00"))
                    self._last_payload_timestamp = parsed_ts.isoformat()
                    lag = datetime.now(timezone.utc) - parsed_ts.astimezone(timezone.utc)
                    self._last_payload_lag_ms = round(lag.total_seconds() * 1000, 2)
                except ValueError:
                    self._last_payload_timestamp = payload_timestamp
                    self._last_payload_lag_ms = None

            # Call handlers
            handlers = self._handlers.get(event_type, [])
            for handler in handlers:
                try:
                    if inspect.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    self._last_error = str(e)
                    logger.error(
                        "handler_error",
                        event_type=event_type,
                        handler=handler.__name__,
                        error=str(e),
                    )

        except json.JSONDecodeError as e:
            self._last_error = str(e)
            logger.warning("invalid_json", error=str(e))
        except Exception as e:
            self._last_error = str(e)
            logger.error("process_error", error=str(e), exc_info=True)

    def get_stats(self) -> dict[str, Any]:
        """Get subscriber statistics.

        Returns:
            Dict with subscriber stats
        """
        return {
            "running": self._running,
            "message_count": self._message_count,
            "subscribed_events": list(self._handlers.keys()),
            "channel_counts": dict(self._channel_counts),
            "last_message_at": self._last_message_at,
            "last_payload_timestamp": self._last_payload_timestamp,
            "last_payload_lag_ms": self._last_payload_lag_ms,
            "connect_attempts": self._connect_attempts,
            "last_error": self._last_error,
        }
