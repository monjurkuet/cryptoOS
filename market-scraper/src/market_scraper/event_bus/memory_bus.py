# src/market_scraper/event_bus/memory_bus.py

"""In-memory event bus implementation for testing."""

import asyncio
from contextlib import suppress

from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus, EventHandler, EventPriority


class MemoryEventBus(EventBus):
    """In-memory event bus implementation.

    Suitable for testing and development.
    Events are stored in memory and processed asynchronously.
    """

    def __init__(self, max_queue_size: int = 10000) -> None:
        """Initialize memory event bus.

        Args:
            max_queue_size: Maximum number of events to queue
        """
        super().__init__(max_queue_size)
        self._queue: asyncio.Queue[StandardEvent] = asyncio.Queue(maxsize=max_queue_size)
        self._running = False
        self._processor_task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        """Start the event processor."""
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())

    async def disconnect(self) -> None:
        """Stop the event processor."""
        self._running = False

        # Put a sentinel value to unblock the queue
        with suppress(asyncio.QueueFull):
            self._queue.put_nowait(None)  # type: ignore[arg-type]

        if self._processor_task:
            self._processor_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._processor_task

    async def publish(
        self,
        event: StandardEvent,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> bool:
        """Publish an event to the in-memory queue."""
        try:
            self._queue.put_nowait(event)
            self._metrics["published"] += 1
            return True
        except asyncio.QueueFull:
            self._metrics["dropped"] += 1
            return False

    async def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> None:
        """Subscribe to events of a specific type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        self._handlers[event_type].append((priority, handler))
        # Sort by priority
        self._handlers[event_type].sort(key=lambda x: x[0].value)

    async def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """Unsubscribe a handler from an event type."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                (p, h) for p, h in self._handlers[event_type] if h != handler
            ]

            if not self._handlers[event_type]:
                del self._handlers[event_type]

    async def publish_bulk(
        self,
        events: list[StandardEvent],
        priority: EventPriority = EventPriority.NORMAL,
    ) -> int:
        """Publish multiple events to the in-memory queue."""
        published = 0
        for event in events:
            if await self.publish(event, priority):
                published += 1
        return published

    async def _process_events(self) -> None:
        """Background task to process events from the queue."""
        while self._running:
            try:
                event = await self._queue.get()

                if event is None:  # Sentinel value for shutdown
                    break

                # Get handlers for this event type and wildcard
                event_type_str = str(event.event_type)
                handlers: list[tuple[EventPriority, EventHandler]] = []

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

                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception:
                self._metrics["errors"] += 1
