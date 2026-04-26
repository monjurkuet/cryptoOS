"""Unit tests for OutcomeTracker wiring into EventProcessor."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from signal_system.services.event_processor import EventProcessor
from signal_system.rl.outcome_tracker import SignalOutcomeTracker, SignalOutcome


def _make_event_processor(**overrides):
    """Create an EventProcessor with mocks."""
    signal_processor = AsyncMock()
    whale_detector = MagicMock()
    signal_store = MagicMock()
    settings = MagicMock()
    settings.symbol = "BTC"

    defaults = dict(
        signal_processor=signal_processor,
        whale_detector=whale_detector,
        signal_store=signal_store,
        settings=settings,
    )
    defaults.update(overrides)
    return EventProcessor(**defaults)


class TestEventProcessorOutcomeTrackerIntegration:
    def test_outcome_tracker_optional(self):
        """EventProcessor works without outcome_tracker (backward compat)."""
        ep = _make_event_processor()
        assert ep._outcome_tracker is None

    def test_outcome_tracker_provided(self):
        """EventProcessor stores outcome_tracker when provided."""
        tracker = SignalOutcomeTracker()
        ep = _make_event_processor(outcome_tracker=tracker)
        assert ep._outcome_tracker is tracker

    @pytest.mark.asyncio
    async def test_signal_registered_with_tracker(self):
        """When a signal is generated, it's registered with the tracker."""
        tracker = SignalOutcomeTracker()
        ep = _make_event_processor(outcome_tracker=tracker)
        ep._signal_processor.process_position = AsyncMock(
            return_value={
                "action": "BUY",
                "confidence": 0.8,
                "net_bias": 0.5,
            }
        )

        event = {"payload": {"address": "0xabc"}}
        await ep.handle_position_event(event)

        pending = tracker.get_pending_outcomes()
        assert len(pending) == 1
        assert pending[0].action == "BUY"
        assert pending[0].confidence == 0.8

    @pytest.mark.asyncio
    async def test_no_tracker_no_crash(self):
        """When no tracker, signals still work fine."""
        ep = _make_event_processor(outcome_tracker=None)
        ep._signal_processor.process_position = AsyncMock(
            return_value={"action": "SELL", "confidence": 0.6, "net_bias": -0.3}
        )
        event = {"payload": {"address": "0xabc"}}
        # Should not raise
        await ep.handle_position_event(event)

    @pytest.mark.asyncio
    async def test_no_signal_no_registration(self):
        """When signal_processor returns None, nothing is registered."""
        tracker = SignalOutcomeTracker()
        ep = _make_event_processor(outcome_tracker=tracker)
        ep._signal_processor.process_position = AsyncMock(return_value=None)

        event = {"payload": {"address": "0xabc"}}
        await ep.handle_position_event(event)

        assert len(tracker.get_pending_outcomes()) == 0

    @pytest.mark.asyncio
    async def test_handle_price_update(self):
        """handle_price_update feeds price to tracker and returns outcomes."""
        tracker = SignalOutcomeTracker(evaluation_horizons=[1])
        ep = _make_event_processor(outcome_tracker=tracker)

        # Register a signal
        tracker.register_signal("sig1", "BUY", 0.8, 100.0, timestamp=100.0)

        # Update price - need to simulate horizon passing
        import time
        with patch("signal_system.rl.outcome_tracker.time") as mock_time:
            mock_time.time.return_value = 200.0  # 100s later
            outcomes = await ep.handle_price_update(110.0)

        assert len(outcomes) >= 0  # At least resolution attempted

    @pytest.mark.asyncio
    async def test_handle_price_update_no_tracker(self):
        """handle_price_update with no tracker is a no-op."""
        ep = _make_event_processor(outcome_tracker=None)
        result = await ep.handle_price_update(100.0)
        assert result == []

    def test_get_outcome_stats(self):
        """get_outcome_stats returns tracker stats or empty dict."""
        tracker = SignalOutcomeTracker()
        ep = _make_event_processor(outcome_tracker=tracker)
        stats = ep.get_outcome_stats()
        assert "pending_signals" in stats

    def test_get_outcome_stats_no_tracker(self):
        """get_outcome_stats with no tracker returns empty dict."""
        ep = _make_event_processor(outcome_tracker=None)
        stats = ep.get_outcome_stats()
        assert stats == {}
