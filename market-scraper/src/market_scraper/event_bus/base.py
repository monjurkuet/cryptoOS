# src/market_scraper/event_bus/base.py

"""EventBus abstract base class for the Market Scraper Framework."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from enum import Enum

from market_scraper.core.events import StandardEvent


class EventPriority(Enum):
    """Event processing priority levels."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


EventHandler = Callable[[StandardEvent], Awaitable[None]]


class EventBus(ABC):
    """Abstract base class for event bus implementations.

    Provides pub/sub messaging between system components.
    Implementations: Redis Pub/Sub, in-memory, RabbitMQ, etc.
    """

    def __init__(self, max_queue_size: int = 10000) -> None:
        """Initialize the event bus.

        Args:
            max_queue_size: Maximum number of events to queue
        """
        self._handlers: dict[str, list[tuple[EventPriority, EventHandler]]] = {}
        self._max_queue_size = max_queue_size
        self._metrics: dict[str, int] = {
            "published": 0,
            "delivered": 0,
            "dropped": 0,
            "errors": 0,
        }

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to event bus backend."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to event bus backend."""
        pass

    @abstractmethod
    async def publish(
        self,
        event: StandardEvent,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> bool:
        """Publish an event to the bus.

        Args:
            event: Event to publish
            priority: Processing priority

        Returns:
            True if published successfully
        """
        pass

    @abstractmethod
    async def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> None:
        """Subscribe to events of a specific type.

        Args:
            event_type: Event type to subscribe to (or "*" for all)
            handler: Async callback function
            priority: Handler execution priority
        """
        pass

    @abstractmethod
    async def unsubscribe(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """Unsubscribe a handler from an event type."""
        pass

    @abstractmethod
    async def publish_bulk(
        self,
        events: list[StandardEvent],
        priority: EventPriority = EventPriority.NORMAL,
    ) -> int:
        """Publish multiple events efficiently.

        Args:
            events: List of events to publish
            priority: Processing priority for all events

        Returns:
            Number of events successfully published
        """
        pass

    def get_metrics(self) -> dict[str, int]:
        """Get event bus metrics.

        Returns:
            Copy of the metrics dictionary
        """
        return self._metrics.copy()

    async def __aenter__(self) -> "EventBus":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit."""
        await self.disconnect()
