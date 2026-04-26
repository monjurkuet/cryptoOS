"""Unit tests for SignalOutcomeTracker."""

import pytest
import time

from signal_system.rl.outcome_tracker import SignalOutcomeTracker, SignalOutcome


class TestSignalOutcomeTracker:
    def test_register_signal(self):
        tracker = SignalOutcomeTracker()
        tracker.register_signal("sig1", "BUY", 0.7, 50000.0)
        pending = tracker.get_pending_outcomes()
        assert len(pending) == 1
        assert pending[0].signal_id == "sig1"

    def test_register_signal_generates_id(self):
        tracker = SignalOutcomeTracker()
        sid = tracker.register_signal(None, "BUY", 0.7, 50000.0)
        assert sid is not None
        assert len(sid) > 0

    def test_update_price_resolves_outcomes(self):
        tracker = SignalOutcomeTracker(evaluation_horizons=[60])
        tracker.register_signal("sig1", "BUY", 0.7, 50000.0, timestamp=time.time() - 61)
        outcomes = tracker.update_price(50500.0)
        assert len(outcomes) == 1
        assert outcomes[0].signal_id == "sig1"
        assert outcomes[0].pnl_pct > 0  # BUY + price up = profit

    def test_sell_signal_reward_negative_on_price_up(self):
        tracker = SignalOutcomeTracker(evaluation_horizons=[60])
        tracker.register_signal("sig1", "SELL", 0.7, 50000.0, timestamp=time.time() - 61)
        outcomes = tracker.update_price(50500.0)
        assert outcomes[0].pnl_pct < 0  # SELL + price up = loss

    def test_neutral_signal_zero_reward(self):
        tracker = SignalOutcomeTracker(evaluation_horizons=[60])
        tracker.register_signal("sig1", "NEUTRAL", 0.3, 50000.0, timestamp=time.time() - 61)
        outcomes = tracker.update_price(50500.0)
        assert outcomes[0].pnl_pct == 0.0

    def test_sell_signal_profit_on_price_down(self):
        tracker = SignalOutcomeTracker(evaluation_horizons=[60])
        tracker.register_signal("sig1", "SELL", 0.7, 50000.0, timestamp=time.time() - 61)
        outcomes = tracker.update_price(49500.0)
        assert outcomes[0].pnl_pct > 0  # SELL + price down = profit

    def test_multiple_horizons(self):
        tracker = SignalOutcomeTracker(evaluation_horizons=[60, 300, 900])
        ts = time.time() - 301  # 5+ minutes old
        tracker.register_signal("sig1", "BUY", 0.7, 50000.0, timestamp=ts)
        outcomes = tracker.update_price(50750.0)
        assert len(outcomes) == 2  # resolved at 60s and 300s horizons

    def test_signal_not_resolved_before_horizon(self):
        tracker = SignalOutcomeTracker(evaluation_horizons=[300])
        tracker.register_signal("sig1", "BUY", 0.7, 50000.0, timestamp=time.time() - 10)
        outcomes = tracker.update_price(50500.0)
        assert len(outcomes) == 0

    def test_pending_cleanup(self):
        tracker = SignalOutcomeTracker(max_pending=3)
        for i in range(5):
            tracker.register_signal(f"sig{i}", "BUY", 0.5, 50000.0)
        pending = tracker.get_pending_outcomes()
        assert len(pending) <= 3

    def test_resolved_outcomes_stored(self):
        tracker = SignalOutcomeTracker(evaluation_horizons=[60])
        tracker.register_signal("sig1", "BUY", 0.7, 50000.0, timestamp=time.time() - 61)
        tracker.update_price(50500.0)
        resolved = tracker.get_resolved_outcomes()
        assert len(resolved) == 1
        assert resolved[0].signal_id == "sig1"

    def test_get_stats(self):
        tracker = SignalOutcomeTracker(evaluation_horizons=[60])
        tracker.register_signal("sig1", "BUY", 0.7, 50000.0, timestamp=time.time() - 61)
        tracker.update_price(50500.0)
        stats = tracker.get_stats()
        assert stats["pending_signals"] == 0
        assert stats["resolved_outcomes"] == 1
        assert stats["last_price"] == 50500.0

    def test_zero_entry_price_no_crash(self):
        tracker = SignalOutcomeTracker(evaluation_horizons=[60])
        tracker.register_signal("sig1", "BUY", 0.7, 0.0, timestamp=time.time() - 61)
        outcomes = tracker.update_price(50500.0)
        assert outcomes[0].pnl_pct == 0.0  # guard against div by zero

    def test_fully_resolved_signal_removed_from_pending(self):
        tracker = SignalOutcomeTracker(evaluation_horizons=[60])
        tracker.register_signal("sig1", "BUY", 0.7, 50000.0, timestamp=time.time() - 61)
        tracker.update_price(50500.0)
        pending = tracker.get_pending_outcomes()
        assert len(pending) == 0  # fully resolved, removed
