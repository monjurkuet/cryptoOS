# src/market_scraper/config/market_config.py

"""Market configuration loader.

This module provides YAML-based configuration for market data collection,
scoring weights, retention, and buffer settings.
"""

from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ScoringWeights(BaseModel):
    """Scoring weight configuration.

    Weights determine how much each factor contributes to the overall score.
    Should ideally sum to 100 for proper percentage weighting.
    """

    all_time_roi: float = 30
    month_roi: float = 25
    week_roi: float = 20
    account_value: float = 15
    volume: float = 10


class ScoringConfig(BaseModel):
    """Scoring algorithm configuration."""

    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    consistency_bonus: float = 5
    roi_multipliers: dict[str, float] = {
        "all_time": 30,
        "month": 50,
        "week": 100,
    }


class TierConfig(BaseModel):
    """Tier-based scoring configuration.

    Used for account value and volume scoring tiers.
    """

    threshold: float
    points: float


class FilterConfig(BaseModel):
    """Filter criteria for trader selection.

    Traders must match ALL filter criteria to be selected.
    """

    min_score: float = 50
    max_count: int = 500
    min_account_value: float = 10000
    require_positive: dict[str, bool] = Field(default_factory=dict)
    exclude: dict[str, list[str]] = Field(default_factory=dict)


class TagConfig(BaseModel):
    """Tag configuration for automatic trader tagging."""

    whale: dict[str, Any] = Field(default_factory=lambda: {"threshold": 10_000_000})
    large: dict[str, Any] = Field(default_factory=lambda: {"threshold": 1_000_000})
    top_performer: dict[str, Any] = Field(default_factory=lambda: {"min_score": 80})
    elite: dict[str, Any] = Field(default_factory=lambda: {"min_score": 90})
    consistent: dict[str, Any] = Field(
        default_factory=lambda: {"require_positive": ["day", "week", "month"]}
    )
    high_performer: dict[str, Any] = Field(default_factory=lambda: {"all_time_roi": 1.0})
    high_volume: dict[str, Any] = Field(default_factory=lambda: {"monthly_volume": 100_000_000})
    medium_volume: dict[str, Any] = Field(default_factory=lambda: {"monthly_volume": 10_000_000})


class PositionInferenceConfig(BaseModel):
    """Position inference configuration.

    Controls how the system infers likely active positions from leaderboard data.
    """

    enabled: bool = True
    confidence_threshold: float = 0.5
    indicators: dict[str, float] = {
        "day_roi_threshold": 0.0001,
        "pnl_ratio_threshold": 0.001,
        "day_volume_threshold": 100_000,
    }


class RetentionConfig(BaseModel):
    """Per-collection retention configuration in days.

    Controls how long data is kept before automatic deletion via MongoDB TTL indexes.
    """

    events: int = Field(default=7, description="Days to keep raw events (catch-all audit log)")
    leaderboard_history: int = Field(default=90, description="Days to keep leaderboard history")
    trader_positions: int = Field(default=30, description="Days to keep position snapshots")
    trader_scores: int = Field(default=90, description="Days to keep score history")
    signals: int = Field(default=30, description="Days to keep trading signals")
    trader_signals: int = Field(default=30, description="Days to keep trader signals")
    mark_prices: int = Field(default=30, description="Days to keep mark prices")
    trades: int = Field(default=7, description="Days to keep trade data")
    orderbook: int = Field(default=7, description="Days to keep orderbook snapshots")
    candles: int = Field(default=30, description="Days to keep candle data")


class StorageConfig(BaseModel):
    """Storage configuration for leaderboard data."""

    refresh_interval: int = 3600
    keep_snapshots: bool = True
    keep_score_history: bool = False
    retention: RetentionConfig = Field(default_factory=RetentionConfig)


class BufferConfig(BaseModel):
    """Buffer and flush configuration.

    Controls how events are batched before being saved to MongoDB.
    Larger buffers reduce database writes but increase memory usage and latency.
    """

    flush_interval: float = Field(
        default=5.0,
        description="Seconds between automatic buffer flushes to database",
    )
    max_size: int = Field(
        default=100,
        description="Maximum events to buffer before forced flush",
    )
    broadcast_batch_size: int = Field(
        default=100,
        description="Maximum messages to batch for WebSocket broadcasts",
    )
    broadcast_batch_timeout_ms: float = Field(
        default=10.0,
        description="Maximum milliseconds to wait before flushing broadcast batch",
    )


class CandleBackfillConfig(BaseModel):
    """Candle backfill configuration.

    Controls historical OHLCV data backfill from Hyperliquid HTTP API.
    """

    enabled: bool = Field(default=True, description="Enable candle backfill on startup")
    start_date: date | None = Field(
        default=None, description="Start date for backfill (null = earliest available)"
    )
    timeframes: list[str] = Field(
        default=["1h", "4h", "1d"], description="Timeframes to backfill (1h and above recommended)"
    )
    batch_size: int = Field(default=500, description="Candles per API request")
    rate_limit_delay: float = Field(default=0.5, description="Delay between requests (seconds)")
    run_on_startup: bool = Field(default=True, description="Run backfill on every startup")
    incremental: bool = Field(
        default=True,
        description="Only fetch missing data (check latest candle and fetch from there)",
    )


class SchedulerTaskConfig(BaseModel):
    """Configuration for a single scheduled task."""

    enabled: bool = Field(default=True, description="Enable this scheduled task")
    interval_seconds: int = Field(default=60, description="Interval between task executions")


class SchedulerConfig(BaseModel):
    """Scheduler configuration for periodic background tasks.

    Controls the task scheduler that runs periodic jobs like
    leaderboard refresh, health checks, and data cleanup.
    """

    enabled: bool = Field(default=True, description="Enable the scheduler")
    tasks: dict[str, SchedulerTaskConfig] = Field(
        default_factory=dict,
        description="Periodic tasks configuration",
    )


class MarketConfig(BaseModel):
    """Complete market configuration.

    This is the main configuration class that contains all settings
    for market data collection, trader scoring, storage, and buffering.
    """

    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    account_value_tiers: list[TierConfig] = [
        TierConfig(threshold=10_000_000, points=15),
        TierConfig(threshold=5_000_000, points=12),
        TierConfig(threshold=1_000_000, points=8),
        TierConfig(threshold=100_000, points=4),
        TierConfig(threshold=0, points=0),
    ]
    volume_tiers: list[TierConfig] = [
        TierConfig(threshold=100_000_000, points=10),
        TierConfig(threshold=50_000_000, points=7),
        TierConfig(threshold=10_000_000, points=4),
        TierConfig(threshold=1_000_000, points=2),
        TierConfig(threshold=0, points=0),
    ]
    filters: FilterConfig = Field(default_factory=FilterConfig)
    tags: TagConfig = Field(default_factory=TagConfig)
    position_inference: PositionInferenceConfig = Field(default_factory=PositionInferenceConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    buffer: BufferConfig = Field(default_factory=BufferConfig)
    candle_backfill: CandleBackfillConfig = Field(default_factory=CandleBackfillConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)


def load_market_config(config_path: str | Path | None = None) -> MarketConfig:
    """Load market configuration from YAML file.

    Args:
        config_path: Path to config file. Defaults to config/market_config.yaml

    Returns:
        MarketConfig instance with loaded or default values
    """
    if config_path is None:
        possible_paths = [
            Path("config/market_config.yaml"),
            Path("market_config.yaml"),
            Path.home() / ".config" / "market_scraper" / "market_config.yaml",
        ]
        config_path = next((p for p in possible_paths if p.exists()), possible_paths[0])
    else:
        config_path = Path(config_path)

    if not config_path.exists():
        return MarketConfig()

    with open(config_path) as f:
        data = yaml.safe_load(f) or {}

    return MarketConfig(**data)
