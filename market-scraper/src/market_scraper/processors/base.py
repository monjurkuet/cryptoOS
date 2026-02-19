# src/market_scraper/processors/base.py

"""Processor abstract base class for the Market Scraper Framework."""

from abc import ABC, abstractmethod

from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus


class Processor(ABC):
    """Abstract base class for event processors.

    Processors transform, validate, enrich, or aggregate events as they flow
    through the system. Each processor can subscribe to specific event types
    and publish processed events back to the event bus.

    Attributes:
        _event_bus: Reference to the event bus for publishing processed events
        _running: Whether the processor is currently running
    """

    def __init__(self, event_bus: EventBus) -> None:
        """Initialize the processor with an event bus reference.

        Args:
            event_bus: Event bus instance for publishing processed events
        """
        self._event_bus = event_bus
        self._running = False

    @abstractmethod
    async def process(self, event: StandardEvent) -> StandardEvent | None:
        """Process an incoming event.

        This is the main processing logic that transforms, validates,
        enriches, or aggregates the event. Implementations should handle
        their specific event types and return the processed event or None
        if the event should be filtered out.

        Args:
            event: The incoming event to process

        Returns:
            The processed event, or None if the event was filtered/invalid
        """
        pass

    async def start(self) -> None:
        """Start the processor.

        Optional lifecycle method for initialization. Subclasses can override
        this to perform setup like connecting to external services,
        initializing caches, or subscribing to event types.

        This method is called before the processor begins processing events.
        """
        self._running = True

    async def stop(self) -> None:
        """Stop the processor.

        Optional lifecycle method for cleanup. Subclasses can override
        this to perform teardown like closing connections, flushing buffers,
        or unsubscribing from event types.

        This method is called when the processor is shutting down.
        """
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if the processor is currently running.

        Returns:
            True if the processor has been started, False otherwise
        """
        return self._running
