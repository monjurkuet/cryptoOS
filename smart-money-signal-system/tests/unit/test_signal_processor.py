"""Unit tests for the Signal Generation Processor."""

import pytest

from signal_system.signal_generation.processor import SignalGenerationProcessor


class TestSignalGenerationProcessor:
    """Tests for SignalGenerationProcessor."""

    def test_init_defaults(self):
        """Test processor initializes with defaults."""
        processor = SignalGenerationProcessor()
        assert processor.symbol == "BTC"
        assert processor._trader_positions == {}
        assert processor._trader_scores == {}
        assert processor._last_signal is None

    def test_init_custom_symbol(self):
        """Test processor initializes with custom symbol."""
        processor = SignalGenerationProcessor(symbol="ETH")
        assert processor.symbol == "ETH"

    @pytest.mark.asyncio
    async def test_process_position_valid(self):
        """Test processing a valid position event."""
        processor = SignalGenerationProcessor()

        event = {
            "payload": {
                "address": "0xtrader1",
                "accountValue": "1000000",
                "positions": [
                    {"position": {"coin": "BTC", "szi": "10.5"}}
                ],
            }
        }

        signal = await processor.process_position(event)

        # No signal should be generated with just one position (no score)
        # But position should be stored
        assert "0xtrader1" in processor._trader_positions

    @pytest.mark.asyncio
    async def test_process_position_no_address(self):
        """Test processing position without address."""
        processor = SignalGenerationProcessor()

        event = {"payload": {}}

        signal = await processor.process_position(event)

        assert signal is None

    @pytest.mark.asyncio
    async def test_process_scored_traders(self):
        """Test processing scored traders event."""
        processor = SignalGenerationProcessor()

        event = {
            "payload": {
                "traders": [
                    {"address": "0xtrader1", "score": 85},
                    {"address": "0xtrader2", "score": 70},
                ]
            }
        }

        await processor.process_scored_traders(event)

        assert processor._trader_scores["0xtrader1"] == 85
        assert processor._trader_scores["0xtrader2"] == 70

    @pytest.mark.asyncio
    async def test_signal_generation_long_bias(self):
        """Test signal generation with long bias."""
        processor = SignalGenerationProcessor()

        # Add traders with scores and long positions
        processor._trader_scores = {
            "0xtrader1": 80,
            "0xtrader2": 70,
            "0xtrader3": 60,
        }

        processor._trader_positions = {
            "0xtrader1": {
                "positions": [{"position": {"coin": "BTC", "szi": "10.0"}}]
            },
            "0xtrader2": {
                "positions": [{"position": {"coin": "BTC", "szi": "5.0"}}]
            },
            "0xtrader3": {
                "positions": [{"position": {"coin": "BTC", "szi": "-2.0"}}]  # Short
            },
        }

        signal = processor._generate_signal()

        assert signal is not None
        assert signal["action"] == "BUY"
        assert signal["net_bias"] > 0
        assert signal["traders_long"] == 2
        assert signal["traders_short"] == 1

    @pytest.mark.asyncio
    async def test_signal_generation_short_bias(self):
        """Test signal generation with short bias."""
        processor = SignalGenerationProcessor()

        # Add traders with scores and short positions
        processor._trader_scores = {
            "0xtrader1": 80,
            "0xtrader2": 70,
            "0xtrader3": 60,
        }

        processor._trader_positions = {
            "0xtrader1": {
                "positions": [{"position": {"coin": "BTC", "szi": "-10.0"}}]
            },
            "0xtrader2": {
                "positions": [{"position": {"coin": "BTC", "szi": "-5.0"}}]
            },
            "0xtrader3": {
                "positions": [{"position": {"coin": "BTC", "szi": "2.0"}}]  # Long
            },
        }

        signal = processor._generate_signal()

        assert signal is not None
        assert signal["action"] == "SELL"
        assert signal["net_bias"] < 0
        assert signal["traders_long"] == 1
        assert signal["traders_short"] == 2

    @pytest.mark.asyncio
    async def test_signal_generation_neutral(self):
        """Test signal generation with neutral bias."""
        processor = SignalGenerationProcessor()

        # Add traders with balanced positions
        processor._trader_scores = {
            "0xtrader1": 70,
            "0xtrader2": 70,
        }

        processor._trader_positions = {
            "0xtrader1": {
                "positions": [{"position": {"coin": "BTC", "szi": "10.0"}}]
            },
            "0xtrader2": {
                "positions": [{"position": {"coin": "BTC", "szi": "-10.0"}}]
            },
        }

        signal = processor._generate_signal()

        assert signal is not None
        assert signal["action"] == "NEUTRAL"
        assert abs(signal["net_bias"]) < 0.2

    def test_should_emit_first_signal(self):
        """Test that first signal is always emitted."""
        processor = SignalGenerationProcessor()

        signal = {"action": "BUY", "net_bias": 0.5}

        assert processor._should_emit(signal) is True

    def test_should_emit_action_change(self):
        """Test that action change triggers emission."""
        processor = SignalGenerationProcessor()
        processor._last_signal = {"action": "BUY", "net_bias": 0.5}

        signal = {"action": "SELL", "net_bias": -0.3}

        assert processor._should_emit(signal) is True

    def test_should_emit_bias_change(self):
        """Test that significant bias change triggers emission."""
        processor = SignalGenerationProcessor()
        processor._last_signal = {"action": "BUY", "net_bias": 0.5}

        # 15% bias change (> 10% threshold)
        signal = {"action": "BUY", "net_bias": 0.65}

        assert processor._should_emit(signal) is True

    def test_should_emit_insignificant_change(self):
        """Test that insignificant change doesn't trigger emission."""
        processor = SignalGenerationProcessor()
        processor._last_signal = {"action": "BUY", "net_bias": 0.5}

        # 5% bias change (< 10% threshold)
        signal = {"action": "BUY", "net_bias": 0.55}

        assert processor._should_emit(signal) is False

    def test_get_stats(self):
        """Test getting processor statistics."""
        processor = SignalGenerationProcessor()
        processor._trader_positions = {"0x1": {}, "0x2": {}}
        processor._trader_scores = {"0x1": 80}
        processor._signals_generated = 5

        stats = processor.get_stats()

        assert stats["tracked_traders"] == 2
        assert stats["scored_traders"] == 1
        assert stats["signals_generated"] == 5

    def test_get_latest_signal(self):
        """Test getting the latest signal."""
        processor = SignalGenerationProcessor()

        assert processor.get_latest_signal() is None

        processor._last_signal = {"action": "BUY", "net_bias": 0.5}

        assert processor.get_latest_signal() == {"action": "BUY", "net_bias": 0.5}

    def test_signal_format(self):
        """Test signal output format."""
        processor = SignalGenerationProcessor()

        processor._trader_scores = {"0xtrader1": 70}
        processor._trader_positions = {
            "0xtrader1": {
                "positions": [{"position": {"coin": "BTC", "szi": "10.0"}}]
            },
        }

        signal = processor._generate_signal()

        assert signal is not None
        assert "symbol" in signal
        assert "action" in signal
        assert "confidence" in signal
        assert "long_bias" in signal
        assert "short_bias" in signal
        assert "net_bias" in signal
        assert "traders_long" in signal
        assert "traders_short" in signal
        assert "timestamp" in signal

    def test_confidence_calculation(self):
        """Test confidence is calculated from net bias."""
        processor = SignalGenerationProcessor()

        processor._trader_scores = {"0xtrader1": 100}
        processor._trader_positions = {
            "0xtrader1": {
                "positions": [{"position": {"coin": "BTC", "szi": "10.0"}}]
            },
        }

        signal = processor._generate_signal()

        # Strong long bias should have high confidence
        assert signal is not None
        assert signal["confidence"] >= 0
        assert signal["confidence"] <= 1.0
        # Confidence = min(abs(net_bias) * 2, 1.0)
        # With one trader long, net_bias = 1.0, confidence = 1.0
        assert signal["confidence"] == 1.0

    def test_no_positions_no_signal(self):
        """Test that no signal is generated without positions."""
        processor = SignalGenerationProcessor()

        signal = processor._generate_signal()

        assert signal is None

    def test_different_symbol_positions_ignored(self):
        """Test that positions for different symbols are ignored."""
        processor = SignalGenerationProcessor(symbol="BTC")

        processor._trader_scores = {"0xtrader1": 70}
        processor._trader_positions = {
            "0xtrader1": {
                "positions": [{"position": {"coin": "ETH", "szi": "10.0"}}]
            },
        }

        signal = processor._generate_signal()

        # No BTC positions, so no signal
        assert signal is None

    def test_weighted_scoring(self):
        """Test that traders are weighted by their scores."""
        processor = SignalGenerationProcessor()

        # High scorer going long
        processor._trader_scores = {
            "0xhigh": 100,  # Weight = 1.0
            "0xlow": 10,    # Weight = 0.1
        }

        processor._trader_positions = {
            "0xhigh": {
                "positions": [{"position": {"coin": "BTC", "szi": "10.0"}}]  # Long
            },
            "0xlow": {
                "positions": [{"position": {"coin": "BTC", "szi": "-10.0"}}]  # Short
            },
        }

        signal = processor._generate_signal()

        assert signal is not None
        # High scorer's weight dominates
        assert signal["action"] == "BUY"
        assert signal["net_bias"] > 0
