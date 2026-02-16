"""
Tests for strategy modules.
"""

import pytest

from src.strategies.trader_scoring import calculate_trader_score, select_top_traders
from src.strategies.position_detection import detect_position_changes, calculate_btc_exposure
from src.strategies.signal_generation import generate_individual_signal, determine_recommendation


class TestTraderScoring:
    """Tests for trader scoring."""

    def test_calculate_trader_score_high_performer(self, sample_trader):
        """Test scoring a high-performing trader."""
        score = calculate_trader_score(sample_trader)

        assert score > 0
        assert isinstance(score, float)

    def test_calculate_trader_score_low_performer(self):
        """Test scoring a low-performing trader."""
        trader = {
            "accountValue": 10000,
            "windowPerformances": [
                ["day", {"pnl": "-1000", "roi": "-0.1", "vlm": "10000"}],
                ["week", {"pnl": "-5000", "roi": "-0.5", "vlm": "50000"}],
                ["month", {"pnl": "-20000", "roi": "-2.0", "vlm": "200000"}],
                ["allTime", {"pnl": "-50000", "roi": "-5.0", "vlm": "500000"}],
            ],
        }

        score = calculate_trader_score(trader)

        # Score should be low or negative
        assert score < 50

    def test_select_top_traders(self):
        """Test selecting top traders."""
        leaderboard_data = {
            "leaderboardRows": [
                {
                    "ethAddress": "0x1...",
                    "accountValue": "10000000",
                    "displayName": "Whale1",
                    "windowPerformances": [
                        ["allTime", {"pnl": "5000000", "roi": "5.0", "vlm": "100000000"}],
                    ],
                },
                {
                    "ethAddress": "0x2...",
                    "accountValue": "5000000",
                    "displayName": "Whale2",
                    "windowPerformances": [
                        ["allTime", {"pnl": "2000000", "roi": "2.0", "vlm": "50000000"}],
                    ],
                },
            ]
        }

        result = select_top_traders(leaderboard_data, max_count=10, min_score=0)

        assert len(result) == 2
        assert result[0]["ethAddress"] == "0x1..."


class TestPositionDetection:
    """Tests for position detection."""

    def test_detect_position_changes_open(self, sample_position):
        """Test detecting a new position."""
        changes = detect_position_changes(None, sample_position)

        assert len(changes) > 0
        assert changes[0]["action"] == "open"
        assert changes[0]["coin"] == "BTC"

    def test_detect_position_changes_no_change(self, sample_position):
        """Test when there are no changes."""
        changes = detect_position_changes(sample_position, sample_position)

        assert len(changes) == 0

    def test_detect_position_changes_close(self, sample_position):
        """Test detecting a position close."""
        empty_state = {
            "marginSummary": {"accountValue": "1000000"},
            "assetPositions": [],
        }

        changes = detect_position_changes(sample_position, empty_state)

        assert len(changes) > 0
        assert changes[0]["action"] == "close"

    def test_calculate_btc_exposure(self):
        """Test BTC exposure calculation."""
        positions = [
            {"coin": "BTC", "szi": 1.5, "positionValue": 112500},
            {"coin": "ETH", "szi": -10, "positionValue": 25000},
        ]

        exposure = calculate_btc_exposure(positions)

        assert isinstance(exposure, float)


class TestSignalGeneration:
    """Tests for signal generation."""

    def test_generate_individual_signal(self):
        """Test generating an individual signal."""
        position_change = {
            "coin": "BTC",
            "direction": "long",
            "action": "open",
            "currSize": 1.5,
            "delta": 1.5,
        }

        signal = generate_individual_signal(
            eth_address="0x123...",
            position_change=position_change,
            trader_score=75.0,
            current_price=75000.0,
        )

        assert signal is not None
        assert signal["coin"] == "BTC"
        assert signal["direction"] == "long"
        assert signal["confidence"] > 0

    def test_generate_individual_signal_non_btc(self):
        """Test that non-BTC signals return None."""
        position_change = {
            "coin": "ETH",
            "direction": "long",
            "action": "open",
            "currSize": 10,
            "delta": 10,
        }

        signal = generate_individual_signal(
            eth_address="0x123...",
            position_change=position_change,
            trader_score=75.0,
            current_price=2500.0,
        )

        assert signal is None

    def test_determine_recommendation_long(self):
        """Test LONG recommendation."""
        result = determine_recommendation(0.7, 0.2)
        assert result == "LONG"

    def test_determine_recommendation_short(self):
        """Test SHORT recommendation."""
        result = determine_recommendation(0.2, 0.7)
        assert result == "SHORT"

    def test_determine_recommendation_neutral(self):
        """Test NEUTRAL recommendation."""
        result = determine_recommendation(0.4, 0.35)
        assert result == "NEUTRAL"
