# tests/unit/processors/test_metrics_processor.py

"""Test suite for MetricsProcessor."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from market_scraper.core.events import EventType, MarketDataPayload, StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.processors.metrics_processor import MetricsProcessor


class TestMetricsProcessor:
    """Test suite for MetricsProcessor."""

    @pytest.fixture
    def mock_event_bus(self) -> MagicMock:
        """Create a mock event bus."""
        return MagicMock(spec=EventBus)

    @pytest.fixture
    def processor(self, mock_event_bus: MagicMock) -> MetricsProcessor:
        """Create a MetricsProcessor instance."""
        return MetricsProcessor(mock_event_bus)

    @pytest.fixture
    def sample_event(self) -> StandardEvent:
        """Create a sample event."""
        payload = MarketDataPayload(
            symbol="BTC-USD",
            price=50000.0,
            timestamp=datetime.utcnow(),
        )
        return StandardEvent.create(
            event_type=EventType.TRADE,
            source="hyperliquid",
            payload=payload.model_dump(),
        )

    def test_init(self, mock_event_bus: MagicMock) -> None:
        """Test processor initialization."""
        processor = MetricsProcessor(mock_event_bus)

        assert processor._event_bus == mock_event_bus
        assert processor._total_events == 0
        assert processor._filtered_events == 0
        assert processor._error_events == 0
        assert len(processor._processing_latencies) == 0

    @pytest.mark.asyncio
    async def test_process_updates_counts(
        self,
        processor: MetricsProcessor,
        sample_event: StandardEvent,
    ) -> None:
        """Test that process updates event counts."""
        result = await processor.process(sample_event)

        assert result == sample_event
        assert processor._total_events == 1
        assert processor._type_counts["trade"] == 1
        assert processor._source_counts["hyperliquid"] == 1

    @pytest.mark.asyncio
    async def test_process_records_latency(
        self,
        processor: MetricsProcessor,
    ) -> None:
        """Test that processing latency is recorded."""
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="test",
            payload={"symbol": "BTC-USD", "timestamp": datetime.utcnow().isoformat()},
        )
        event.processing_time_ms = 50.5

        await processor.process(event)

        assert len(processor._processing_latencies) == 1
        assert processor._processing_latencies[0] == 50.5

    @pytest.mark.asyncio
    async def test_process_records_multiple_events(
        self,
        processor: MetricsProcessor,
    ) -> None:
        """Test recording multiple events."""
        for i in range(5):
            event = StandardEvent.create(
                event_type=EventType.TRADE,
                source="hyperliquid",
                payload={"symbol": "BTC-USD", "timestamp": datetime.utcnow().isoformat()},
            )
            await processor.process(event)

        assert processor._total_events == 5
        assert processor._type_counts["trade"] == 5
        assert processor._source_counts["hyperliquid"] == 5

    @pytest.mark.asyncio
    async def test_process_different_types(
        self,
        processor: MetricsProcessor,
    ) -> None:
        """Test recording events of different types."""
        events = [
            StandardEvent.create(
                event_type=EventType.TRADE,
                source="test",
                payload={"symbol": "BTC-USD", "timestamp": datetime.utcnow().isoformat()},
            ),
            StandardEvent.create(
                event_type=EventType.TICKER,
                source="test",
                payload={"symbol": "ETH-USD", "timestamp": datetime.utcnow().isoformat()},
            ),
            StandardEvent.create(
                event_type=EventType.OHLCV,
                source="test",
                payload={"symbol": "SOL-USD", "timestamp": datetime.utcnow().isoformat()},
            ),
        ]

        for event in events:
            await processor.process(event)

        assert processor._total_events == 3
        assert processor._type_counts["trade"] == 1
        assert processor._type_counts["ticker"] == 1
        assert processor._type_counts["ohlcv"] == 1

    @pytest.mark.asyncio
    async def test_process_different_sources(
        self,
        processor: MetricsProcessor,
    ) -> None:
        """Test recording events from different sources."""
        sources = ["hyperliquid", "cbbi", "test"]

        for source in sources:
            event = StandardEvent.create(
                event_type=EventType.TRADE,
                source=source,
                payload={"symbol": "BTC-USD", "timestamp": datetime.utcnow().isoformat()},
            )
            await processor.process(event)

        assert processor._total_events == 3
        for source in sources:
            assert processor._source_counts[source] == 1

    def test_get_metrics_structure(self, processor: MetricsProcessor) -> None:
        """Test that get_metrics returns expected structure."""
        metrics = processor.get_metrics()

        assert "total_events" in metrics
        assert "events_per_second" in metrics
        assert "events_in_current_window" in metrics
        assert "uptime_seconds" in metrics
        assert "by_source" in metrics
        assert "by_type" in metrics
        assert "latency_ms" in metrics

    @pytest.mark.asyncio
    async def test_get_metrics_with_data(
        self,
        processor: MetricsProcessor,
    ) -> None:
        """Test get_metrics with recorded data."""
        # Record some events
        for i in range(10):
            event = StandardEvent.create(
                event_type=EventType.TRADE,
                source="hyperliquid",
                payload={"symbol": "BTC-USD", "timestamp": datetime.utcnow().isoformat()},
            )
            event.processing_time_ms = float(i * 10)
            await processor.process(event)

        metrics = processor.get_metrics()

        assert metrics["total_events"] == 10
        assert metrics["by_source"]["hyperliquid"] == 10
        assert metrics["by_type"]["trade"] == 10

    def test_record_filtered(self, processor: MetricsProcessor) -> None:
        """Test recording filtered events."""
        processor.record_filtered()
        processor.record_filtered()

        assert processor._filtered_events == 2

    def test_record_error(self, processor: MetricsProcessor) -> None:
        """Test recording errors."""
        processor.record_error()

        assert processor._error_events == 1

    def test_reset(self, processor: MetricsProcessor) -> None:
        """Test resetting metrics."""
        # Add some data
        processor._total_events = 100
        processor._source_counts["test"] = 50
        processor._type_counts["trade"] = 50
        processor._processing_latencies = [10.0, 20.0, 30.0]
        processor._filtered_events = 5
        processor._error_events = 3

        processor.reset()

        assert processor._total_events == 0
        assert len(processor._source_counts) == 0
        assert len(processor._type_counts) == 0
        assert len(processor._processing_latencies) == 0
        assert processor._filtered_events == 0
        assert processor._error_events == 0

    def test_percentile(self, processor: MetricsProcessor) -> None:
        """Test percentile calculation."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]

        assert processor._percentile(data, 0) == 1.0
        assert processor._percentile(data, 50) == 3.0
        assert processor._percentile(data, 100) == 5.0

    def test_percentile_empty(self, processor: MetricsProcessor) -> None:
        """Test percentile with empty data."""
        assert processor._percentile([], 50) == 0.0

    @pytest.mark.asyncio
    async def test_latency_stats(self, processor: MetricsProcessor) -> None:
        """Test latency statistics in metrics."""
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0]

        for latency in latencies:
            event = StandardEvent.create(
                event_type=EventType.TRADE,
                source="test",
                payload={"symbol": "BTC-USD", "timestamp": datetime.utcnow().isoformat()},
            )
            event.processing_time_ms = latency
            await processor.process(event)

        metrics = processor.get_metrics()

        assert metrics["latency_ms"]["count"] == 5
        assert metrics["latency_ms"]["avg_ms"] == 30.0
        assert metrics["latency_ms"]["min_ms"] == 10.0
        assert metrics["latency_ms"]["max_ms"] == 50.0
        assert metrics["latency_ms"]["p50_ms"] == 30.0

    def test_check_window_reset(self, processor: MetricsProcessor) -> None:
        """Test window reset check."""
        processor._events_in_window = 100
        processor._last_reset = datetime.utcnow()

        # Should not reset yet
        processor._check_window_reset()
        assert processor._events_in_window == 100

    @pytest.mark.asyncio
    async def test_process_with_exception(
        self,
        processor: MetricsProcessor,
    ) -> None:
        """Test handling of exceptions during processing."""
        # Create a properly mocked event with all required attributes
        from datetime import datetime as dt

        event = MagicMock()
        event.event_type = EventType.TRADE
        event.source = "test"
        event.correlation_id = "corr-id"
        event.event_id = "test-id"
        event.processing_time_ms = None

        # Should return the event even on error (doesn't filter)
        result = await processor.process(event)

        # The processor returns the event on error, not None
        assert result is not None

    @pytest.mark.asyncio
    async def test_latency_limit(
        self,
        processor: MetricsProcessor,
    ) -> None:
        """Test that latency list has a max size."""
        processor._max_latencies = 5

        for i in range(10):
            event = StandardEvent.create(
                event_type=EventType.TRADE,
                source="test",
                payload={"symbol": "BTC-USD", "timestamp": datetime.utcnow().isoformat()},
            )
            event.processing_time_ms = float(i)
            await processor.process(event)

        # Should only keep last 5
        assert len(processor._processing_latencies) == 5
        assert processor._processing_latencies == [5.0, 6.0, 7.0, 8.0, 9.0]
