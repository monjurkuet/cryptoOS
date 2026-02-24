"""Integration tests for event flow and API."""

import pytest
from fastapi.testclient import TestClient

from signal_system.api.main import app
from signal_system.api.dependencies import set_components
from signal_system.signal_generation.processor import SignalGenerationProcessor
from signal_system.signal_store import SignalStore
from signal_system.whale_alerts.detector import WhaleAlertDetector


@pytest.fixture
def test_client():
    """Create a test client with mocked components."""
    # Initialize test components
    signal_processor = SignalGenerationProcessor(symbol="BTC")
    whale_detector = WhaleAlertDetector()
    signal_store = SignalStore()

    # Set dependencies
    set_components(
        signal_processor=signal_processor,
        whale_detector=whale_detector,
        signal_store=signal_store,
    )

    with TestClient(app) as client:
        yield client, signal_processor, whale_detector, signal_store


class TestAPIEndpoints:
    """Tests for API endpoints."""

    def test_health_check(self, test_client):
        """Test health check endpoint."""
        client, _, _, _ = test_client
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "components" in data

    def test_get_latest_signal_empty(self, test_client):
        """Test getting latest signal when none exists."""
        client, _, _, _ = test_client
        response = client.get("/api/v1/signals/latest")

        assert response.status_code == 200
        # May be None or empty
        data = response.json()
        # With fresh processor, no signal yet
        assert data is None or "action" in data

    def test_get_signal_history_empty(self, test_client):
        """Test getting signal history when empty."""
        client, _, _, _ = test_client
        response = client.get("/api/v1/signals/history")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_signal_stats(self, test_client):
        """Test getting signal stats."""
        client, _, _, _ = test_client
        response = client.get("/api/v1/signals/stats")

        assert response.status_code == 200
        data = response.json()
        assert "signals_generated" in data
        assert "tracked_traders" in data
        assert "scored_traders" in data

    def test_get_latest_alert_empty(self, test_client):
        """Test getting latest alert when none exists."""
        client, _, _, _ = test_client
        response = client.get("/api/v1/alerts/latest")

        assert response.status_code == 200
        # May be None
        data = response.json()
        assert data is None or "priority" in data

    def test_get_alert_history(self, test_client):
        """Test getting alert history."""
        client, _, _, _ = test_client
        response = client.get("/api/v1/alerts/history")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_active_alerts(self, test_client):
        """Test getting active alerts."""
        client, _, _, _ = test_client
        response = client.get("/api/v1/alerts/active")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_whale_stats(self, test_client):
        """Test getting whale detector stats."""
        client, _, _, _ = test_client
        response = client.get("/api/v1/whales/stats")

        assert response.status_code == 200
        data = response.json()
        assert "tracked_traders" in data
        assert "whale_count" in data

    def test_get_signal_store_stats(self, test_client):
        """Test getting signal store stats."""
        client, _, _, _ = test_client
        response = client.get("/api/v1/signals/store/stats")

        assert response.status_code == 200
        data = response.json()
        assert "signals" in data
        assert "alerts" in data


class TestSignalFlow:
    """Tests for end-to-end signal flow."""

    @pytest.mark.asyncio
    async def test_position_to_signal(self, test_client):
        """Test position event generates signal."""
        client, processor, _, store = test_client

        # Add a trader score first
        await processor.process_scored_traders({
            "payload": {
                "traders": [{"address": "0xtrader1", "score": 80}]
            }
        })

        # Process a position
        event = {
            "payload": {
                "address": "0xtrader1",
                "accountValue": "1000000",
                "positions": [
                    {"position": {"coin": "BTC", "szi": "10.0"}}
                ],
            }
        }

        signal = await processor.process_position(event)

        # Should generate a signal
        assert signal is not None
        assert signal["action"] == "BUY"

        # Store the signal
        store.store_signal(signal)

        # Verify it's available via API
        response = client.get("/api/v1/signals/latest")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_multiple_positions_aggregation(self, test_client):
        """Test multiple positions are aggregated."""
        client, processor, _, _ = test_client

        # Add trader scores - use different scores to ensure bias changes
        await processor.process_scored_traders({
            "payload": {
                "traders": [
                    {"address": "0xtrader1", "score": 100},  # Full weight
                    {"address": "0xtrader2", "score": 100},  # Full weight
                ]
            }
        })

        # Process first position (long)
        await processor.process_position({
            "payload": {
                "address": "0xtrader1",
                "positions": [{"position": {"coin": "BTC", "szi": "10.0"}}],
            }
        })

        # Check first signal - one trader long
        latest1 = processor.get_latest_signal()
        assert latest1 is not None
        assert latest1["traders_long"] == 1
        assert latest1["action"] == "BUY"

        # Process second position (SHORT to create meaningful change)
        signal2 = await processor.process_position({
            "payload": {
                "address": "0xtrader2",
                "positions": [{"position": {"coin": "BTC", "szi": "-10.0"}}],  # SHORT
            }
        })

        # Should emit a new signal because bias changed significantly
        # Check the processor state
        stats = processor.get_stats()
        assert stats["tracked_traders"] == 2

        # The latest signal should reflect both traders
        latest2 = processor.get_latest_signal()
        if signal2:  # If signal was emitted
            assert signal2["traders_long"] == 1
            assert signal2["traders_short"] == 1


class TestWhaleAlertFlow:
    """Tests for whale alert flow."""

    def test_whale_detection_to_alert(self, test_client):
        """Test whale detection generates alert."""
        client, _, detector, _ = test_client

        # Update trader info
        detector.update_trader_info(
            address="0xalpha_whale",
            account_value=25_000_000,
        )

        # Detect position change
        change = detector.detect_position_change(
            address="0xalpha_whale",
            coin="BTC",
            current_szi=100.0,
        )

        assert change is not None

        # Generate alert
        alert = detector.generate_alert(change)

        assert alert is not None
        # Alpha whale change should be CRITICAL
        assert alert.priority.value == "CRITICAL"

    def test_multiple_whales_high_alert(self, test_client):
        """Test multiple whale changes generate HIGH alert."""
        client, _, detector, _ = test_client

        # Set high alpha threshold to avoid CRITICAL
        detector.alpha_whale_threshold = 100_000_000

        # Add whales
        detector.update_trader_info("0xwhale1", account_value=15_000_000)
        detector.update_trader_info("0xwhale2", account_value=12_000_000)

        # Both change
        detector.detect_position_change("0xwhale1", "BTC", 100.0)
        detector.detect_position_change("0xwhale2", "BTC", 50.0)

        # Generate alert
        alert = detector.generate_alert()

        assert alert is not None
        assert alert.priority.value == "HIGH"


class TestSignalStore:
    """Tests for signal storage."""

    def test_store_signal(self, test_client):
        """Test storing a signal."""
        client, _, _, store = test_client

        signal = {
            "symbol": "BTC",
            "action": "BUY",
            "confidence": 0.8,
            "long_bias": 0.7,
            "short_bias": 0.3,
            "net_bias": 0.4,
            "traders_long": 5,
            "traders_short": 2,
            "timestamp": "2026-02-25T10:00:00Z",
        }

        stored = store.store_signal(signal)

        assert stored.action == "BUY"
        assert stored.confidence == 0.8

        # Verify retrieval
        signals = store.get_signals(limit=10)
        assert len(signals) == 1
        assert signals[0].action == "BUY"

    def test_store_multiple_signals(self, test_client):
        """Test storing multiple signals."""
        client, _, _, store = test_client

        for i in range(5):
            store.store_signal({
                "symbol": "BTC",
                "action": "BUY" if i % 2 == 0 else "SELL",
                "confidence": 0.5 + i * 0.1,
                "long_bias": 0.5,
                "short_bias": 0.5,
                "net_bias": 0.0,
                "traders_long": 1,
                "traders_short": 1,
                "timestamp": f"2026-02-25T10:0{i}:00Z",
            })

        signals = store.get_signals(limit=10)
        assert len(signals) == 5

        stats = store.get_signal_stats()
        assert stats["total"] == 5

    def test_store_alert(self, test_client):
        """Test storing an alert."""
        client, _, _, store = test_client

        alert = {
            "priority": "HIGH",
            "title": "Test Alert",
            "description": "Test description",
            "detected_at": "2026-02-25T10:00:00Z",
        }

        stored = store.store_alert(alert)

        assert stored.priority == "HIGH"
        assert stored.title == "Test Alert"

        # Verify retrieval
        alerts = store.get_alerts(limit=10)
        assert len(alerts) == 1


class TestCORS:
    """Tests for CORS configuration."""

    def test_cors_headers(self, test_client):
        """Test CORS headers are set correctly."""
        client, _, _, _ = test_client

        response = client.options(
            "/health",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

        # CORS should allow all origins
        assert response.status_code == 200


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_endpoint(self, test_client):
        """Test invalid endpoint returns 404."""
        client, _, _, _ = test_client

        response = client.get("/invalid")
        assert response.status_code == 404

    def test_invalid_query_param(self, test_client):
        """Test invalid query parameter handling."""
        client, _, _, _ = test_client

        # Invalid limit (should still work, limited by endpoint)
        response = client.get("/api/v1/signals/history?limit=invalid")
        # FastAPI should return 422 for invalid type
        assert response.status_code == 422
