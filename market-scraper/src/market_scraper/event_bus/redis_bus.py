# src/market_scraper/event_bus/redis_bus.py

"""Redis Pub/Sub event bus implementation."""

import asyncio
import json
from contextlib import suppress

import redis.asyncio as redis

from market_scraper.core.events import StandardEvent
from market_scraper.core.exceptions import EventBusError
from market_scraper.event_bus.base import EventBus, EventHandler, EventPriority


class RedisEventBus(EventBus):
    """Redis Pub/Sub event bus implementation.

    Uses Redis Pub/Sub for real-time messaging.
    Note: Redis Pub/Sub is at-most-once delivery.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        max_queue_size: int = 10000,
    ) -> None:
        """Initialize Redis event bus.

        Args:
            redis_url: Redis connection URL
            max_queue_size: Maximum queue size for events
        """
        super().__init__(max_queue_size)
        self._redis_url = redis_url
        self._redis: redis.Redis | None = None
        self._pubsub: redis.client.PubSub | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._running = False

    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self._redis = redis.from_url(self._redis_url, decode_responses=True)
            self._pubsub = self._redis.pubsub()
            self._running = True
            self._listener_task = asyncio.create_task(self._listener())
        except Exception as e:
            raise EventBusError(f"Failed to connect to Redis: {e}") from e

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        self._running = False

        if self._listener_task:
            self._listener_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._listener_task

        if self._pubsub:
            try:
                await self._pubsub.aclose()
            except Exception:
                pass  # Ignore errors during cleanup

        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass  # Ignore errors during cleanup

    async def publish(
        self,
        event: StandardEvent,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> bool:
        """Publish event to Redis channel."""
        if not self._redis:
            raise EventBusError("Not connected to Redis")

        try:
            channel = f"events:{event.event_type}"
            message = event.model_dump_json()
            await self._redis.publish(channel, message)
            self._metrics["published"] += 1
            return True
        except Exception as e:
            self._metrics["errors"] += 1
            raise EventBusError(f"Failed to publish event: {e}") from e

    async def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> None:
        """Subscribe to Redis channel.

        For wildcard subscriptions (event_type="*"), uses pattern subscribe
        to match all event types.
        """
        if not self._pubsub:
            raise EventBusError("Not connected to Redis")

        if event_type not in self._handlers:
            self._handlers[event_type] = []
            if event_type == "*":
                # Use pattern subscribe for wildcard
                await self._pubsub.psubscribe("events:*")
            else:
                channel = f"events:{event_type}"
                await self._pubsub.subscribe(channel)

        self._handlers[event_type].append((priority, handler))
        # Sort by priority
        self._handlers[event_type].sort(key=lambda x: x[0].value)

    async def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """Unsubscribe from Redis channel."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                (p, h) for p, h in self._handlers[event_type] if h != handler
            ]

            if not self._handlers[event_type] and self._pubsub:
                if event_type == "*":
                    await self._pubsub.punsubscribe("events:*")
                else:
                    channel = f"events:{event_type}"
                    await self._pubsub.unsubscribe(channel)
                del self._handlers[event_type]

    async def publish_bulk(
        self,
        events: list[StandardEvent],
        priority: EventPriority = EventPriority.NORMAL,
    ) -> int:
        """Publish multiple events using pipeline.

        Note: Redis PUBLISH returns the number of subscribers that received
        the message, not a boolean. We count events as published even if
        there are no subscribers (the publish was still successful).
        """
        if not self._redis:
            raise EventBusError("Not connected to Redis")

        pipe = self._redis.pipeline()

        for event in events:
            channel = f"events:{event.event_type}"
            message = event.model_dump_json()
            pipe.publish(channel, message)

        try:
            await pipe.execute()
            # Count all events as published since the operation succeeded
            published = len(events)
            self._metrics["published"] += published
            return published
        except Exception as e:
            self._metrics["errors"] += 1
            raise EventBusError(f"Failed to publish bulk events: {e}") from e

    async def _listener(self) -> None:
        """Background listener for incoming messages.

        Handles both regular messages (from subscribe) and pattern messages
        (from psubscribe for wildcard subscriptions).
        """
        if not self._pubsub:
            return

        while self._running:
            try:
                # Use get_message with timeout to allow checking _running periodically
                message = await asyncio.wait_for(
                    self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=2.0
                )

                if message is None:
                    continue

                # Handle both regular messages and pattern messages
                msg_type = message.get("type", "")
                if msg_type not in ("message", "pmessage"):
                    continue

                try:
                    # For pmessage, data is in message["data"]
                    # For message, data is in message["data"]
                    data = json.loads(message["data"])
                    event = StandardEvent.model_validate(data)

                    # Get handlers for this event type and wildcard
                    handlers: list[tuple[EventPriority, EventHandler]] = []
                    event_type_str = str(event.event_type)
                    if event_type_str in self._handlers:
                        handlers.extend(self._handlers[event_type_str])
                    if "*" in self._handlers:
                        handlers.extend(self._handlers["*"])

                    # Execute handlers
                    for _priority, handler in handlers:
                        try:
                            await handler(event)
                            self._metrics["delivered"] += 1
                        except Exception:
                            self._metrics["errors"] += 1
                            # Log error but continue with other handlers

                except json.JSONDecodeError:
                    self._metrics["errors"] += 1
                except Exception:
                    self._metrics["errors"] += 1

            except asyncio.TimeoutError:
                # No message received, check _running and continue
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                self._metrics["errors"] += 1
                await asyncio.sleep(0.1)  # Brief pause on error
