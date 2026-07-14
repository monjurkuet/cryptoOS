"""Data models for MongoDB documents."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LeaderboardRow(BaseModel):
    eth: str = ""
    name: str | None = None
    acct_val: float = 0.0
    roi_all_time: float = 0.0
    roi_year: float = 0.0
    roi_month: float = 0.0
    roi_week: float = 0.0
    roi_day: float = 0.0
    volume_month: float = 0.0
    pnl_all_time: float = 0.0
    score: float = 0.0
    tags: list[str] = Field(default_factory=list)
    rank: int = 0


class TrackedTrader(BaseModel):
    eth: str
    name: str | None = None
    acct_val: float = 0.0
    score: float = 0.0
    tags: list[str] = Field(default_factory=list)
    leaderboard_rank: int = 0
    roi_all_time: float = 0.0
    roi_month: float = 0.0
    roi_week: float = 0.0
    selected_at: datetime | None = None
    last_position_update: datetime | None = None
    position_hash: str | None = None


class Position(BaseModel):
    eth: str
    symbol: str
    size: float = 0.0
    entry_price: float = 0.0
    mark_price: float = 0.0
    unrealized_pnl: float = 0.0
    leverage: float = 0.0
    liquidation_price: float | None = None
    timestamp: datetime


class TraderState(BaseModel):
    eth: str
    symbol: str
    positions: list[dict[str, Any]] = Field(default_factory=list)
    open_orders: list[dict[str, Any]] = Field(default_factory=list)
    margin_summary: dict[str, Any] = Field(default_factory=dict)
    position_hash: str
    updated_at: datetime
