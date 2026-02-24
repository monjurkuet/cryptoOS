"""Weighting Configuration."""

from dataclasses import dataclass, field


@dataclass
class PerformanceWeightConfig:
    """Configuration for performance-based weighting."""

    sharpe_weight: float = 0.25
    sortino_weight: float = 0.20
    consistency_weight: float = 0.20
    max_drawdown_weight: float = 0.15
    win_rate_weight: float = 0.10
    profit_factor_weight: float = 0.10


@dataclass
class SizeWeightConfig:
    """Configuration for size-based weighting."""

    alpha_whale_threshold: float = 20_000_000
    whale_threshold: float = 10_000_000
    large_threshold: float = 5_000_000
    medium_threshold: float = 1_000_000
    standard_threshold: float = 100_000

    alpha_whale_weight: float = 3.0
    whale_weight: float = 2.5
    large_weight: float = 2.0
    medium_weight: float = 1.5
    standard_weight: float = 1.0
    small_weight: float = 0.5


@dataclass
class RecencyWeightConfig:
    """Configuration for recency-based weighting."""

    day_weight: float = 0.50
    week_weight: float = 0.30
    month_weight: float = 0.20
    min_recency: float = 0.5
    max_recency: float = 1.5


@dataclass
class WeightingConfig:
    """Master weighting configuration."""

    performance: PerformanceWeightConfig = field(default_factory=PerformanceWeightConfig)
    size: SizeWeightConfig = field(default_factory=SizeWeightConfig)
    recency: RecencyWeightConfig = field(default_factory=RecencyWeightConfig)

    performance_dimension_weight: float = 0.40
    size_dimension_weight: float = 0.30
    recency_dimension_weight: float = 0.20
    regime_dimension_weight: float = 0.10
