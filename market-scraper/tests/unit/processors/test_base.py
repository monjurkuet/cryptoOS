# tests/unit/processors/test_base.py

"""Test suite for Processor base class."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from market_scraper.core.events import EventType, MarketDataPayload, StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.processors.base import Processor


class MockProcessor(Processor):
    """Mock implementation of Processor for testing."""

    def __init__(self, event_bus: EventBus) -> None:
        super().__init__(event_bus)
        self.processed_events: list[StandardEvent] = []

    async def process(self, event: StandardEvent) -> StandardEvent | None:
        """Mock process method."""
        self.processed_events.append(event)
        return event


class TestProcessor:
    """Test suite for Processor ABC."""

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        """Create a mock event bus."""
        return MagicMock(spec=EventBus)

    @pytest.fixture
    def sample_event(self) -> StandardEvent:
        """Create a sample event for testing."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            timestamp=__import__("datetime").datetime.utcnow(),
        )
        return StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload=payload.model_dump(),
        )

    def test_init(self, mock_event_bus: MagicMock) -> None:
        """Test processor initialization."""
        processor = MockProcessor(mock_event_bus)

        assert processor._event_bus == mock_event_bus
        assert processor.is_running is False

    @pytest.mark.asyncio
    async def test_start(self, mock_event_bus: MagicMock) -> None:
        """Test processor start lifecycle."""
        processor = MockProcessor(mock_event_bus)

        assert processor.is_running is False

        await processor.start()

        assert processor.is_running is True

    @pytest.mark.asyncio
    async def test_stop(self, mock_event_bus: MagicMock) -> None:
        """Test processor stop lifecycle."""
        processor = MockProcessor(mock_event_bus)

        await processor.start()
        assert processor.is_running is True

        await processor.stop()
        assert processor.is_running is False

    @pytest.mark.asyncio
    async def test_process(self, mock_event_bus: MagicMock, sample_event: StandardEvent) -> None:
        """Test process method stores events."""
        processor = MockProcessor(mock_event_bus)

        result = await processor.process(sample_event)

        assert result == sample_event
        assert len(processor.processed_events) == 1
        assert processor.processed_events[0] == sample_event

    def test_is_running_property(self, mock_event_bus: MagicMock) -> None:
        """Test is_running property."""
        processor = MockProcessor(mock_event_bus)

        assert processor.is_running is False

        processor._running = True
        assert processor.is_running is True
