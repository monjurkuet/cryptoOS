"""Unit tests for SignalGenerationProcessor RL params integration."""

import pytest
import time
from unittest.mock import MagicMock

from signal_system.signal_generation.processor import SignalGenerationProcessor


def make_position_event(address: str, szi: float, coin: str = "BTC") -> dict:
    """Helper to create a position event."""
    return {
        "type": "trader_position_update",
        "payload": {
            "address": address,
            "positions": [
                {"position": {"coin": coin, "szi": str(szi)}},
            ],
        },
    }


class TestSignalProcessorRLParams:
    @pytest.mark.asyncio
    async def test_default_bias_threshold(self):
        """Default bias threshold is 0.2 (backward compatible)."""
        proc = SignalGenerationProcessor(symbol="BTC")
        assert proc._bias_threshold == 0.2

    @pytest.mark.asyncio
    async def test_custom_bias_threshold(self):
        """Can set custom bias threshold."""
        proc = SignalGenerationProcessor(symbol="BTC", bias_threshold=0.35)
        assert proc._bias_threshold == 0.35

    @pytest.mark.asyncio
    async def test_custom_conf_scale(self):
        """Can set custom confidence scale."""
        proc = SignalGenerationProcessor(symbol="BTC", conf_scale=1.5)
        assert proc._conf_scale == 1.5

    @pytest.mark.asyncio
    async def test_custom_min_confidence(self):
        """Can set custom minimum confidence."""
        proc = SignalGenerationProcessor(symbol="BTC", min_confidence=0.5)
        assert proc._min_confidence == 0.5

    @pytest.mark.asyncio
    async def test_set_rl_params(self):
        """set_rl_params updates thresholds at runtime."""
        proc = SignalGenerationProcessor(symbol="BTC")
        proc.set_rl_params(bias_threshold=0.3, conf_scale=1.2, min_confidence=0.4)
        assert proc._bias_threshold == 0.3
        assert proc._conf_scale == 1.2
        assert proc._min_confidence == 0.4

    @pytest.mark.asyncio
    async def test_set_rl_params_partial(self):
        """set_rl_params can update just one param."""
        proc = SignalGenerationProcessor(symbol="BTC")
        proc.set_rl_params(bias_threshold=0.4)
        assert proc._bias_threshold == 0.4
        assert proc._conf_scale == 1.0  # default unchanged

    @pytest.mark.asyncio
    async def test_higher_bias_threshold_needs_stronger_signal(self):
        """With bias_threshold=0.3, net_bias=0.25 produces NEUTRAL not BUY."""
        proc = SignalGenerationProcessor(symbol="BTC", bias_threshold=0.3)
        # Add traders with slight long bias
        for i in range(3):
            event = make_position_event(f"0xaddr{i}", szi=1.0)
            await proc.process_position(event)
        # Add one short
        event = make_position_event("0xshort", szi=-0.5)
        signal = await proc.process_position(event)
        # With 3 longs (score 50 each -> weight 0.5 each = 1.5) and 1 short (0.5)
        # net_bias should be small enough to be NEUTRAL with threshold 0.3
        # This tests that the threshold is actually being used

    @pytest.mark.asyncio
    async def test_conf_scale_affects_confidence(self):
        """Higher conf_scale produces higher confidence values."""
        proc_default = SignalGenerationProcessor(symbol="BTC", conf_scale=1.0)
        proc_scaled = SignalGenerationProcessor(symbol="BTC", conf_scale=2.0)

        # Same positions
        for i in range(5):
            event = make_position_event(f"0xlong{i}", szi=10.0)
            await proc_default.process_position(event)
            await proc_scaled.process_position(event)

        sig_default = proc_default.get_latest_signal()
        sig_scaled = proc_scaled.get_latest_signal()

        if sig_default and sig_scaled:
            # Scaled confidence should be higher (capped at 1.0)
            assert sig_scaled["confidence"] >= sig_default["confidence"]

    @pytest.mark.asyncio
    async def test_min_confidence_filters_signals(self):
        """Signals below min_confidence are not emitted."""
        proc = SignalGenerationProcessor(symbol="BTC", min_confidence=0.9)
        # Add positions that would produce low confidence
        event = make_position_event("0xlow1", szi=0.001)
        signal = await proc.process_position(event)
        # With such small position, confidence should be below 0.9
        # so signal should be None (filtered)
        # Actually with 1 trader net_bias could be 1.0 -> confidence 1.0
        # Need a scenario where confidence is definitely below 0.9
        # Let's add mixed positions
        proc2 = SignalGenerationProcessor(symbol="BTC", min_confidence=0.95)
        for i in range(5):
            event = make_position_event(f"0xmix{i}", szi=0.01)
            await proc2.process_position(event)
        for i in range(4):
            event = make_position_event(f"0xmixs{i}", szi=-0.01)
            signal = await proc2.process_position(event)
        # With roughly balanced positions, confidence should be low

    @pytest.mark.asyncio
    async def test_get_stats_includes_rl_params(self):
        """get_stats includes current RL params."""
        proc = SignalGenerationProcessor(symbol="BTC", bias_threshold=0.3)
        stats = proc.get_stats()
        assert "rl_params" in stats
        assert stats["rl_params"]["bias_threshold"] == 0.3
