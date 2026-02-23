# tests/integration/test_event_bus.py

"""Integration tests for EventBus implementations."""

import asyncio

import pytest
import pytest_asyncio

from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus, EventPriority
from market_scraper.event_bus.memory_bus import MemoryEventBus


class TestMemoryEventBus:
    """Tests for in-memory event bus implementation."""

    @pytest_asyncio.fixture
    async def event_bus(self):
        """Create and cleanup event bus fixture."""
        bus = MemoryEventBus()
        await bus.connect()
        yield bus
        await bus.disconnect()

    @pytest.mark.asyncio
    async def test_publish_and_subscribe(self, event_bus: EventBus) -> None:
        """Test basic publish/subscribe functionality."""
        received_events = []

        async def handler(event: StandardEvent) -> None:
            received_events.append(event)

        await event_bus.subscribe("test_event", handler)

        event = StandardEvent.create(
            event_type="test_event",
            source="test",
            payload={"data": "test"},
        )

        await event_bus.publish(event)
        await asyncio.sleep(0.1)  # Allow async processing

        assert len(received_events) == 1
        assert received_events[0].event_id == event.event_id

    @pytest.mark.asyncio
    async def test_unsubscribe(self, event_bus: EventBus) -> None:
        """Test unsubscribing from events."""
        received_events = []

        async def handler(event: StandardEvent) -> None:
            received_events.append(event)

        await event_bus.subscribe("test_event", handler)
        await event_bus.unsubscribe("test_event", handler)

        event = StandardEvent.create(
            event_type="test_event",
            source="test",
            payload={"data": "test"},
        )

        await event_bus.publish(event)
        await asyncio.sleep(0.1)

        assert len(received_events) == 0

    @pytest.mark.asyncio
    async def test_wildcard_subscription(self, event_bus: EventBus) -> None:
        """Test wildcard event subscription."""
        received_events = []

        async def handler(event: StandardEvent) -> None:
            received_events.append(event)

        await event_bus.subscribe("*", handler)

        for i in range(3):
            event = StandardEvent.create(
                event_type=f"event_{i}",
                source="test",
                payload={"data": i},
            )
            await event_bus.publish(event)

        await asyncio.sleep(0.1)

        assert len(received_events) == 3

    @pytest.mark.asyncio
    async def test_bulk_publish(self, event_bus: EventBus) -> None:
        """Test bulk event publishing."""
        received_count = 0

        async def handler(event: StandardEvent) -> None:
            nonlocal received_count
            received_count += 1

        await event_bus.subscribe("bulk_event", handler)

        events = [
            StandardEvent.create(
                event_type="bulk_event",
                source="test",
                payload={"data": i},
            )
            for i in range(100)
        ]

        published = await event_bus.publish_bulk(events)
        await asyncio.sleep(0.2)

        assert published == 100
        assert received_count == 100

    @pytest.mark.asyncio
    async def test_multiple_handlers(self, event_bus: EventBus) -> None:
        """Test multiple handlers for same event type."""
        handler1_events = []
        handler2_events = []

        async def handler1(event: StandardEvent) -> None:
            handler1_events.append(event)

        async def handler2(event: StandardEvent) -> None:
            handler2_events.append(event)

        await event_bus.subscribe("multi_event", handler1)
        await event_bus.subscribe("multi_event", handler2)

        event = StandardEvent.create(
            event_type="multi_event",
            source="test",
            payload={"data": "test"},
        )

        await event_bus.publish(event)
        await asyncio.sleep(0.1)

        assert len(handler1_events) == 1
        assert len(handler2_events) == 1
        assert handler1_events[0].event_id == event.event_id
        assert handler2_events[0].event_id == event.event_id

    @pytest.mark.asyncio
    async def test_metrics(self, event_bus: EventBus) -> None:
        """Test metrics tracking."""

        async def handler(event: StandardEvent) -> None:
            pass

        await event_bus.subscribe("metric_event", handler)

        event = StandardEvent.create(
            event_type="metric_event",
            source="test",
            payload={"data": "test"},
        )

        await event_bus.publish(event)
        await asyncio.sleep(0.1)

        metrics = event_bus.get_metrics()
        assert metrics["published"] == 1
        assert metrics["delivered"] == 1

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager."""
        received_events = []

        async def handler(event: StandardEvent) -> None:
            received_events.append(event)

        async with MemoryEventBus() as bus:
            await bus.subscribe("ctx_event", handler)

            event = StandardEvent.create(
                event_type="ctx_event",
                source="test",
                payload={"data": "test"},
            )

            await bus.publish(event)
            await asyncio.sleep(0.1)

            assert len(received_events) == 1

        # After context exit, no more events should be processed
        received_events.clear()

        event2 = StandardEvent.create(
            event_type="ctx_event",
            source="test",
            payload={"data": "test2"},
        )

        # Should not process since disconnected
        await asyncio.sleep(0.1)
        assert len(received_events) == 0

    @pytest.mark.asyncio
    async def test_handler_error_handling(self, event_bus: EventBus) -> None:
        """Test error handling in handlers."""
        error_count = 0

        async def error_handler(event: StandardEvent) -> None:
            nonlocal error_count
            error_count += 1
            raise ValueError("Test error")

        async def normal_handler(event: StandardEvent) -> None:
            pass

        await event_bus.subscribe("error_event", error_handler)
        await event_bus.subscribe("error_event", normal_handler)

        event = StandardEvent.create(
            event_type="error_event",
            source="test",
            payload={"data": "test"},
        )

        await event_bus.publish(event)
        await asyncio.sleep(0.1)

        # Error should be counted but not crash the bus
        metrics = event_bus.get_metrics()
        assert metrics["errors"] >= 1


class TestEventPriority:
    """Tests for event priority handling."""

    @pytest.mark.asyncio
    async def test_priority_ordering(self) -> None:
        """Test that handlers are executed in priority order."""
        execution_order = []

        async def low_priority_handler(event: StandardEvent) -> None:
            execution_order.append("low")

        async def high_priority_handler(event: StandardEvent) -> None:
            execution_order.append("high")

        async def normal_priority_handler(event: StandardEvent) -> None:
            execution_order.append("normal")

        bus = MemoryEventBus()
        await bus.connect()

        # Subscribe in reverse priority order
        await bus.subscribe("priority_event", low_priority_handler, EventPriority.LOW)
        await bus.subscribe("priority_event", normal_priority_handler, EventPriority.NORMAL)
        await bus.subscribe("priority_event", high_priority_handler, EventPriority.HIGH)

        event = StandardEvent.create(
            event_type="priority_event",
            source="test",
            payload={"data": "test"},
        )

        await bus.publish(event)
        await asyncio.sleep(0.1)
        await bus.disconnect()

        # High priority should execute first (0 = highest)
        assert execution_order == ["high", "normal", "low"]
