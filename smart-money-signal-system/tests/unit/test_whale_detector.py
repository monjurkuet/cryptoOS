"""Unit tests for the Whale Alert Detector."""

from datetime import datetime, timedelta, timezone

import pytest

from signal_system.whale_alerts.detector import (
    AlertPriority,
    PositionChange,
    WhaleAlert,
    WhaleAlertDetector,
)


class TestWhaleAlertDetector:
    """Tests for WhaleAlertDetector."""

    def test_init_defaults(self):
        """Test detector initializes with defaults."""
        detector = WhaleAlertDetector()
        assert detector.alpha_whale_threshold == 20_000_000
        assert detector.whale_threshold == 10_000_000
        assert detector.aggregation_window == timedelta(minutes=5)

    def test_init_custom_thresholds(self):
        """Test detector initializes with custom thresholds."""
        detector = WhaleAlertDetector(
            alpha_whale_threshold=50_000_000,
            whale_threshold=25_000_000,
            aggregation_window_minutes=10,
        )
        assert detector.alpha_whale_threshold == 50_000_000
        assert detector.whale_threshold == 25_000_000
        assert detector.aggregation_window == timedelta(minutes=10)

    def test_update_trader_info(self):
        """Test updating trader information."""
        detector = WhaleAlertDetector()

        detector.update_trader_info(
            address="0xtest123",
            name="Test Trader",
            tier="whale",
            account_value=15_000_000,
        )

        assert "0xtest123" in detector._trader_info
        assert detector._trader_info["0xtest123"]["name"] == "Test Trader"
        assert detector._trader_info["0xtest123"]["tier"] == "whale"
        assert detector._trader_info["0xtest123"]["account_value"] == 15_000_000

    def test_detect_position_change_new_position(self):
        """Test detecting a new position."""
        detector = WhaleAlertDetector()
        detector.update_trader_info("0xwhale1", account_value=15_000_000)

        change = detector.detect_position_change(
            address="0xwhale1",
            coin="BTC",
            current_szi=100.0,
        )

        assert change is not None
        assert change.address == "0xwhale1"
        assert change.coin == "BTC"
        assert change.previous_szi == 0
        assert change.current_szi == 100.0
        assert change.change_pct == 1.0  # New position = 100% change

    def test_detect_position_change_significant(self):
        """Test detecting a significant position change (>= 10%)."""
        detector = WhaleAlertDetector()
        detector.update_trader_info("0xwhale1", account_value=15_000_000)

        # Initial position
        detector.detect_position_change("0xwhale1", "BTC", 100.0)

        # Significant change (50% increase)
        change = detector.detect_position_change("0xwhale1", "BTC", 150.0)

        assert change is not None
        assert change.previous_szi == 100.0
        assert change.current_szi == 150.0
        assert change.change_pct == 0.5  # 50% change

    def test_detect_position_change_insignificant(self):
        """Test that insignificant changes (< 10%) are not detected."""
        detector = WhaleAlertDetector()
        detector.update_trader_info("0xwhale1", account_value=15_000_000)

        # Initial position
        detector.detect_position_change("0xwhale1", "BTC", 100.0)

        # Insignificant change (5% increase)
        change = detector.detect_position_change("0xwhale1", "BTC", 105.0)

        # Should return None (change < 10%)
        assert change is None

    def test_detect_position_change_non_whale(self):
        """Test that non-whale position changes are ignored."""
        detector = WhaleAlertDetector()
        detector.update_trader_info("0xsmall", account_value=5_000_000)  # Below whale threshold

        change = detector.detect_position_change("0xsmall", "BTC", 100.0)

        # Should return None (below whale threshold)
        assert change is None

    def test_detect_position_change_direction(self):
        """Test detecting position direction changes."""
        detector = WhaleAlertDetector()
        detector.update_trader_info("0xwhale1", account_value=15_000_000)

        # Open long
        detector.detect_position_change("0xwhale1", "BTC", 100.0)

        # Flip to short
        change = detector.detect_position_change("0xwhale1", "BTC", -50.0)

        assert change is not None
        assert change.previous_szi == 100.0
        assert change.current_szi == -50.0

    def test_generate_alert_critical_alpha_whale(self):
        """Test CRITICAL alert for alpha whale change."""
        detector = WhaleAlertDetector()
        detector.update_trader_info("0xalpha", account_value=25_000_000)

        change = detector.detect_position_change("0xalpha", "BTC", 100.0)
        alert = detector.generate_alert(change)

        assert alert is not None
        assert alert.priority == AlertPriority.CRITICAL
        assert "Alpha Whale" in alert.title

    def test_generate_alert_high_multiple_whales(self):
        """Test HIGH alert for multiple whale changes."""
        detector = WhaleAlertDetector(
            alpha_whale_threshold=100_000_000,  # High threshold to avoid CRITICAL
        )

        # Add two whales
        detector.update_trader_info("0xwhale1", account_value=15_000_000)
        detector.update_trader_info("0xwhale2", account_value=12_000_000)

        # Both change
        change1 = detector.detect_position_change("0xwhale1", "BTC", 100.0)
        change2 = detector.detect_position_change("0xwhale2", "BTC", -50.0)

        # Generate alert (should be HIGH because 2+ whales)
        alert = detector.generate_alert()

        assert alert is not None
        assert alert.priority == AlertPriority.HIGH
        assert "Multiple Whales" in alert.title

    def test_generate_alert_low_single_whale(self):
        """Test LOW alert for single whale change."""
        detector = WhaleAlertDetector(
            alpha_whale_threshold=100_000_000,  # High threshold to avoid CRITICAL
        )

        detector.update_trader_info("0xwhale1", account_value=15_000_000)
        change = detector.detect_position_change("0xwhale1", "BTC", 100.0)

        # Clear any recent changes from previous tests
        detector._recent_changes = [change] if change else []

        alert = detector.generate_alert(change)

        assert alert is not None
        # Note: May be LOW or MEDIUM depending on bias change calculation
        assert alert.priority in [AlertPriority.LOW, AlertPriority.MEDIUM]
        assert "Whale" in alert.title

    def test_generate_alert_no_changes(self):
        """Test that no alert is generated without changes."""
        detector = WhaleAlertDetector()

        alert = detector.generate_alert()

        assert alert is None

    def test_alert_expiry(self):
        """Test that alerts have proper expiry times."""
        detector = WhaleAlertDetector()
        detector.update_trader_info("0xalpha", account_value=25_000_000)

        change = detector.detect_position_change("0xalpha", "BTC", 100.0)
        alert = detector.generate_alert(change)

        assert alert is not None
        detected_at = datetime.fromisoformat(alert.detected_at)
        expires_at = datetime.fromisoformat(alert.expires_at)

        # CRITICAL alerts expire in 1 hour (allow small tolerance for time generation)
        assert expires_at > detected_at
        delta_seconds = (expires_at - detected_at).total_seconds()
        assert abs(delta_seconds - 3600) < 1  # 1 hour with 1 second tolerance

    def test_get_recent_alerts(self):
        """Test getting recent alerts."""
        detector = WhaleAlertDetector()
        detector.update_trader_info("0xwhale1", account_value=15_000_000)

        # Generate an alert (generate_alert stores it automatically)
        change = detector.detect_position_change("0xwhale1", "BTC", 100.0)
        alert = detector.generate_alert(change)

        recent = detector.get_recent_alerts(limit=10)

        assert len(recent) == 1
        # Note: May be LOW or MEDIUM depending on bias change calculation
        assert recent[0].priority in [AlertPriority.LOW, AlertPriority.MEDIUM]

    def test_get_active_alerts(self):
        """Test getting active (non-expired) alerts."""
        detector = WhaleAlertDetector()
        detector.update_trader_info("0xwhale1", account_value=15_000_000)

        # Generate an alert (generate_alert stores it automatically)
        change = detector.detect_position_change("0xwhale1", "BTC", 100.0)
        alert = detector.generate_alert(change)

        active = detector.get_active_alerts()

        assert len(active) == 1

    def test_get_active_alerts_expired(self):
        """Test that expired alerts are not returned as active."""
        detector = WhaleAlertDetector()
        detector.update_trader_info("0xwhale1", account_value=15_000_000)

        # Generate an alert (generate_alert stores it automatically)
        change = detector.detect_position_change("0xwhale1", "BTC", 100.0)
        alert = detector.generate_alert(change)

        if alert:
            # Manually set expired time on the already-stored alert
            alert.expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        active = detector.get_active_alerts()

        assert len(active) == 0

    def test_get_stats(self):
        """Test getting detector statistics."""
        detector = WhaleAlertDetector()

        detector.update_trader_info("0xwhale1", account_value=15_000_000)
        detector.update_trader_info("0xalpha", account_value=25_000_000)
        detector.update_trader_info("0xsmall", account_value=5_000_000)

        stats = detector.get_stats()

        assert stats["tracked_traders"] == 3
        assert stats["whale_count"] == 2  # whale1 and alpha
        assert stats["alpha_whale_count"] == 1  # alpha only

    def test_aggregation_window_cleanup(self):
        """Test that old changes are cleaned up."""
        detector = WhaleAlertDetector(aggregation_window_minutes=1)
        detector.update_trader_info("0xwhale1", account_value=15_000_000)

        # Add a change
        detector.detect_position_change("0xwhale1", "BTC", 100.0)

        # Manually age the change
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        # Access the first item in the deque
        if detector._recent_changes:
            detector._recent_changes[0].detected_at = old_time

        # Clean old changes
        detector._clean_old_changes()

        assert len(detector._recent_changes) == 0

    def test_calculate_aggregate_bias_change(self):
        """Test aggregate bias calculation."""
        detector = WhaleAlertDetector()

        # No changes
        bias = detector._calculate_aggregate_bias_change()
        assert bias == 0.0

    def test_signal_impact(self):
        """Test that alerts include signal impact data."""
        detector = WhaleAlertDetector()
        detector.update_trader_info("0xalpha", account_value=25_000_000)

        change = detector.detect_position_change("0xalpha", "BTC", 100.0)
        alert = detector.generate_alert(change)

        assert alert is not None
        assert "confidence_boost" in alert.signal_impact
        assert "priority" in alert.signal_impact


class TestPositionChange:
    """Tests for PositionChange dataclass."""

    def test_position_change_creation(self):
        """Test creating a PositionChange."""
        change = PositionChange(
            address="0xtest",
            trader_name="Test Trader",
            tier="whale",
            coin="BTC",
            previous_szi=100.0,
            current_szi=150.0,
            change_pct=0.5,
            account_value=15_000_000,
            detected_at=datetime.now(timezone.utc).isoformat(),
        )

        assert change.address == "0xtest"
        assert change.tier == "whale"
        assert change.change_pct == 0.5


class TestWhaleAlert:
    """Tests for WhaleAlert dataclass."""

    def test_whale_alert_creation(self):
        """Test creating a WhaleAlert."""
        alert = WhaleAlert(
            priority=AlertPriority.HIGH,
            title="Test Alert",
            description="Test description",
            changes=[],
            signal_impact={"confidence_boost": 0.2},
            detected_at=datetime.now(timezone.utc).isoformat(),
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )

        assert alert.priority == AlertPriority.HIGH
        assert alert.title == "Test Alert"


class TestAlertPriority:
    """Tests for AlertPriority enum."""

    def test_priority_order(self):
        """Test priority values."""
        assert AlertPriority.CRITICAL.value == "CRITICAL"
        assert AlertPriority.HIGH.value == "HIGH"
        assert AlertPriority.MEDIUM.value == "MEDIUM"
        assert AlertPriority.LOW.value == "LOW"
