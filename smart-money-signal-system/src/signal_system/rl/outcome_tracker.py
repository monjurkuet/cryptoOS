"""Track signal outcomes for reward computation."""

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Default horizons: 1min, 5min, 15min, 1h
DEFAULT_HORIZONS = [60, 300, 900, 3600]


@dataclass
class SignalOutcome:
    """Outcome of a signal after evaluation."""

    signal_id: str
    action: str
    confidence: float
    entry_price: float
    exit_price: float
    pnl_pct: float
    horizon_seconds: int
    timestamp: float
    resolved_at: float


@dataclass
class PendingSignal:
    """A signal awaiting outcome evaluation."""

    signal_id: str
    action: str
    confidence: float
    entry_price: float
    timestamp: float
    resolved_horizons: set[int] = field(default_factory=set)


class SignalOutcomeTracker:
    """Tracks price movement after signals to compute reward.

    Registers signals with entry prices, then resolves them as price
    updates arrive and evaluation horizons expire.
    """

    def __init__(
        self,
        evaluation_horizons: list[int] | None = None,
        max_pending: int = 10000,
        max_outcomes: int = 50000,
    ) -> None:
        self._horizons = sorted(evaluation_horizons or DEFAULT_HORIZONS)
        self._max_pending = max_pending
        self._pending: deque[PendingSignal] = deque(maxlen=max_pending)
        self._outcomes: deque[SignalOutcome] = deque(maxlen=max_outcomes)
        self._last_price: float | None = None

    def register_signal(
        self,
        signal_id: str | None,
        action: str,
        confidence: float,
        price: float,
        timestamp: float | None = None,
    ) -> str:
        sid = signal_id or str(uuid.uuid4())[:8]
        ts = timestamp or time.time()
        self._pending.append(PendingSignal(
            signal_id=sid,
            action=action,
            confidence=confidence,
            entry_price=price,
            timestamp=ts,
        ))
        logger.debug("signal_registered_for_tracking", signal_id=sid, action=action)
        return sid

    def update_price(self, price: float) -> list[SignalOutcome]:
        now = time.time()
        self._last_price = price
        resolved: list[SignalOutcome] = []

        for pending in list(self._pending):
            elapsed = now - pending.timestamp
            for horizon in self._horizons:
                if horizon in pending.resolved_horizons:
                    continue
                if elapsed >= horizon:
                    pnl = self._compute_pnl(pending.action, pending.entry_price, price)
                    outcome = SignalOutcome(
                        signal_id=pending.signal_id,
                        action=pending.action,
                        confidence=pending.confidence,
                        entry_price=pending.entry_price,
                        exit_price=price,
                        pnl_pct=pnl,
                        horizon_seconds=horizon,
                        timestamp=pending.timestamp,
                        resolved_at=now,
                    )
                    resolved.append(outcome)
                    self._outcomes.append(outcome)
                    pending.resolved_horizons.add(horizon)

        # Remove fully resolved signals
        self._pending = deque(
            [p for p in self._pending if len(p.resolved_horizons) < len(self._horizons)],
            maxlen=self._max_pending,
        )

        if resolved:
            logger.debug("outcomes_resolved", count=len(resolved))

        return resolved

    def _compute_pnl(self, action: str, entry: float, exit_price: float) -> float:
        if action == "NEUTRAL" or entry == 0:
            return 0.0
        price_change = (exit_price - entry) / entry
        return price_change if action == "BUY" else -price_change

    def get_pending_outcomes(self) -> list[PendingSignal]:
        return list(self._pending)

    def get_resolved_outcomes(self, limit: int = 1000) -> list[SignalOutcome]:
        return list(self._outcomes)[-limit:]

    def get_stats(self) -> dict[str, Any]:
        outcomes = list(self._outcomes)
        return {
            "evaluation_horizons": list(self._horizons),
            "pending_signals": len(self._pending),
            "resolved_outcomes": len(outcomes),
            "avg_pnl": sum(o.pnl_pct for o in outcomes) / len(outcomes) if outcomes else 0,
            "last_price": self._last_price,
        }

    def set_runtime_config(
        self,
        evaluation_horizons: list[int],
        max_pending: int,
        max_outcomes: int,
    ) -> None:
        """Apply runtime settings without losing currently tracked data."""
        self._horizons = sorted({int(h) for h in evaluation_horizons if int(h) > 0})
        self._max_pending = max(100, max_pending)
        self._pending = deque(self._pending, maxlen=self._max_pending)
        self._outcomes = deque(self._outcomes, maxlen=max(100, max_outcomes))
