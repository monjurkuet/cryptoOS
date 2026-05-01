"""Signal Store for persisting signals and alerts."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

SIGNALS_COLLECTION = "signal_system_signals"
ALERTS_COLLECTION = "signal_system_alerts"


@dataclass
class StoredSignal:
    """A stored trading signal."""

    symbol: str
    action: str
    confidence: float
    long_bias: float
    short_bias: float
    net_bias: float
    traders_long: int
    traders_short: int
    timestamp: str
    stored_at: str


@dataclass
class StoredAlert:
    """A stored whale alert."""

    priority: str
    title: str
    description: str
    detected_at: str
    stored_at: str


class SignalStore:
    """In-memory + Mongo-backed signal and alert store."""

    def __init__(
        self,
        max_signals: int = 1000,
        max_alerts: int = 500,
        mongo_client: Any | None = None,
        database_name: str = "signal_system",
        retention_days: int = 30,
    ) -> None:
        self.max_signals = max_signals
        self.max_alerts = max_alerts
        self._retention_days = max(1, retention_days)
        self._signals: deque[StoredSignal] = deque(maxlen=max_signals)
        self._alerts: deque[StoredAlert] = deque(maxlen=max_alerts)

        self._signals_collection = None
        self._alerts_collection = None
        if mongo_client is not None:
            db = mongo_client[database_name]
            self._signals_collection = db[SIGNALS_COLLECTION]
            self._alerts_collection = db[ALERTS_COLLECTION]
            try:
                self._signals_collection.create_index("stored_at_ts")
                self._signals_collection.create_index("symbol")
                self._signals_collection.create_index("action")
                self._signals_collection.create_index("expire_at", expireAfterSeconds=0)
                self._alerts_collection.create_index("stored_at_ts")
                self._alerts_collection.create_index("priority")
                self._alerts_collection.create_index("expire_at", expireAfterSeconds=0)
            except Exception as error:
                logger.warning("signal_store_index_creation_failed", error=str(error))

    def store_signal(self, signal: dict[str, Any]) -> StoredSignal:
        """Store a trading signal."""
        stored = StoredSignal(
            symbol=signal.get("symbol", "BTC"),
            action=signal.get("action", "NEUTRAL"),
            confidence=signal.get("confidence", 0.0),
            long_bias=signal.get("long_bias", 0.0),
            short_bias=signal.get("short_bias", 0.0),
            net_bias=signal.get("net_bias", 0.0),
            traders_long=signal.get("traders_long", 0),
            traders_short=signal.get("traders_short", 0),
            timestamp=signal.get("timestamp", ""),
            stored_at=datetime.now(UTC).isoformat(),
        )
        self._signals.append(stored)
        self._persist_signal(stored)
        logger.debug("signal_stored", action=stored.action)
        return stored

    def store_alert(self, alert: dict[str, Any]) -> StoredAlert:
        """Store a whale alert."""
        stored = StoredAlert(
            priority=alert.get("priority", "LOW"),
            title=alert.get("title", ""),
            description=alert.get("description", ""),
            detected_at=alert.get("detected_at", ""),
            stored_at=datetime.now(UTC).isoformat(),
        )
        self._alerts.append(stored)
        self._persist_alert(stored)
        logger.debug("alert_stored", priority=stored.priority)
        return stored

    def _persist_signal(self, stored: StoredSignal) -> None:
        if self._signals_collection is None:
            return
        try:
            stored_dt = datetime.now(UTC)
            self._signals_collection.insert_one(
                {
                    "source": "signal_system",
                    "symbol": stored.symbol,
                    "action": stored.action,
                    "confidence": float(stored.confidence),
                    "long_bias": float(stored.long_bias),
                    "short_bias": float(stored.short_bias),
                    "net_bias": float(stored.net_bias),
                    "traders_long": int(stored.traders_long),
                    "traders_short": int(stored.traders_short),
                    "timestamp": stored.timestamp,
                    "stored_at": stored.stored_at,
                    "stored_at_ts": stored_dt.timestamp(),
                    "expire_at": stored_dt + timedelta(days=self._retention_days),
                }
            )
        except Exception as error:
            logger.error("signal_store_mongo_error", error=str(error))

    def _persist_alert(self, stored: StoredAlert) -> None:
        if self._alerts_collection is None:
            return
        try:
            stored_dt = datetime.now(UTC)
            self._alerts_collection.insert_one(
                {
                    "priority": stored.priority,
                    "title": stored.title,
                    "description": stored.description,
                    "detected_at": stored.detected_at,
                    "stored_at": stored.stored_at,
                    "stored_at_ts": stored_dt.timestamp(),
                    "expire_at": stored_dt + timedelta(days=self._retention_days),
                }
            )
        except Exception as error:
            logger.error("alert_store_mongo_error", error=str(error))

    def _signal_from_doc(self, doc: dict[str, Any]) -> StoredSignal:
        return StoredSignal(
            symbol=doc.get("symbol", "BTC"),
            action=doc.get("action", "NEUTRAL"),
            confidence=float(doc.get("confidence", 0.0)),
            long_bias=float(doc.get("long_bias", 0.0)),
            short_bias=float(doc.get("short_bias", 0.0)),
            net_bias=float(doc.get("net_bias", 0.0)),
            traders_long=int(doc.get("traders_long", 0)),
            traders_short=int(doc.get("traders_short", 0)),
            timestamp=str(doc.get("timestamp", "")),
            stored_at=str(doc.get("stored_at", "")),
        )

    def _in_memory_signals(self, limit: int) -> list[StoredSignal]:
        if limit <= 0:
            return []
        return list(self._signals)[-limit:][::-1]

    def _signal_in_window(
        self,
        signal: StoredSignal,
        from_ts: float | None,
        to_ts: float | None,
    ) -> bool:
        try:
            ts = datetime.fromisoformat(signal.stored_at.replace("Z", "+00:00")).timestamp()
        except Exception:
            return False
        if from_ts is not None and ts < from_ts:
            return False
        if to_ts is not None and ts > to_ts:
            return False
        return True

    def _signal_to_dashboard_row(self, signal: StoredSignal) -> dict[str, Any]:
        ts = 0.0
        try:
            ts = datetime.fromisoformat(signal.stored_at.replace("Z", "+00:00")).timestamp()
        except Exception:
            pass
        return {
            "source": "signal_system",
            "timestamp": signal.timestamp,
            "timestamp_ts": ts,
            "action": signal.action,
            "confidence": float(signal.confidence),
            "long_bias": float(signal.long_bias),
            "short_bias": float(signal.short_bias),
            "net_bias": float(signal.net_bias),
            "traders_long": int(signal.traders_long),
            "traders_short": int(signal.traders_short),
        }

    def get_latest_signal(self) -> StoredSignal | None:
        """Get the most recent signal."""
        if self._signals_collection is not None:
            try:
                doc = self._signals_collection.find_one(sort=[("stored_at_ts", -1)])
                if doc:
                    return self._signal_from_doc(doc)
            except Exception as error:
                logger.warning("signal_store_mongo_read_failed", error=str(error))
        if self._signals:
            return self._signals[-1]
        return None

    def get_signals(self, limit: int = 100) -> list[StoredSignal]:
        """Get recent signals."""
        if self._signals_collection is not None:
            try:
                docs = list(self._signals_collection.find({}).sort("stored_at_ts", -1).limit(limit))
                return [self._signal_from_doc(doc) for doc in docs]
            except Exception as error:
                logger.warning("signal_store_mongo_read_failed", error=str(error))
        return self._in_memory_signals(limit)

    def get_signals_in_window(
        self,
        from_ts: float | None = None,
        to_ts: float | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Get normalized signal rows from Mongo for dashboard timeline."""
        if self._signals_collection is not None:
            query: dict[str, Any] = {}
            if from_ts is not None or to_ts is not None:
                query["stored_at_ts"] = {}
                if from_ts is not None:
                    query["stored_at_ts"]["$gte"] = from_ts
                if to_ts is not None:
                    query["stored_at_ts"]["$lte"] = to_ts
            try:
                docs = list(self._signals_collection.find(query).sort("stored_at_ts", -1).limit(limit))
                rows: list[dict[str, Any]] = []
                for doc in docs:
                    doc.pop("_id", None)
                    doc.pop("expire_at", None)
                    rows.append(
                        {
                            "source": "signal_system",
                            "timestamp": doc.get("timestamp", ""),
                            "timestamp_ts": doc.get("stored_at_ts", 0.0),
                            "action": doc.get("action", "NEUTRAL"),
                            "confidence": float(doc.get("confidence", 0.0)),
                            "long_bias": float(doc.get("long_bias", 0.0)),
                            "short_bias": float(doc.get("short_bias", 0.0)),
                            "net_bias": float(doc.get("net_bias", 0.0)),
                            "traders_long": int(doc.get("traders_long", 0)),
                            "traders_short": int(doc.get("traders_short", 0)),
                        }
                    )
                return rows
            except Exception as error:
                logger.warning("signal_store_mongo_read_failed", error=str(error))

        memory_rows = [
            self._signal_to_dashboard_row(signal)
            for signal in self._in_memory_signals(self.max_signals)
            if self._signal_in_window(signal, from_ts=from_ts, to_ts=to_ts)
        ]
        return memory_rows[:max(0, limit)]

    def get_alerts(self, limit: int = 50) -> list[StoredAlert]:
        """Get recent alerts."""
        return list(self._alerts)[-limit:]

    def get_signal_stats(self) -> dict[str, Any]:
        """Get signal statistics."""
        signals = self.get_signals(limit=self.max_signals)
        if not signals:
            return {"total": 0, "mongo_enabled": self._signals_collection is not None}

        actions: dict[str, int] = {}
        for signal in signals:
            actions[signal.action] = actions.get(signal.action, 0) + 1

        avg_confidence = sum(s.confidence for s in signals) / len(signals)

        return {
            "total": len(signals),
            "action_distribution": actions,
            "avg_confidence": round(avg_confidence, 4),
            "latest_action": signals[0].action if signals else None,
            "mongo_enabled": self._signals_collection is not None,
        }

    def get_alert_stats(self) -> dict[str, Any]:
        """Get alert statistics."""
        alerts = list(self._alerts)
        if not alerts:
            return {"total": 0, "mongo_enabled": self._alerts_collection is not None}

        priorities: dict[str, int] = {}
        for alert in alerts:
            priorities[alert.priority] = priorities.get(alert.priority, 0) + 1

        return {
            "total": len(alerts),
            "priority_distribution": priorities,
            "mongo_enabled": self._alerts_collection is not None,
        }

    def clear(self) -> None:
        """Clear in-memory data."""
        self._signals.clear()
        self._alerts.clear()
        logger.info("store_cleared")
