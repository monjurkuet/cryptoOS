"""Structured repository payloads."""

from pydantic import BaseModel, Field

from trading_watchlist.models.common import PriceResponse
from trading_watchlist.models.rules import Rule
from trading_watchlist.models.state import StateBundle, StateManifest
from trading_watchlist.models.trades import Position
from trading_watchlist.models.watchlist import WatchlistSummary


class RulesDocument(BaseModel):
    """Rules plus extracted price metadata."""

    prices: dict[str, float] = Field(default_factory=dict)
    rules: list[Rule] = Field(default_factory=list)


class PositionsDocument(BaseModel):
    """Positions plus extracted price metadata."""

    prices: dict[str, float] = Field(default_factory=dict)
    positions: list[Position] = Field(default_factory=list)


class WatchlistDocument(BaseModel):
    """Watchlist plus extracted price metadata."""

    prices: dict[str, float] = Field(default_factory=dict)
    watchlist: WatchlistSummary = Field(default_factory=WatchlistSummary)


class PricesDocument(PriceResponse):
    """Structured prices payload."""


class StateDocument(StateBundle):
    """Structured canonical state payload."""


class ManifestDocument(StateManifest):
    """Structured manifest payload."""
