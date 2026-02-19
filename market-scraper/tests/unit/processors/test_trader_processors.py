# tests/unit/processors/test_trader_processors.py

"""Tests for trader-related processors."""

import pytest

from market_scraper.core.events import StandardEvent
from market_scraper.processors.position_inference import (
    PositionInferenceProcessor,
    has_likely_active_position,
    parse_performances,
)
from market_scraper.processors.trader_scoring import (
    TraderScoringProcessor,
    calculate_trader_score,
    get_trader_tags,
)
from market_scraper.processors.signal_generation import (
    SignalGenerationProcessor,
    calculate_confidence,
    determine_recommendation,
)
from market_scraper.event_bus.memory_bus import MemoryEventBus


# Sample trader data
SAMPLE_TRADER = {
    "ethAddress": "0x1234567890abcdef1234567890abcdef12345678",
    "displayName": "TestTrader",
    "accountValue": 1_500_000,
    "windowPerformances": [
        ["allTime", {"roi": 2.5, "pnl": 3_000_000, "vlm": 50_000_000}],
        ["month", {"roi": 0.5, "pnl": 500_000, "vlm": 10_000_000}],
        ["week", {"roi": 0.1, "pnl": 100_000, "vlm": 2_000_000}],
        ["day", {"roi": 0.02, "pnl": 20_000, "vlm": 500_000}],
    ],
}


class TestPositionInference:
    """Tests for position inference functions."""

    def test_parse_performances_list_format(self):
        """Test parsing performances from list format."""
        result = parse_performances(SAMPLE_TRADER)

        assert "allTime" in result
        assert "month" in result
        assert "week" in result
        assert "day" in result

        assert result["day"]["roi"] == 0.02
        assert result["day"]["pnl"] == 20_000

    def test_parse_performances_dict_format(self):
        """Test parsing performances from dict format."""
        trader = {
            "windowPerformances": {
                "day": {"roi": 0.01, "pnl": 10_000},
            }
        }

        result = parse_performances(trader)
        assert result["day"]["roi"] == 0.01

    def test_has_likely_active_position_day_roi(self):
        """Test position inference from day ROI."""
        has_position, reason, confidence = has_likely_active_position(SAMPLE_TRADER)

        assert has_position is True
        assert "day_roi" in reason
        assert confidence > 0

    def test_has_likely_active_position_no_activity(self):
        """Test position inference with no activity."""
        trader = {
            "accountValue": 1_000_000,
            "windowPerformances": [
                ["day", {"roi": 0, "pnl": 0, "vlm": 0}],
            ],
        }

        has_position, reason, confidence = has_likely_active_position(trader)

        assert has_position is False
        assert reason == "no_activity_indicators"

    def test_has_likely_active_position_high_volume(self):
        """Test position inference from high volume."""
        trader = {
            "accountValue": 1_000_000,
            "windowPerformances": [
                ["day", {"roi": 0, "pnl": 0, "vlm": 500_000}],
            ],
        }

        has_position, reason, confidence = has_likely_active_position(trader)

        assert has_position is True
        assert "day_volume" in reason


class TestTraderScoring:
    """Tests for trader scoring functions."""

    def test_calculate_trader_score(self):
        """Test trader score calculation."""
        score = calculate_trader_score(SAMPLE_TRADER)

        # Should have points from:
        # - All-time ROI: 2.5 * 30 = 75 (capped at 30)
        # - Month ROI: 0.5 * 50 = 25 (capped at 25)
        # - Week ROI: 0.1 * 100 = 10
        # - Account value: 8 (1M+)
        # - Volume: 4 (10M+)
        # - Consistency bonus: 5 (all positive)

        assert score > 50
        assert score < 150

    def test_get_trader_tags(self):
        """Test trader tag generation."""
        score = calculate_trader_score(SAMPLE_TRADER)
        tags = get_trader_tags(SAMPLE_TRADER, score)

        # Should have "large" tag for 1M+ account
        assert "large" in tags

        # Should have "consistent" tag for all positive ROIs
        assert "consistent" in tags

    def test_score_with_negative_week(self):
        """Test scoring with negative week ROI."""
        trader = {
            **SAMPLE_TRADER,
            "windowPerformances": [
                ["allTime", {"roi": 2.5, "pnl": 3_000_000, "vlm": 50_000_000}],
                ["month", {"roi": 0.5, "pnl": 500_000, "vlm": 10_000_000}],
                ["week", {"roi": -0.1, "pnl": -100_000, "vlm": 2_000_000}],  # Negative
                ["day", {"roi": 0.02, "pnl": 20_000, "vlm": 500_000}],
            ],
        }

        score = calculate_trader_score(trader)

        # Week ROI penalty: -0.1 * 100 = -10 (capped at -10)
        # Should still have positive score
        assert score > 0


class TestSignalGeneration:
    """Tests for signal generation functions."""

    def test_determine_recommendation_buy(self):
        """Test buy recommendation."""
        rec = determine_recommendation(long_bias=0.6, short_bias=0.2)
        assert rec == "BUY"

    def test_determine_recommendation_sell(self):
        """Test sell recommendation."""
        rec = determine_recommendation(long_bias=0.2, short_bias=0.6)
        assert rec == "SELL"

    def test_determine_recommendation_neutral(self):
        """Test neutral recommendation."""
        rec = determine_recommendation(long_bias=0.4, short_bias=0.35)
        assert rec == "NEUTRAL"

    def test_calculate_confidence(self):
        """Test confidence calculation."""
        # High agreement, high participation
        confidence = calculate_confidence(
            long_bias=0.8,
            short_bias=0.1,
            total_weight=50,
            traders_involved=80,
        )

        assert confidence > 0.5
        assert confidence <= 1.0

        # Low agreement, low participation
        confidence = calculate_confidence(
            long_bias=0.5,
            short_bias=0.45,
            total_weight=10,
            traders_involved=10,
        )

        assert confidence < 0.5


class TestProcessors:
    """Tests for processor classes."""

    @pytest.fixture
    def event_bus(self):
        """Create an event bus for testing."""
        bus = MemoryEventBus()
        return bus

    @pytest.mark.asyncio
    async def test_position_inference_processor(self, event_bus):
        """Test position inference processor."""
        processor = PositionInferenceProcessor(event_bus)

        # Create a leaderboard event
        event = StandardEvent.create(
            event_type="leaderboard",
            source="test",
            payload={
                "traders": [SAMPLE_TRADER],
            },
        )

        result = await processor.process(event)

        assert result is not None
        assert result.event_type == "inferred_positions"
        assert result.payload["inferred_count"] == 1

    @pytest.mark.asyncio
    async def test_trader_scoring_processor(self, event_bus):
        """Test trader scoring processor."""
        processor = TraderScoringProcessor(event_bus, min_score=0.0)

        # Create a leaderboard event
        event = StandardEvent.create(
            event_type="leaderboard",
            source="test",
            payload={
                "rows": [SAMPLE_TRADER],
            },
        )

        result = await processor.process(event)

        assert result is not None
        assert result.event_type == "scored_traders"
        assert result.payload["count"] == 1
        assert result.payload["traders"][0]["score"] > 0

    @pytest.mark.asyncio
    async def test_trader_scoring_processor_min_score(self, event_bus):
        """Test trader scoring processor with minimum score."""
        processor = TraderScoringProcessor(event_bus, min_score=100.0)

        # Create a leaderboard event
        event = StandardEvent.create(
            event_type="leaderboard",
            source="test",
            payload={
                "rows": [SAMPLE_TRADER],
            },
        )

        result = await processor.process(event)

        # No traders should meet the high threshold
        assert result is None

    @pytest.mark.asyncio
    async def test_signal_generation_processor_no_data(self, event_bus):
        """Test signal generation processor with no data."""
        processor = SignalGenerationProcessor(event_bus)

        # Create a price event (should not generate signal alone)
        event = StandardEvent.create(
            event_type="mark_price",
            source="test",
            payload={"mark_price": 100000},
        )

        result = await processor.process(event)

        # No signal without trader positions
        assert result is None

    @pytest.mark.asyncio
    async def test_processor_ignores_wrong_event_type(self, event_bus):
        """Test that processors ignore wrong event types."""
        processor = PositionInferenceProcessor(event_bus)

        # Create a trade event (wrong type)
        event = StandardEvent.create(
            event_type="trade",
            source="test",
            payload={"symbol": "BTC", "price": 100000},
        )

        result = await processor.process(event)

        assert result is None
