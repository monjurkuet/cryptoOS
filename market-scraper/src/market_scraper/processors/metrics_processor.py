# src/market_scraper/processors/metrics_processor.py

"""Metrics processor for collecting and emitting system metrics."""

import time
from collections import defaultdict
from datetime import datetime
from typing import Any

import structlog

from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.processors.base import Processor
from market_scraper.utils.metrics import (
    record_event_published,
)

logger = structlog.get_logger(__name__)


class MetricsProcessor(Processor):
    """Collects and emits system metrics from events.

    Tracks:
    - Events processed per second
    - Processing latency
    - Events by source
    - Events by type

    Metrics are stored in memory and can be retrieved via get_metrics().
    """

    def __init__(self, event_bus: EventBus) -> None:
        """Initialize the metrics processor.

        Args:
            event_bus: Event bus instance
        """
        super().__init__(event_bus)
        # Event counters
        self._event_counts: dict[str, int] = defaultdict(int)
        self._source_counts: dict[str, int] = defaultdict(int)
        self._type_counts: dict[str, int] = defaultdict(int)

        # Timing metrics
        self._processing_latencies: list[float] = []
        self._max_latencies = 1000  # Keep last 1000 latencies

        # Rate tracking
        self._start_time = time.time()
        self._last_reset = datetime.utcnow()
        self._events_in_window = 0
        self._window_size = 60  # 1 minute window

        # Additional metrics
        self._total_events = 0
        self._filtered_events = 0
        self._error_events = 0

    async def process(self, event: StandardEvent) -> StandardEvent | None:
        """Update metrics based on the event.

        Args:
            event: Event to record metrics for

        Returns:
            The original event (metrics processor doesn't modify events)
        """
        try:
            self._record_event_metrics(event)
            return event

        except Exception as e:
            logger.error(
                "Failed to record metrics",
                event_id=event.event_id,
                error=str(e),
            )
            return event

    def _record_event_metrics(self, event: StandardEvent) -> None:
        """Increment counters and track metrics for an event.

        Args:
            event: Event to record
        """
        # Increment total counter
        self._total_events += 1
        self._events_in_window += 1

        # Track by event type
        event_type = str(event.event_type)
        self._type_counts[event_type] += 1

        # Track by source
        source = event.source
        self._source_counts[source] += 1

        # Track processing latency if available
        if event.processing_time_ms is not None:
            self._processing_latencies.append(event.processing_time_ms)
            # Keep only last N latencies
            if len(self._processing_latencies) > self._max_latencies:
                self._processing_latencies.pop(0)

        # Record to Prometheus metrics
        record_event_published(event_type, source)

        # Reset window if needed
        self._check_window_reset()

    def _check_window_reset(self) -> None:
        """Check if the rate window should be reset."""
        now = datetime.utcnow()
        if (now - self._last_reset).total_seconds() >= self._window_size:
            self._events_in_window = 0
            self._last_reset = now

    def get_metrics(self) -> dict[str, Any]:
        """Return current metrics summary.

        Returns:
            Dictionary containing all current metrics
        """
        elapsed = time.time() - self._start_time
        events_per_second = self._total_events / elapsed if elapsed > 0 else 0

        # Calculate latency stats
        latency_stats = {}
        if self._processing_latencies:
            latencies = self._processing_latencies
            latency_stats = {
                "count": len(latencies),
                "avg_ms": sum(latencies) / len(latencies),
                "min_ms": min(latencies),
                "max_ms": max(latencies),
                "p50_ms": self._percentile(latencies, 50),
                "p95_ms": self._percentile(latencies, 95),
                "p99_ms": self._percentile(latencies, 99),
            }

        return {
            "total_events": self._total_events,
            "events_per_second": round(events_per_second, 2),
            "events_in_current_window": self._events_in_window,
            "window_duration_seconds": self._window_size,
            "uptime_seconds": round(elapsed, 2),
            "by_source": dict(self._source_counts),
            "by_type": dict(self._type_counts),
            "latency_ms": latency_stats,
            "filtered_events": self._filtered_events,
            "error_events": self._error_events,
        }

    def _percentile(self, data: list[float], percentile: float) -> float:
        """Calculate percentile from a list of values.

        Args:
            data: List of float values
            percentile: Percentile to calculate (0-100)

        Returns:
            Percentile value
        """
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * (percentile / 100))
        return sorted_data[min(index, len(sorted_data) - 1)]

    def record_filtered(self) -> None:
        """Record that an event was filtered."""
        self._filtered_events += 1

    def record_error(self) -> None:
        """Record that an error occurred during processing."""
        self._error_events += 1

    def reset(self) -> None:
        """Reset all metrics to initial state."""
        self._event_counts.clear()
        self._source_counts.clear()
        self._type_counts.clear()
        self._processing_latencies.clear()
        self._start_time = time.time()
        self._last_reset = datetime.utcnow()
        self._events_in_window = 0
        self._total_events = 0
        self._filtered_events = 0
        self._error_events = 0
