"""Mongo-backed stores and normalization for dashboard endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

TRACE_COLLECTION = "signal_generator_traces"
PARAM_EVENTS_COLLECTION = "signal_generator_param_events"


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed
    except Exception:
        return None


def normalize_signal_system_signal(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize signal-system signal rows for dashboard timelines."""
    timestamp = row.get("timestamp")
    dt = _parse_iso_timestamp(timestamp)
    return {
        "source": "signal_system",
        "timestamp": timestamp,
        "timestamp_ts": dt.timestamp() if dt else 0.0,
        "action": row.get("action", "NEUTRAL"),
        "confidence": float(row.get("confidence", 0.0)),
        "long_bias": float(row.get("long_bias", 0.0)),
        "short_bias": float(row.get("short_bias", 0.0)),
        "net_bias": float(row.get("net_bias", 0.0)),
        "traders_long": int(row.get("traders_long", 0)),
        "traders_short": int(row.get("traders_short", 0)),
    }


def normalize_market_scraper_signal(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize market-scraper signal rows for dashboard timelines."""
    timestamp = row.get("t")
    ts_iso = timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp or "")
    return {
        "source": "market_scraper",
        "timestamp": ts_iso,
        "timestamp_ts": timestamp.timestamp() if isinstance(timestamp, datetime) else 0.0,
        "action": row.get("rec", "NEUTRAL"),
        "confidence": float(row.get("conf", 0.0)),
        "long_bias": float(row.get("long_bias", 0.0)),
        "short_bias": float(row.get("short_bias", 0.0)),
        "net_bias": float(row.get("net_exp", 0.0)),
        "traders_long": int(row.get("t_long", 0)),
        "traders_short": int(row.get("t_short", 0)),
    }


class DecisionTraceStore:
    """Persists signal decision traces to MongoDB."""

    def __init__(
        self,
        mongo_client: Any | None = None,
        database_name: str = "signal_system",
        retention_days: int = 30,
    ) -> None:
        self._client = mongo_client
        self._collection = None
        self._retention_days = max(1, retention_days)
        self._stored_count = 0

        if self._client is not None:
            db = self._client[database_name]
            self._collection = db[TRACE_COLLECTION]
            try:
                self._collection.create_index("timestamp_ts")
                self._collection.create_index("result")
                self._collection.create_index("reason_code")
                self._collection.create_index("expire_at", expireAfterSeconds=0)
            except Exception as error:
                logger.warning("decision_trace_index_creation_failed", error=str(error))

    def store_trace(self, trace: dict[str, Any]) -> None:
        self._stored_count += 1
        doc = dict(trace)
        doc["expire_at"] = datetime.now(UTC) + timedelta(days=self._retention_days)
        if self._collection is None:
            return
        try:
            self._collection.insert_one(doc)
        except Exception as error:
            logger.error("decision_trace_store_error", error=str(error))

    def get_traces(
        self,
        from_ts: float | None = None,
        to_ts: float | None = None,
        limit: int = 200,
        result: str | None = None,
    ) -> list[dict[str, Any]]:
        if self._collection is None:
            return []
        query: dict[str, Any] = {}
        if from_ts is not None or to_ts is not None:
            query["timestamp_ts"] = {}
            if from_ts is not None:
                query["timestamp_ts"]["$gte"] = from_ts
            if to_ts is not None:
                query["timestamp_ts"]["$lte"] = to_ts
        if result:
            query["result"] = result
        cursor = self._collection.find(query).sort("timestamp_ts", -1).limit(limit)
        rows = list(cursor)
        for row in rows:
            row.pop("_id", None)
            row.pop("expire_at", None)
        return rows

    def get_stats(self) -> dict[str, Any]:
        if self._collection is None:
            return {"mongo_enabled": False, "stored_count": self._stored_count}
        try:
            count = self._collection.count_documents({})
        except Exception:
            count = self._stored_count
        return {"mongo_enabled": True, "stored_count": self._stored_count, "mongo_count": count}


class ParamEventStore:
    """Persists runtime parameter update history."""

    def __init__(
        self,
        mongo_client: Any | None = None,
        database_name: str = "signal_system",
        retention_days: int = 30,
    ) -> None:
        self._client = mongo_client
        self._collection = None
        self._retention_days = max(1, retention_days)
        self._stored_count = 0

        if self._client is not None:
            db = self._client[database_name]
            self._collection = db[PARAM_EVENTS_COLLECTION]
            try:
                self._collection.create_index("timestamp_ts")
                self._collection.create_index("source")
                self._collection.create_index("expire_at", expireAfterSeconds=0)
            except Exception as error:
                logger.warning("param_event_index_creation_failed", error=str(error))

    def store_event(self, params: dict[str, float], source: str) -> None:
        now = datetime.now(UTC)
        self._stored_count += 1
        doc = {
            "source": source,
            "params": dict(params),
            "timestamp": now.isoformat(),
            "timestamp_ts": now.timestamp(),
            "expire_at": now + timedelta(days=self._retention_days),
        }
        if self._collection is None:
            return
        try:
            self._collection.insert_one(doc)
        except Exception as error:
            logger.error("param_event_store_error", error=str(error))

    def get_events(
        self,
        from_ts: float | None = None,
        to_ts: float | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        if self._collection is None:
            return []
        query: dict[str, Any] = {}
        if from_ts is not None or to_ts is not None:
            query["timestamp_ts"] = {}
            if from_ts is not None:
                query["timestamp_ts"]["$gte"] = from_ts
            if to_ts is not None:
                query["timestamp_ts"]["$lte"] = to_ts
        cursor = self._collection.find(query).sort("timestamp_ts", -1).limit(limit)
        rows = list(cursor)
        for row in rows:
            row.pop("_id", None)
            row.pop("expire_at", None)
        return rows

    def get_stats(self) -> dict[str, Any]:
        if self._collection is None:
            return {"mongo_enabled": False, "stored_count": self._stored_count}
        try:
            count = self._collection.count_documents({})
        except Exception:
            count = self._stored_count
        return {"mongo_enabled": True, "stored_count": self._stored_count, "mongo_count": count}
