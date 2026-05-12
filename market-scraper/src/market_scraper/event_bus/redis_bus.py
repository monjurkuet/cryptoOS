"""Redis Pub/Sub event bus implementation."""

import asyncio
import json
from contextlib import suppress

import redis.asyncio as redis
import structlog

from market_scraper.core.events import StandardEvent
from market_scraper.core.exceptions import EventBusError
from market_scraper.event_bus.base import EventBus, EventHandler, EventPriority

logger = structlog.get_logger(__name__)


class RedisEventBus(EventBus):
    """Redis Pub/Sub event bus implementation.

    Uses Redis Pub/Sub for real-time messaging.
    Note: Redis Pub/Sub is at-most-once delivery.

    Supports local (in-process) subscribers that bypass Redis entirely,
    avoiding the publish/subscribe round-trip for handlers in the same
    process. This is critical for high-volume channels like
    ``trader_positions`` (~190 events per flush) where the Redis
    round-trip adds ~1–2 ms of event-loop blocking per event.
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
        self._subscribed = asyncio.Event()

        # Local (in-process) subscribers — dispatched directly, bypassing Redis.
        # Key is event_type (or "*"), value is list of (priority, handler) tuples.
        self._local_subscribers: dict[str, list[tuple[EventPriority, EventHandler]]] = {}

        # Toggle for direct dispatch. When True (default), publish() and
        # publish_bulk() dispatch to local subscribers first, then publish
        # to Redis for any external consumers. When False, all events go
        # through Redis only (behaviour identical to pre-2C).
        self._direct_dispatch: bool = True

        # Semaphore to limit concurrent handler dispatches and prevent
        # event loop starvation from hundreds of simultaneous DB writes.
        self._dispatch_semaphore = asyncio.Semaphore(20)

    # -- Local subscriber management ----------------------------------------

    async def subscribe_local(
        self,
        event_type: str,
        handler: EventHandler,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> None:
        """Subscribe a handler for direct in-process dispatch.

        Local subscribers are invoked directly by publish() / publish_bulk()
        *before* the event is published to Redis. This avoids the Redis
        round-trip for handlers that live in the same process.

        Local subscribers are completely separate from Redis subscribers.
        They do NOT cause a Redis SUBSCRIBE command and they are NOT
        dispatched from the _listener loop (which would be redundant).

        Args:
            event_type: Event type to subscribe to (or "*" for all)
            handler: Async callback function
            priority: Handler execution priority
        """
        if event_type not in self._local_subscribers:
            self._local_subscribers[event_type] = []
        self._local_subscribers[event_type].append((priority, handler))
        # Sort by priority (lower value = higher priority)
        self._local_subscribers[event_type].sort(key=lambda x: x[0].value)
        logger.debug(
            "local_subscriber_registered",
            event_type=event_type,
            handler=handler.__qualname__,
        )

    async def unsubscribe_local(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """Unsubscribe a local handler from an event type.

        Args:
            event_type: Event type to unsubscribe from
            handler: Handler to remove
        """
        if event_type in self._local_subscribers:
            self._local_subscribers[event_type] = [
                (p, h)
                for p, h in self._local_subscribers[event_type]
                if h != handler
            ]
            if not self._local_subscribers[event_type]:
                del self._local_subscribers[event_type]

    def set_direct_dispatch(self, enabled: bool) -> None:
        """Enable or disable direct dispatch to local subscribers.

        When disabled, all events go through Redis even if local
        subscribers are registered. This is useful for debugging or
        for temporarily reverting to pure-Redis behaviour.

        Args:
            enabled: True to enable direct dispatch (default), False to disable
        """
        self._direct_dispatch = enabled
        logger.info("direct_dispatch_toggled", enabled=enabled)

    # -- Direct dispatch helpers -------------------------------------------

    def _get_local_handlers(
        self, event_type: str
    ) -> list[tuple[EventPriority, EventHandler]]:
        """Collect local handlers for a given event type.

        Merges concrete handlers (exact event_type match) and wildcard
        handlers ("*"), sorted by priority.

        Args:
            event_type: The event type string

        Returns:
            Merged list of (priority, handler) tuples
        """
        handlers: list[tuple[EventPriority, EventHandler]] = []
        if event_type in self._local_subscribers:
            handlers.extend(self._local_subscribers[event_type])
        if "*" in self._local_subscribers:
            handlers.extend(self._local_subscribers["*"])
        # Re-sort by priority after merging
        handlers.sort(key=lambda x: x[0].value)
        return handlers

    def _has_local_subscribers(self, event_type: str) -> bool:
        """Check if any local subscribers exist for an event type.

        Args:
            event_type: The event type string

        Returns:
            True if at least one local subscriber (concrete or wildcard) exists
        """
        return (
            event_type in self._local_subscribers or "*" in self._local_subscribers
        )

    async def _dispatch_local(
        self, event: StandardEvent, event_type: str
    ) -> None:
        """Dispatch an event to all matching local subscribers.

        Exceptions in individual handlers are caught and logged so that
        one failing handler cannot crash the entire flush.

        Args:
            event: The event to dispatch
            event_type: The event type string (from event.event_type)
        """
        handlers = self._get_local_handlers(event_type)
        if not handlers:
            return

        for _priority, handler in handlers:
            try:
                await handler(event)
                self._metrics["delivered"] += 1
            except Exception as e:
                self._metrics["errors"] += 1
                logger.error(
                    "local_dispatch_handler_error",
                    event_type=event.event_type,
                    handler=handler.__qualname__,
                    error=str(e),
                    exc_info=True,
                )

    async def _dispatch_local_bulk(
        self, events: list[StandardEvent]
    ) -> None:
        """Dispatch a batch of events to local subscribers.

        Uses a bounded semaphore to limit concurrent handler executions to 20.
        Tasks are created for all (handler, event) pairs but the semaphore
        ensures only 20 run concurrently, preventing event loop starvation.

        Dispatch is fire-and-forget: this method creates a single background
        task that processes all dispatches, then returns immediately so the
        caller (publish_bulk) is not blocked.

        Args:
            events: List of events to dispatch
        """
        if not self._local_subscribers:
            return

        async def _safe_dispatch(handler: EventHandler, event: StandardEvent) -> None:
            async with self._dispatch_semaphore:
                try:
                    await handler(event)
                    self._metrics["delivered"] += 1
                except Exception as e:
                    self._metrics["errors"] += 1
                    logger.error(
                        "local_dispatch_handler_error",
                        event_type=event.event_type,
                        handler=handler.__qualname__,
                        error=str(e),
                        exc_info=True,
                    )

        async def _run_all_dispatches() -> None:
            tasks = []
            for event in events:
                event_type_str = str(event.event_type)
                handlers = self._get_local_handlers(event_type_str)
                for _priority, handler in handlers:
                    tasks.append(asyncio.create_task(
                        _safe_dispatch(handler, event)
                    ))
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        # Fire-and-forget: run all dispatches in a single background task
        asyncio.create_task(_run_all_dispatches())
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
        self._subscribed.clear()

        if self._listener_task:
            self._listener_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._listener_task

        if self._pubsub:
            with suppress(Exception):
                await self._pubsub.aclose()

        if self._redis:
            with suppress(Exception):
                await self._redis.aclose()

        # Clear local subscribers on disconnect
        self._local_subscribers.clear()

    # -- Publishing --------------------------------------------------------

    async def publish(
        self,
        event: StandardEvent,
        priority: EventPriority = EventPriority.NORMAL,
        local_only: bool = False,
    ) -> bool:
        """Publish event to local subscribers and/or Redis channel.

        If direct dispatch is enabled and local subscribers exist for
        this event type, they are invoked first (awaited directly).

        If local_only=True, the event is dispatched to local subscribers
        only and NOT published to Redis. This is ideal for events that
        are consumed entirely in-process (e.g. trader_positions).

        If local_only=False (default), the event is also published to
        Redis for any external consumers (e.g. API server, WebSocket).
        """
        if not self._redis:
            raise EventBusError("Not connected to Redis")

        event_type_str = str(event.event_type)

        # 1. Direct dispatch to local subscribers (bypasses Redis)
        if self._direct_dispatch and self._has_local_subscribers(event_type_str):
            await self._dispatch_local(event, event_type_str)

        # 2. Publish to Redis for external consumers (unless local_only)
        if local_only:
            return True

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

        # Signal the listener that at least one subscription now exists,
        # so it can safely start polling get_message().
        self._subscribed.set()

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
        local_only: bool = False,
    ) -> int:
        """Publish multiple events using pipeline.

        If direct dispatch is enabled and local subscribers exist, all
        events are dispatched to local subscribers first (awaited in
        sequence), then the batch is published to Redis via pipeline.

        This is the hot path for trader_positions (~190 events/flush).
        Direct dispatch eliminates ~190 Redis round-trips per flush,
        saving ~190–380 ms of event-loop blocking.

        Note: Redis PUBLISH returns the number of subscribers that received
        the message, not a boolean. We count events as published even if
        there are no subscribers (the publish was still successful).
        """
        if not self._redis:
            raise EventBusError("Not connected to Redis")

        # 1. Direct dispatch to local subscribers (bypasses Redis)
        if self._direct_dispatch and self._local_subscribers:
            await self._dispatch_local_bulk(events)

        # 2. Pipeline publish to Redis for external consumers (unless local_only)
        if local_only:
            return len(events)

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

    # -- Internal reconnection ---------------------------------------------

    async def _re_subscribe(self) -> None:
        """Re-establish pubsub connection and re-subscribe all handlers.

        Called when the pubsub connection is lost (e.g. Redis timeout during
        event loop lag). Without this, the listener spins forever on a dead
        pubsub and no events get delivered.
        """
        if not self._redis:
            logger.error("redis_listener_resubscribe_no_redis")
            return

        try:
            if self._pubsub:
                try:
                    await self._pubsub.unsubscribe()
                    await self._pubsub.punsubscribe()
                except Exception:
                    pass
                try:
                    await self._pubsub.aclose()
                except Exception:
                    pass

            # Create fresh pubsub
            self._pubsub = self._redis.pubsub()

            # Re-subscribe all registered handlers
            handler_keys = list(self._handlers.keys())
            for event_type in handler_keys:
                if event_type == "*":
                    await self._pubsub.psubscribe("events:*")
                else:
                    channel = f"events:{event_type}"
                    await self._pubsub.subscribe(channel)

            logger.info(
                "redis_listener_resubscribed",
                channels=handler_keys,
                handler_count=len(handler_keys),
            )

            # Re-arm the subscribed event so the listener loop can
            # resume polling after a reconnection.
            if handler_keys:
                self._subscribed.set()
        except Exception as e:
            logger.error("redis_listener_resubscribe_error", error=str(e), exc_info=True)
            raise

    # -- Handler safety ----------------------------------------------------

    async def _safe_handler_call(self, handler: EventHandler, event: StandardEvent) -> None:
        """Safely call an event handler, updating metrics on success/failure."""
        try:
            await handler(event)
            self._metrics["delivered"] += 1
        except Exception as e:
            self._metrics["errors"] += 1
            logger.error(
                "redis_event_handler_error",
                event_type=event.event_type,
                error=str(e),
                exc_info=True,
            )

    def _should_resubscribe(self, err_str: str) -> bool:
        """Check if an error indicates the pubsub connection was lost."""
        err_lower = err_str.lower()
        return (
            "pubsub connection not set" in err_lower
            or "connection lost" in err_lower
            or "connection closed" in err_lower
            or "broken pipe" in err_lower
            or "connectionreset" in err_lower
            or "eof" in err_lower
        )

    # -- Listener loop -----------------------------------------------------

    async def _listener(self) -> None:
        """Background listener for incoming messages.

        Handles both regular messages (from subscribe) and pattern messages
        (from psubscribe for wildcard subscriptions).

        Dedup logic: When both concrete (subscribe) and wildcard (psubscribe)
        are registered for the same event type, Redis emits both "message" and
        "pmessage". The "message" dispatch covers concrete + wildcard handlers.
        The "pmessage" only dispatches wildcard handlers that haven't already
        been called — this prevents the bug where wildcard-only handlers
        (like the storage handler) were silently dropped for event types that
        also had concrete subscribers.
        """
        if not self._pubsub:
            return

        # Wait until at least one subscription is registered before polling.
        # Without this, get_message() raises RuntimeError because the pubsub
        # connection is lazily opened on the first subscribe() call.
        while self._running and not self._subscribed.is_set():
            try:
                await asyncio.wait_for(self._subscribed.wait(), timeout=1.0)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                return

        while self._running:
            try:
                # Use get_message with timeout to allow checking _running periodically
                message = await asyncio.wait_for(
                    self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=2.0,
                )

                if message is None:
                    continue

                # Handle both regular messages and pattern messages
                msg_type = message.get("type", "")
                if msg_type not in ("message", "pmessage"):
                    continue

                try:
                    data = json.loads(message["data"])
                    event = StandardEvent.model_validate(data)
                    event_type_str = str(event.event_type)

                    # Collect handlers to dispatch for this event.
                    # For "message" type: dispatch concrete + wildcard handlers.
                    # For "pmessage" type: only dispatch wildcard handlers that
                    # weren't already called by the "message" dispatch.
                    if msg_type == "pmessage":
                        channel = str(message.get("channel", ""))
                        if channel.startswith("events:"):
                            channel_event_type = channel.split("events:", 1)[1]
                            if channel_event_type in self._handlers:
                                # Concrete subscribers already dispatched via "message".
                                # Only run wildcard handlers here to avoid dropping them.
                                if "*" in self._handlers:
                                    for _priority, handler in self._handlers["*"]:
                                        try:
                                            asyncio.create_task(
                                                self._safe_handler_call(handler, event)
                                            )
                                        except Exception as e:
                                            self._metrics["errors"] += 1
                                            logger.error(
                                                "redis_event_handler_dispatch_error",
                                                event_type=event.event_type,
                                                error=str(e),
                                            )
                                    await asyncio.sleep(0)
                                continue  # Skip normal dispatch (already handled above)

                    # Normal dispatch: collect concrete + wildcard handlers
                    handlers: list[tuple[EventPriority, EventHandler]] = []
                    if event_type_str in self._handlers:
                        handlers.extend(self._handlers[event_type_str])
                    if "*" in self._handlers:
                        handlers.extend(self._handlers["*"])

                    # Execute handlers non-blocking to prevent slow handlers
                    # (e.g. MongoDB storage) from blocking the listener loop
                    for _priority, handler in handlers:
                        try:
                            asyncio.create_task(
                                self._safe_handler_call(handler, event)
                            )
                        except Exception as e:
                            self._metrics["errors"] += 1
                            logger.error(
                                "redis_event_handler_dispatch_error",
                                event_type=event.event_type,
                                error=str(e),
                            )

                    # Yield to event loop after dispatching all handlers
                    # to prevent starving HTTP request handling during
                    # high-throughput bursts
                    await asyncio.sleep(0)

                except json.JSONDecodeError as e:
                    self._metrics["errors"] += 1
                    logger.warning("redis_listener_json_error", error=str(e))
                except Exception as e:
                    self._metrics["errors"] += 1
                    logger.error("redis_listener_event_error", error=str(e), exc_info=True)

            except TimeoutError:
                # No message received, check _running and continue
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._metrics["errors"] += 1
                logger.error("redis_listener_error", error=str(e), exc_info=True)
                # If pubsub connection was lost, attempt to re-subscribe
                # instead of spinning on a broken connection forever.
                if self._should_resubscribe(str(e)):
                    try:
                        logger.info("redis_listener_resubscribe", error=str(e))
                        await self._re_subscribe()
                        # Sleep after successful re-subscribe to let
                        # the new pubsub connection settle before reading
                        await asyncio.sleep(2.0)
                    except Exception as resub_err:
                        logger.error("redis_listener_resubscribe_failed", error=str(resub_err))
                        await asyncio.sleep(5.0)  # Longer pause after failed re-subscribe
                else:
                    await asyncio.sleep(0.1)  # Brief pause on other errors
