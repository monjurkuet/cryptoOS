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


class TieredFilterDef(BaseModel):
    """Configuration for a single tier in multi-tier filtering.

    Each tier draws from the scored trader universe independently.
    A trader can belong to multiple tiers; the first matching tier wins.
    Tiers are evaluated in definition order (Whales -> Alpha -> Grinders -> Momentum).
    """

    name: str
    max_slots: int = 50
    min_account_value: float = 0
    min_score: float = 0
    min_roi_all_time: float | None = None
    min_roi_month: float | None = None
    min_roi_week: float | None = None
    min_roi_day: float | None = None
    min_volume_month: float | None = None
    require_positive: list[str] | None = None  # windows: ["day", "week", "month"]


class FilterConfig(BaseModel):
    """Filter criteria for trader selection.

    Traders must match ALL filter criteria to be selected.
    Supports both boolean (require_positive) and numeric thresholds
    for ROI, volume, and PnL across all time windows.

    When tiered_filters are enabled, the multi-tier filter replaces the
    single-score-threshold approach, allocating the max_count slots across
    different trader pools (Whales, Alpha, Grinders, Momentum).
    """

    min_score: float = 50
    max_count: int = 200
    min_account_value: float = 10000
    require_positive: dict[str, bool] = Field(default_factory=dict)
    # Numeric ROI thresholds (null = no filter)
    min_roi_all_time: float | None = None
    max_roi_all_time: float | None = None
    min_roi_month: float | None = None
    max_roi_month: float | None = None
    min_roi_week: float | None = None
    max_roi_week: float | None = None
    min_roi_day: float | None = None
    max_roi_day: float | None = None
    # Numeric volume thresholds
    min_volume_month: float | None = None
    max_volume_month: float | None = None
    # Numeric PnL thresholds
    min_pnl_all_time: float | None = None
    max_pnl_all_time: float | None = None
    include: dict[str, list[str]] = Field(default_factory=dict)
    exclude: dict[str, list[str]] = Field(default_factory=dict)
    # Multi-tier filtering (replaces single-score approach when enabled)
    tiered_enabled: bool = True
    tiers: list[TieredFilterDef] = Field(default_factory=list)


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


class CadenceTierConfig(BaseModel):
    """Configuration for a single tracking cadence tier (Gold/Silver/Watchlist).

    Controls which traders get real-time position tracking vs occasional score checks.
    """

    max_traders: int = 50
    check_interval_seconds: int = 120
    min_acct_val: float = 100_000.0
    min_month_roi: float = 3.0
    min_score: float = 50.0


class TrackingCadenceConfig(BaseModel):
    """Configuration for tracking cadence tiers.

    Traders are grouped into cadence tiers with different update frequencies
    to avoid wasting API calls on low-signal traders.
    """

    enabled: bool = True
    check_interval_base: int = 60
    tiers: dict[str, CadenceTierConfig] = {
        "gold": CadenceTierConfig(max_traders=20, check_interval_seconds=30,
                                   min_acct_val=1_000_000, min_month_roi=5.0, min_score=70),
        "silver": CadenceTierConfig(max_traders=50, check_interval_seconds=120,
                                     min_acct_val=100_000, min_month_roi=3.0, min_score=50),
        "watchlist": CadenceTierConfig(max_traders=100, check_interval_seconds=300,
                                        min_acct_val=10_000, min_month_roi=0.0, min_score=30),
    }


class PromoterConfig(BaseModel):
    """Configuration for the promotion/demotion engine.

    Evaluates tracked traders each cycle and promotes/demotes them
    between cadence tiers based on performance.
    """

    enabled: bool = True
    stale_cycles: int = 10
    min_demote_score: float = 20.0
    promotion_warmup_cycles: int = 3
    max_evictions_per_cycle: int = 10


class PositionInferenceConfig(BaseModel):
    """Position inference configuration.

    Controls how the system infers likely active positions from leaderboard data.
    """

    enabled: bool = True
    confidence_threshold: float = 0.5
    max_inferred_traders: int = 50
    indicators: dict[str, float] = {
        "day_roi_threshold": 0.0001,
        "pnl_ratio_threshold": 0.001,
        "day_volume_threshold": 100_000,
    }


class RetentionConfig(BaseModel):
    """Per-collection retention configuration in days.

    Controls how long data is kept before automatic deletion via MongoDB TTL indexes.
    """

    events: int = Field(default=2, description="Days to keep raw audit events only")
    leaderboard_history: int = Field(default=90, description="Days to keep leaderboard history")
    leaderboard_raw: int = Field(default=7, description="Days to keep raw 39K leaderboard snapshots")
    trader_positions: int = Field(default=7, description="Days to keep position snapshots")
    trader_closed_trades: int = Field(default=90, description="Days to keep closed-trade ledger")
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
    keep_raw_leaderboard: bool = True
    retention: RetentionConfig = Field(default_factory=RetentionConfig)


class BufferConfig(BaseModel):
    """Buffer and flush configuration.

    Controls how events are batched before being saved to MongoDB.
    Larger buffers reduce database writes but increase memory usage and latency.
    """

    flush_interval: float = Field(
        default=10.0,  # Changed from 60.0 — 60s was causing stale data accumulation
        description="Seconds between automatic buffer flushes to database (10s = reduced latency)",
    )
    max_size: int = Field(
        default=2000,  # Increased from 500 — more headroom before forced flush
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


class TraderWsConfig(BaseModel):
    """Trader WebSocket tracking configuration."""

    # Hard-cap the number of websocket clients to keep system stable.
    max_clients: int = Field(default=5, ge=1, le=30)
    # Hyperliquid webData2 allows max 10 users/connection; keep this fixed.
    subscriptions_per_client: int = Field(default=10, ge=1, le=10)
    # Rotate the tracked WS subset through the active universe at this interval.
    rotation_interval_seconds: int = Field(default=900, ge=60, le=86400)


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
    run_on_startup: bool = Field(default=False, description="Run backfill on every startup (disabled: causes OOM on budget VPS)")
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
    tracking_cadence: TrackingCadenceConfig = Field(default_factory=TrackingCadenceConfig)
    promoter: PromoterConfig = Field(default_factory=PromoterConfig)
    position_inference: PositionInferenceConfig = Field(default_factory=PositionInferenceConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    buffer: BufferConfig = Field(default_factory=BufferConfig)
    trader_ws: TraderWsConfig = Field(default_factory=TraderWsConfig)
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
