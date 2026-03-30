"""Canonical structured state models."""

from datetime import datetime

from pydantic import BaseModel, Field

from trading_watchlist.models.rules import Rule
from trading_watchlist.models.trades import Position
from trading_watchlist.models.watchlist import WatchlistSummary

SCHEMA_VERSION = "v1"


class StateBundleMetadata(BaseModel):
    """Lightweight source metadata for the canonical state bundle."""

    source_mode: str
    sources: dict[str, str] = Field(default_factory=dict)


class StateBundle(BaseModel):
    """Canonical structured state document for integrations."""

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime
    prices: dict[str, float] = Field(default_factory=dict)
    rules: list[Rule] = Field(default_factory=list)
    positions: list[Position] = Field(default_factory=list)
    watchlist: WatchlistSummary = Field(default_factory=WatchlistSummary)
    metadata: StateBundleMetadata


class ManifestFileEntry(BaseModel):
    """Manifest metadata for an exported file."""

    filename: str
    generated_at: datetime


class StateManifest(BaseModel):
    """Lightweight export manifest."""

    schema_version: str = SCHEMA_VERSION
    generated_at: datetime
    source_mode: str
    files: dict[str, ManifestFileEntry] = Field(default_factory=dict)


class StateWriteResponse(BaseModel):
    """Structured response for canonical state persistence."""

    schema_version: str
    source_mode: str
    written_files: list[str] = Field(default_factory=list)
