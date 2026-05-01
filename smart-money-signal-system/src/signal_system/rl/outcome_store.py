"""Persist signal outcomes to MongoDB for RL training data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from signal_system.rl.outcome_tracker import SignalOutcome

logger = structlog.get_logger(__name__)

COLLECTION_NAME = "rl_outcomes"


@dataclass
class OutcomeRecord:
    """Serializable representation of a signal outcome."""

    signal_id: str
    action: str
    confidence: float
    entry_price: float
    exit_price: float
    pnl_pct: float
    horizon_seconds: int
    timestamp: float
    resolved_at: float

    @classmethod
    def from_outcome(cls, outcome: SignalOutcome) -> OutcomeRecord:
        """Create from a SignalOutcome."""
        return cls(
            signal_id=outcome.signal_id,
            action=outcome.action,
            confidence=outcome.confidence,
            entry_price=outcome.entry_price,
            exit_price=outcome.exit_price,
            pnl_pct=outcome.pnl_pct,
            horizon_seconds=outcome.horizon_seconds,
            timestamp=outcome.timestamp,
            resolved_at=outcome.resolved_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to MongoDB-compatible dict."""
        return {
            "signal_id": self.signal_id,
            "action": self.action,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl_pct": self.pnl_pct,
            "horizon_seconds": self.horizon_seconds,
            "timestamp": self.timestamp,
            "resolved_at": self.resolved_at,
        }


class OutcomeStore:
    """Persists signal outcomes to MongoDB for offline RL training.

    Falls back to in-memory counting when no MongoDB client is provided,
    allowing the system to run without a database for testing/development.
    """

    def __init__(
        self,
        mongo_client: Any | None = None,
        database_name: str = "signal_system",
    ) -> None:
        self._client = mongo_client
        self._db_name = database_name
        self._stored_count = 0

        if self._client is not None:
            self._db = self._client[database_name]
            self._collection = self._db[COLLECTION_NAME]
            # Create indexes for common queries
            try:
                self._collection.create_index("signal_id")
                self._collection.create_index("resolved_at")
            except Exception as e:
                logger.warning("outcome_store_index_creation_failed", error=str(e))

            # TTL index - auto-expire outcomes after 90 days
            try:
                self._collection.create_index(
                    [("resolved_at", 1)],
                    name="ttl_retention",
                    expireAfterSeconds=90 * 86400,
                )
            except Exception as e:
                logger.warning("outcome_store_ttl_index_failed", error=str(e))
        else:
            self._collection = None
            logger.info("outcome_store_running_in_memory")

    def store_outcome(self, outcome: SignalOutcome) -> None:
        """Persist a single signal outcome.

        Args:
            outcome: Resolved signal outcome to store
        """
        record = OutcomeRecord.from_outcome(outcome)
        self._stored_count += 1

        if self._collection is not None:
            try:
                self._collection.insert_one(record.to_dict())
                logger.debug(
                    "outcome_stored_mongo",
                    signal_id=record.signal_id,
                    pnl_pct=record.pnl_pct,
                )
            except Exception as e:
                logger.error("outcome_store_mongo_error", error=str(e))
        else:
            logger.debug(
                "outcome_stored_in_memory",
                signal_id=record.signal_id,
            )

    def store_batch(self, outcomes: list[SignalOutcome]) -> None:
        """Persist multiple signal outcomes at once.

        Args:
            outcomes: List of resolved signal outcomes
        """
        if not outcomes:
            return

        records = [OutcomeRecord.from_outcome(o).to_dict() for o in outcomes]
        self._stored_count += len(records)

        if self._collection is not None:
            try:
                self._collection.insert_many(records)
                logger.info(
                    "outcomes_batch_stored",
                    count=len(records),
                )
            except Exception as e:
                logger.error("outcome_batch_store_mongo_error", error=str(e))
        else:
            logger.debug("outcomes_batch_stored_in_memory", count=len(records))

    def get_recent_outcomes(
        self, limit: int = 1000, horizon_seconds: int | None = None
    ) -> list[dict[str, Any]]:
        """Query recent outcomes from MongoDB.

        Args:
            limit: Maximum number of outcomes to return
            horizon_seconds: Filter by specific evaluation horizon

        Returns:
            List of outcome dicts, or empty list if no MongoDB
        """
        if self._collection is None:
            return []

        query: dict[str, Any] = {}
        if horizon_seconds is not None:
            query["horizon_seconds"] = horizon_seconds

        try:
            cursor = (
                self._collection.find(query)
                .sort("resolved_at", -1)
                .limit(limit)
            )
            return list(cursor)
        except Exception as e:
            logger.error("outcome_query_error", error=str(e))
            return []

    def get_outcome_count(self) -> int:
        """Get total number of stored outcomes in MongoDB.

        Returns:
            Count of documents, or in-memory count if no MongoDB
        """
        if self._collection is not None:
            try:
                return self._collection.count_documents({})
            except Exception:
                return self._stored_count
        return self._stored_count

    def get_stats(self) -> dict[str, Any]:
        """Get outcome store statistics.

        Returns:
            Dict with store stats
        """
        return {
            "stored_count": self._stored_count,
            "mongo_enabled": self._collection is not None,
            "mongo_db_count": self.get_outcome_count() if self._collection else 0,
        }

    def close(self) -> None:
        """Close MongoDB client if available."""
        if self._client is not None:
            try:
                self._client.close()
                logger.info("outcome_store_mongo_closed")
            except Exception as e:
                logger.warning("outcome_store_close_error", error=str(e))
