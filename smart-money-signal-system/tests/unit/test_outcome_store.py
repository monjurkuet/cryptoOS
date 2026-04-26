"""Unit tests for OutcomeStore."""

import pytest
from unittest.mock import MagicMock, patch

from signal_system.rl.outcome_store import OutcomeStore, OutcomeRecord


class TestOutcomeRecord:
    def test_from_outcome(self):
        """OutcomeRecord converts from SignalOutcome."""
        from signal_system.rl.outcome_tracker import SignalOutcome

        outcome = SignalOutcome(
            signal_id="sig1",
            action="BUY",
            confidence=0.8,
            entry_price=50000.0,
            exit_price=51000.0,
            pnl_pct=0.02,
            horizon_seconds=300,
            timestamp=1000.0,
            resolved_at=1300.0,
        )
        record = OutcomeRecord.from_outcome(outcome)
        assert record.signal_id == "sig1"
        assert record.action == "BUY"
        assert record.pnl_pct == 0.02

    def test_to_dict(self):
        """OutcomeRecord serializes to dict."""
        record = OutcomeRecord(
            signal_id="sig2",
            action="SELL",
            confidence=0.6,
            entry_price=50000.0,
            exit_price=49000.0,
            pnl_pct=0.02,
            horizon_seconds=60,
            timestamp=1000.0,
            resolved_at=1060.0,
        )
        d = record.to_dict()
        assert d["signal_id"] == "sig2"
        assert d["action"] == "SELL"
        assert d["pnl_pct"] == 0.02


class TestOutcomeStore:
    def test_store_outcome_no_mongo(self):
        """OutcomeStore works without MongoDB (in-memory only)."""
        store = OutcomeStore(mongo_client=None, database_name="test")
        from signal_system.rl.outcome_tracker import SignalOutcome

        outcome = SignalOutcome(
            signal_id="s1",
            action="BUY",
            confidence=0.8,
            entry_price=100.0,
            exit_price=105.0,
            pnl_pct=0.05,
            horizon_seconds=60,
            timestamp=1000.0,
            resolved_at=1060.0,
        )
        # Should not raise
        store.store_outcome(outcome)
        assert store.get_stats()["stored_count"] == 1

    def test_store_outcome_with_mongo(self):
        """OutcomeStore persists to MongoDB when client provided."""
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection

        store = OutcomeStore(mongo_client=mock_client, database_name="test_db")

        from signal_system.rl.outcome_tracker import SignalOutcome

        outcome = SignalOutcome(
            signal_id="s2",
            action="BUY",
            confidence=0.9,
            entry_price=200.0,
            exit_price=210.0,
            pnl_pct=0.05,
            horizon_seconds=300,
            timestamp=2000.0,
            resolved_at=2300.0,
        )
        store.store_outcome(outcome)

        # Verify insert_one was called
        mock_collection.insert_one.assert_called_once()
        call_args = mock_collection.insert_one.call_args[0][0]
        assert call_args["signal_id"] == "s2"

    def test_store_batch(self):
        """store_batch stores multiple outcomes."""
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection

        store = OutcomeStore(mongo_client=mock_client, database_name="test_db")

        from signal_system.rl.outcome_tracker import SignalOutcome

        outcomes = [
            SignalOutcome("s1", "BUY", 0.8, 100.0, 105.0, 0.05, 60, 1000.0, 1060.0),
            SignalOutcome("s2", "SELL", 0.6, 100.0, 95.0, 0.05, 60, 2000.0, 2060.0),
        ]
        store.store_batch(outcomes)

        mock_collection.insert_many.assert_called_once()
        assert store.get_stats()["stored_count"] == 2

    def test_get_recent_outcomes(self):
        """get_recent_outcomes queries MongoDB."""
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection
        mock_collection.find.return_value.sort.return_value.limit.return_value = [
            {"signal_id": "s1", "action": "BUY", "pnl_pct": 0.05},
        ]

        store = OutcomeStore(mongo_client=mock_client, database_name="test_db")
        results = store.get_recent_outcomes(limit=10)
        assert len(results) == 1

    def test_get_recent_outcomes_no_mongo(self):
        """get_recent_outcomes returns empty list without MongoDB."""
        store = OutcomeStore(mongo_client=None, database_name="test")
        results = store.get_recent_outcomes(limit=10)
        assert results == []

    def test_get_stats(self):
        """get_stats returns correct structure."""
        store = OutcomeStore(mongo_client=None, database_name="test")
        stats = store.get_stats()
        assert "stored_count" in stats
        assert "mongo_enabled" in stats
        assert stats["mongo_enabled"] is False

    def test_close_no_mongo(self):
        """close() is safe without MongoDB."""
        store = OutcomeStore(mongo_client=None, database_name="test")
        store.close()  # Should not raise

    def test_close_with_mongo(self):
        """close() closes MongoDB client."""
        mock_client = MagicMock()
        store = OutcomeStore(mongo_client=mock_client, database_name="test")
        store.close()
        mock_client.close.assert_called_once()
