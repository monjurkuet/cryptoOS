"""Unit tests for dashboard normalization and stores."""

from datetime import UTC, datetime

from signal_system.dashboard.store import (
    normalize_market_scraper_signal,
    normalize_signal_system_signal,
)


def test_normalize_signal_system_signal():
    row = {
        "timestamp": "2026-04-26T12:00:00+00:00",
        "action": "BUY",
        "confidence": 0.9,
        "long_bias": 0.7,
        "short_bias": 0.3,
        "net_bias": 0.4,
        "traders_long": 12,
        "traders_short": 4,
    }
    normalized = normalize_signal_system_signal(row)
    assert normalized["source"] == "signal_system"
    assert normalized["action"] == "BUY"
    assert normalized["net_bias"] == 0.4
    assert normalized["timestamp_ts"] > 0


def test_normalize_market_scraper_signal():
    row = {
        "t": datetime(2026, 4, 26, 12, 0, tzinfo=UTC),
        "rec": "SELL",
        "conf": 0.67,
        "long_bias": 0.2,
        "short_bias": 0.8,
        "net_exp": -0.6,
        "t_long": 3,
        "t_short": 9,
    }
    normalized = normalize_market_scraper_signal(row)
    assert normalized["source"] == "market_scraper"
    assert normalized["action"] == "SELL"
    assert normalized["net_bias"] == -0.6
    assert normalized["traders_long"] == 3
    assert normalized["traders_short"] == 9
