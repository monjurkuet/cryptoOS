"""
Trader Tracking Models.

This module defines Pydantic models for trader tracking collections.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from src.models.base import BaseDocument, TimestampMixin


# =============================================================================
# Performance Models
# =============================================================================


class WindowPerformance(BaseModel):
    """Trader performance for a specific time window."""

    pnl: float = Field(description="Profit/Loss in USD")
    roi: float = Field(description="Return on Investment (decimal)")
    vlm: float = Field(description="Trading volume in USD")


class TraderPerformances(BaseModel):
    """Trader performances across all time windows."""

    day: WindowPerformance = Field(description="24h performance")
    week: WindowPerformance = Field(description="7-day performance")
    month: WindowPerformance = Field(description="30-day performance")
    all_time: WindowPerformance = Field(alias="allTime", description="All-time performance")


# =============================================================================
# Tracked Trader Models
# =============================================================================


class TrackedTrader(BaseDocument, TimestampMixin):
    """
    Tracked Trader (configuration collection, upserted by ethAddress).

    Stores information about traders we're monitoring.
    """

    eth_address: str = Field(alias="ethAddress", description="Trader's Ethereum address")
    display_name: Optional[str] = Field(
        default=None, alias="displayName", description="Display name"
    )
    score: float = Field(description="Calculated trader score")
    account_value: float = Field(alias="accountValue", description="Current account value")
    performances: TraderPerformances = Field(description="Performance metrics")
    is_active: bool = Field(default=True, alias="isActive", description="Is being monitored")
    tags: List[str] = Field(default_factory=list, description="Trader tags")
    notes: Optional[str] = Field(default=None, description="Manual notes")
    added_at: datetime = Field(
        default_factory=datetime.utcnow, alias="addedAt", description="When added to tracking"
    )
    last_updated: datetime = Field(
        default_factory=datetime.utcnow, alias="lastUpdated", description="Last update time"
    )


# =============================================================================
# Position Models
# =============================================================================


class PositionDetail(BaseModel):
    """Detailed position information for a single coin."""

    coin: str = Field(description="Coin ticker")
    szi: float = Field(description="Position size (signed: positive=long, negative=short)")
    entry_px: float = Field(alias="entryPx", description="Entry price")
    position_value: float = Field(alias="positionValue", description="Position value in USD")
    unrealized_pnl: float = Field(alias="unrealizedPnl", description="Unrealized PnL")
    leverage: float = Field(description="Current leverage")
    liquidation_px: Optional[float] = Field(
        default=None, alias="liquidationPx", description="Liquidation price"
    )
    margin_used: float = Field(alias="marginUsed", description="Margin used for position")


class TraderPosition(BaseDocument, TimestampMixin):
    """
    Trader Position Snapshot (time-series collection).

    Stores periodic snapshots of trader positions.
    """

    eth_address: str = Field(alias="ethAddress", description="Trader's Ethereum address")
    t: datetime = Field(description="Snapshot timestamp")
    account_value: float = Field(alias="accountValue", description="Total account value")
    total_notional_pos: float = Field(
        alias="totalNotionalPos", description="Total notional position"
    )
    margin_used: float = Field(alias="marginUsed", description="Total margin used")
    positions: List[PositionDetail] = Field(default_factory=list, description="List of positions")
    btc_exposure: float = Field(alias="btcExposure", description="Net BTC exposure")


class TraderCurrentState(BaseDocument):
    """
    Trader Current State (single document per trader, upserted).

    Stores the latest position state for quick access.
    """

    eth_address: str = Field(alias="ethAddress", description="Trader's Ethereum address")
    account_value: float = Field(alias="accountValue", description="Total account value")
    positions: List[PositionDetail] = Field(default_factory=list, description="Current positions")
    btc_exposure: float = Field(alias="btcExposure", description="Net BTC exposure")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, alias="updatedAt", description="Last update time"
    )


# =============================================================================
# Order Models
# =============================================================================


class TraderOrder(BaseDocument, TimestampMixin):
    """
    Trader Order History (time-series collection).

    Stores historical orders for tracked traders.
    """

    eth_address: str = Field(alias="ethAddress", description="Trader's Ethereum address")
    oid: int = Field(description="Order ID (unique)")
    coin: str = Field(description="Coin ticker")
    side: str = Field(description="Order side: B (Buy) or A (Ask/Sell)")
    limit_px: float = Field(alias="limitPx", description="Limit price")
    sz: float = Field(description="Order size")
    order_type: str = Field(alias="orderType", description="Order type (Limit, Market, etc.)")
    tif: str = Field(description="Time in force (Alo, Ioc, etc.)")
    status: str = Field(description="Order status (open, filled, canceled)")
    timestamp: datetime = Field(description="Order creation timestamp")
    status_timestamp: datetime = Field(
        alias="statusTimestamp", description="Status change timestamp"
    )


# =============================================================================
# Leaderboard Models
# =============================================================================


class LeaderboardSnapshot(BaseDocument, TimestampMixin):
    """
    Leaderboard Snapshot (time-series collection).

    Stores daily snapshots of the full leaderboard.
    """

    t: datetime = Field(description="Snapshot timestamp")
    traders: List[dict] = Field(default_factory=list, description="Full leaderboard data")
    trader_count: int = Field(alias="traderCount", description="Number of traders in snapshot")
