"""Unit tests for SignalStore."""

from unittest.mock import MagicMock

from signal_system.signal_store import SignalStore


def _sample_signal(action: str = "BUY") -> dict[str, object]:
    return {
        "symbol": "BTC",
        "action": action,
        "confidence": 0.8,
        "long_bias": 0.7,
        "short_bias": 0.3,
        "net_bias": 0.4,
        "traders_long": 5,
        "traders_short": 2,
        "timestamp": "2026-04-27T00:00:00Z",
    }


def test_get_latest_signal_falls_back_when_mongo_read_fails():
    store = SignalStore(mongo_client=None)
    stored = store.store_signal(_sample_signal())

    failing_collection = MagicMock()
    failing_collection.find_one.side_effect = RuntimeError("mongo unavailable")
    store._signals_collection = failing_collection

    latest = store.get_latest_signal()
    assert latest is not None
    assert latest.action == stored.action


def test_get_signals_falls_back_when_mongo_read_fails():
    store = SignalStore(mongo_client=None)
    store.store_signal(_sample_signal("BUY"))
    store.store_signal(_sample_signal("SELL"))

    failing_collection = MagicMock()
    failing_collection.find.side_effect = RuntimeError("mongo unavailable")
    store._signals_collection = failing_collection

    signals = store.get_signals(limit=10)
    assert len(signals) == 2
    assert signals[0].action == "SELL"
    assert signals[1].action == "BUY"


def test_get_signals_in_window_falls_back_when_mongo_read_fails():
    store = SignalStore(mongo_client=None)
    store.store_signal(_sample_signal())

    failing_collection = MagicMock()
    failing_collection.find.side_effect = RuntimeError("mongo unavailable")
    store._signals_collection = failing_collection

    rows = store.get_signals_in_window(limit=10)
    assert len(rows) == 1
    assert rows[0]["source"] == "signal_system"
    assert rows[0]["action"] == "BUY"
