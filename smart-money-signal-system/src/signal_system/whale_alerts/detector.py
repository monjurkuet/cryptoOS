"""Whale Alert Detector for detecting large position changes."""

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import structlog

from signal_system.utils.safe_convert import safe_datetime

logger = structlog.get_logger(__name__)

# TTL for position history (7 days in seconds)
POSITION_HISTORY_TTL = 604800
# Maximum alerts to keep in memory
MAX_ALERTS = 500
# Maximum recent changes to keep
MAX_RECENT_CHANGES = 1000


class AlertPriority(str, Enum):
    """Alert priority levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class PositionChange:
    """Detected position change."""

    address: str
    trader_name: str | None
    tier: str
    coin: str
    previous_szi: float
    current_szi: float
    change_pct: float
    account_value: float
    detected_at: str


@dataclass
class WhaleAlert:
    """Generated whale alert."""

    priority: AlertPriority
    title: str
    description: str
    changes: list[PositionChange]
    signal_impact: dict[str, float]
    detected_at: str
    expires_at: str


class WhaleAlertDetector:
    """Detects whale position changes and generates alerts.

    Alert Priorities:
    - CRITICAL: Alpha Whale ($20M+) position change
    - HIGH: 2+ whales change within 5 min
    - MEDIUM: Aggregate whale bias flips
    - LOW: Elite consensus shifts 20%+

    Implements TTL-based cleanup to prevent unbounded memory growth.
    """

    def __init__(
        self,
        alpha_whale_threshold: float = 20_000_000,
        whale_threshold: float = 10_000_000,
        aggregation_window_minutes: int = 5,
        position_history_ttl: int = POSITION_HISTORY_TTL,
        max_alerts: int = MAX_ALERTS,
        max_recent_changes: int = MAX_RECENT_CHANGES,
    ) -> None:
        """Initialize the detector.

        Args:
            alpha_whale_threshold: Account value for alpha whale classification
            whale_threshold: Account value for whale classification
            aggregation_window_minutes: Window for aggregating changes
            position_history_ttl: TTL for position history in seconds
            max_alerts: Maximum alerts to keep in memory
            max_recent_changes: Maximum recent changes to keep
        """
        self.alpha_whale_threshold = alpha_whale_threshold
        self.whale_threshold = whale_threshold
        self.aggregation_window = timedelta(minutes=aggregation_window_minutes)
        self.position_history_ttl = position_history_ttl
        self.max_alerts = max_alerts
        self.max_recent_changes = max_recent_changes

        # Position history with TTL: addr -> coin -> (szi, timestamp)
        self._position_history: dict[str, dict[str, tuple[float, float]]] = {}
        # Bounded recent changes
        self._recent_changes: deque[PositionChange] = deque(maxlen=max_recent_changes)
        # Bounded alerts
        self._alerts: deque[WhaleAlert] = deque(maxlen=max_alerts)
        # Trader info (active traders only, cleaned up when whale threshold not met)
        self._trader_info: dict[str, dict[str, Any]] = {}

    def update_trader_info(
        self,
        address: str,
        name: str | None = None,
        tier: str = "standard",
        account_value: float = 0,
    ) -> None:
        """Update trader information.

        Args:
            address: Trader's Ethereum address
            name: Optional trader name
            tier: Trader tier
            account_value: Account value in USD
        """
        self._trader_info[address] = {
            "name": name,
            "tier": tier,
            "account_value": account_value,
        }

    def detect_position_change(
        self,
        address: str,
        coin: str,
        current_szi: float,
    ) -> PositionChange | None:
        """Detect if a position change is significant.

        Args:
            address: Trader's Ethereum address
            coin: Trading pair coin
            current_szi: Current position size

        Returns:
            PositionChange if significant, else None
        """
        trader_info = self._trader_info.get(address, {})
        tier = trader_info.get("tier", "standard")
        account_value = trader_info.get("account_value", 0)

        # Only track whales and above
        if account_value < self.whale_threshold:
            return None

        # Get previous position (now stored as tuple)
        if address not in self._position_history:
            self._position_history[address] = {}

        prev_entry = self._position_history[address].get(coin)
        previous_szi = prev_entry[0] if prev_entry else 0.0

        # Calculate change
        if previous_szi == 0:
            change_pct = 1.0 if current_szi != 0 else 0.0
        else:
            change_pct = abs(current_szi - previous_szi) / abs(previous_szi)

        # Threshold for significance (10% change or new position)
        if change_pct < 0.1 and not (previous_szi == 0 and current_szi != 0):
            # Update history even for small changes (with timestamp)
            self._position_history[address][coin] = (current_szi, time.time())
            return None

        # Create change record
        change = PositionChange(
            address=address,
            trader_name=trader_info.get("name"),
            tier=tier,
            coin=coin,
            previous_szi=previous_szi,
            current_szi=current_szi,
            change_pct=change_pct,
            account_value=account_value,
            detected_at=datetime.now(timezone.utc).isoformat(),
        )

        # Update history (with timestamp)
        self._position_history[address][coin] = (current_szi, time.time())
        self._recent_changes.append(change)

        # Clean old changes and position history
        self._cleanup()

        return change

    def _cleanup(self) -> None:
        """Remove stale data to prevent unbounded memory growth."""
        # Clean old changes (outside aggregation window)
        cutoff = datetime.now(timezone.utc) - self.aggregation_window
        while self._recent_changes:
            c = self._recent_changes[0]
            dt = safe_datetime(c.detected_at)
            if dt and dt > cutoff:
                break
            self._recent_changes.popleft()

        # Clean position history entries older than TTL
        now = time.time()
        cutoff_time = now - self.position_history_ttl

        for address in list(self._position_history.keys()):
            coins = self._position_history[address]
            for coin in list(coins.keys()):
                _, timestamp = coins[coin]
                if timestamp < cutoff_time:
                    del coins[coin]
            # Remove address entry if no coins left
            if not coins:
                del self._position_history[address]

    def _clean_old_changes(self) -> None:
        """Remove changes outside the aggregation window."""
        self._cleanup()

    def generate_alert(self, change: PositionChange | None = None) -> WhaleAlert | None:
        """Generate alert based on detected changes.

        Args:
            change: Optional specific change to process

        Returns:
            WhaleAlert if conditions met, else None
        """
        now = datetime.now(timezone.utc)
        self._clean_old_changes()

        changes_to_process = [change] if change else self._recent_changes
        if not changes_to_process:
            return None

        alert: WhaleAlert | None = None

        # Check for CRITICAL: Alpha Whale position change
        alpha_changes = [
            c for c in changes_to_process
            if c.account_value >= self.alpha_whale_threshold
        ]
        if alpha_changes:
            alert = self._create_critical_alert(alpha_changes)

        # Check for HIGH: 2+ whales in window
        if not alert:
            whale_changes = [
                c for c in changes_to_process
                if c.account_value >= self.whale_threshold
            ]
            if len(whale_changes) >= 2:
                alert = self._create_high_alert(whale_changes)

            # Check for MEDIUM: Aggregate bias flip
            if not alert:
                bias_change = self._calculate_aggregate_bias_change()
                if abs(bias_change) >= 0.3:  # 30% bias flip
                    alert = self._create_medium_alert(whale_changes, bias_change)

            # Check for LOW: Single whale change or smaller consensus shift
            if not alert and whale_changes:
                alert = self._create_low_alert(whale_changes)

        # Store the alert
        if alert:
            self._alerts.append(alert)

        return alert

    def _create_critical_alert(self, changes: list[PositionChange]) -> WhaleAlert:
        """Create CRITICAL priority alert for alpha whale changes."""
        change = changes[0]  # Primary change
        direction = "LONG" if change.current_szi > change.previous_szi else "SHORT"
        if change.previous_szi * change.current_szi < 0:
            direction = "FLIP to " + direction

        return WhaleAlert(
            priority=AlertPriority.CRITICAL,
            title=f"Alpha Whale {direction}",
            description=f"Alpha whale (${change.account_value/1e6:.1f}M) changed {change.coin} position",
            changes=changes,
            signal_impact={"confidence_boost": 0.3, "priority": 1.5},
            detected_at=datetime.now(timezone.utc).isoformat(),
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )

    def _create_high_alert(self, changes: list[PositionChange]) -> WhaleAlert:
        """Create HIGH priority alert for multiple whale changes."""
        long_count = sum(1 for c in changes if c.current_szi > c.previous_szi)
        short_count = len(changes) - long_count
        bias = "bullish" if long_count > short_count else "bearish"

        return WhaleAlert(
            priority=AlertPriority.HIGH,
            title=f"Multiple Whales {bias.upper()}",
            description=f"{len(changes)} whales changed positions in last {self.aggregation_window.seconds // 60} min",
            changes=changes,
            signal_impact={"confidence_boost": 0.2, "priority": 1.3},
            detected_at=datetime.now(timezone.utc).isoformat(),
            expires_at=(datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        )

    def _create_medium_alert(
        self,
        changes: list[PositionChange],
        bias_change: float,
    ) -> WhaleAlert:
        """Create MEDIUM priority alert for aggregate bias flip."""
        direction = "bullish" if bias_change > 0 else "bearish"

        return WhaleAlert(
            priority=AlertPriority.MEDIUM,
            title=f"Whale Bias Flip {direction.upper()}",
            description=f"Aggregate whale bias shifted {abs(bias_change)*100:.0f}% {direction}",
            changes=changes,
            signal_impact={"confidence_boost": 0.15, "priority": 1.1},
            detected_at=datetime.now(timezone.utc).isoformat(),
            expires_at=(datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        )

    def _create_low_alert(self, changes: list[PositionChange]) -> WhaleAlert:
        """Create LOW priority alert for single whale change."""
        change = changes[0]
        direction = "increased" if abs(change.current_szi) > abs(change.previous_szi) else "decreased"

        return WhaleAlert(
            priority=AlertPriority.LOW,
            title=f"Whale {change.coin} {direction.title()}",
            description=f"Whale (${change.account_value/1e6:.1f}M) {direction} {change.coin} position",
            changes=changes,
            signal_impact={"confidence_boost": 0.05, "priority": 1.0},
            detected_at=datetime.now(timezone.utc).isoformat(),
            expires_at=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        )

    def _calculate_aggregate_bias_change(self) -> float:
        """Calculate aggregate change in whale bias.

        Returns:
            Net bias change (-1 to 1)
        """
        if not self._recent_changes:
            return 0.0

        long_delta = 0.0
        short_delta = 0.0

        for change in self._recent_changes:
            delta = change.current_szi - change.previous_szi
            weight = min(change.account_value / self.whale_threshold, 3.0)

            if delta > 0:
                long_delta += weight
            else:
                short_delta += weight

        total = long_delta + short_delta
        if total == 0:
            return 0.0

        return (long_delta - short_delta) / total

    def get_recent_alerts(self, limit: int = 20) -> list[WhaleAlert]:
        """Get recent alerts.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of WhaleAlert
        """
        return list(self._alerts)[-limit:]

    def get_active_alerts(self) -> list[WhaleAlert]:
        """Get alerts that haven't expired.

        Returns:
            List of active WhaleAlert
        """
        now = datetime.now(timezone.utc)
        return [
            a for a in self._alerts
            if safe_datetime(a.expires_at) and safe_datetime(a.expires_at) > now
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get detector statistics.

        Returns:
            Dict with detector stats
        """
        return {
            "tracked_traders": len(self._trader_info),
            "whale_count": sum(
                1 for t in self._trader_info.values()
                if t.get("account_value", 0) >= self.whale_threshold
            ),
            "alpha_whale_count": sum(
                1 for t in self._trader_info.values()
                if t.get("account_value", 0) >= self.alpha_whale_threshold
            ),
            "recent_changes": len(self._recent_changes),
            "total_alerts": len(self._alerts),
            "active_alerts": len(self.get_active_alerts()),
        }
