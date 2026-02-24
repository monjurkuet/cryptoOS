"""Signal Store for persisting signals and alerts."""

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


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
    """In-memory store for signals and alerts.

    Maintains a rolling window of recent signals and alerts
    for API retrieval and analysis.
    """

    def __init__(self, max_signals: int = 1000, max_alerts: int = 500) -> None:
        """Initialize the store.

        Args:
            max_signals: Maximum signals to retain
            max_alerts: Maximum alerts to retain
        """
        self.max_signals = max_signals
        self.max_alerts = max_alerts
        self._signals: deque[StoredSignal] = deque(maxlen=max_signals)
        self._alerts: deque[StoredAlert] = deque(maxlen=max_alerts)

    def store_signal(self, signal: dict[str, Any]) -> StoredSignal:
        """Store a trading signal.

        Args:
            signal: Signal dict from processor

        Returns:
            StoredSignal object
        """
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
            stored_at=datetime.now(timezone.utc).isoformat(),
        )
        self._signals.append(stored)
        logger.debug("signal_stored", action=stored.action)
        return stored

    def store_alert(self, alert: dict[str, Any]) -> StoredAlert:
        """Store a whale alert.

        Args:
            alert: Alert dict from detector

        Returns:
            StoredAlert object
        """
        stored = StoredAlert(
            priority=alert.get("priority", "LOW"),
            title=alert.get("title", ""),
            description=alert.get("description", ""),
            detected_at=alert.get("detected_at", ""),
            stored_at=datetime.now(timezone.utc).isoformat(),
        )
        self._alerts.append(stored)
        logger.debug("alert_stored", priority=stored.priority)
        return stored

    def get_latest_signal(self) -> StoredSignal | None:
        """Get the most recent signal.

        Returns:
            Latest StoredSignal or None
        """
        if self._signals:
            return self._signals[-1]
        return None

    def get_signals(self, limit: int = 100) -> list[StoredSignal]:
        """Get recent signals.

        Args:
            limit: Maximum signals to return

        Returns:
            List of StoredSignal objects
        """
        return list(self._signals)[-limit:]

    def get_alerts(self, limit: int = 50) -> list[StoredAlert]:
        """Get recent alerts.

        Args:
            limit: Maximum alerts to return

        Returns:
            List of StoredAlert objects
        """
        return list(self._alerts)[-limit:]

    def get_signal_stats(self) -> dict[str, Any]:
        """Get signal statistics.

        Returns:
            Dict with signal statistics
        """
        signals = list(self._signals)
        if not signals:
            return {"total": 0}

        actions = {}
        for s in signals:
            actions[s.action] = actions.get(s.action, 0) + 1

        avg_confidence = sum(s.confidence for s in signals) / len(signals)

        return {
            "total": len(signals),
            "action_distribution": actions,
            "avg_confidence": round(avg_confidence, 4),
            "latest_action": signals[-1].action if signals else None,
        }

    def get_alert_stats(self) -> dict[str, Any]:
        """Get alert statistics.

        Returns:
            Dict with alert statistics
        """
        alerts = list(self._alerts)
        if not alerts:
            return {"total": 0}

        priorities = {}
        for a in alerts:
            priorities[a.priority] = priorities.get(a.priority, 0) + 1

        return {
            "total": len(alerts),
            "priority_distribution": priorities,
        }

    def clear(self) -> None:
        """Clear all stored data."""
        self._signals.clear()
        self._alerts.clear()
        logger.info("store_cleared")
