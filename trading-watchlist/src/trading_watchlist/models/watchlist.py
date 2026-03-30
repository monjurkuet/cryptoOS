"""Watchlist models."""

from pydantic import BaseModel, Field


class AlertLevel(BaseModel):
    """Parsed alert level."""

    price: str
    asset: str
    direction: str
    trigger: str
    priority: str


class ApproachingSetup(BaseModel):
    """Parsed approaching setup."""

    title: str
    rule_id: str | None = None
    fields: dict[str, str] = Field(default_factory=dict)
    summary: str | None = None


class WatchlistSummary(BaseModel):
    """Combined watchlist data."""

    live_positions: list[dict[str, str]] = Field(default_factory=list)
    approaching: list[ApproachingSetup] = Field(default_factory=list)
    future_setups: list[ApproachingSetup] = Field(default_factory=list)
    alerts: list[AlertLevel] = Field(default_factory=list)
    expiring: list[dict[str, str]] = Field(default_factory=list)
