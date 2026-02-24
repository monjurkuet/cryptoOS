"""Trader Weighting Engine for multi-dimensional trader scoring."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from signal_system.weighting_engine.config import WeightingConfig

logger = structlog.get_logger(__name__)


@dataclass
class TraderWeight:
    """Calculated weight for a trader."""

    address: str
    performance_weight: float
    size_weight: float
    recency_weight: float
    regime_weight: float
    composite_weight: float
    tier: str
    calculated_at: str


class TraderWeightingEngine:
    """Multi-dimensional weighting engine for trader scoring.

    Calculates weights based on four dimensions:
    - Performance: Sharpe, Sortino, consistency, drawdown, win rate
    - Size: Account value tiers (whale, large, medium, small)
    - Recency: Time-decay favoring recent performance
    - Regime: Alignment with current market conditions
    """

    def __init__(self, config: WeightingConfig | None = None) -> None:
        """Initialize the weighting engine.

        Args:
            config: Optional weighting configuration
        """
        self.config = config or WeightingConfig()
        self._current_regime: str = "unknown"
        self._weight_cache: dict[str, TraderWeight] = {}

    def set_regime(self, regime_name: str) -> None:
        """Set current market regime for regime-based weighting.

        Args:
            regime_name: Name of current market regime
        """
        self._current_regime = regime_name
        logger.debug("regime_set", regime=regime_name)

    def calculate_weight(
        self,
        address: str,
        performance_metrics: dict[str, float],
        account_value: float,
        last_trade_at: datetime | None = None,
        regime_alignment: float = 1.0,
    ) -> TraderWeight:
        """Calculate composite weight for a trader.

        Args:
            address: Trader's Ethereum address
            performance_metrics: Dict with sharpe, sortino, win_rate, etc.
            account_value: Current account value in USD
            last_trade_at: Timestamp of most recent trade
            regime_alignment: How well trader aligns with current regime (0-1)

        Returns:
            TraderWeight with all dimension scores
        """
        # Calculate each dimension
        perf_weight = self._calc_performance_weight(performance_metrics)
        size_weight = self._calc_size_weight(account_value)
        recency_weight = self._calc_recency_weight(last_trade_at)
        regime_weight = self._calc_regime_weight(regime_alignment)

        # Combine dimensions
        composite = (
            perf_weight * self.config.performance_dimension_weight
            + size_weight * self.config.size_dimension_weight
            + recency_weight * self.config.recency_dimension_weight
            + regime_weight * self.config.regime_dimension_weight
        )

        # Determine tier
        tier = self._determine_tier(account_value)

        weight = TraderWeight(
            address=address,
            performance_weight=round(perf_weight, 4),
            size_weight=round(size_weight, 4),
            recency_weight=round(recency_weight, 4),
            regime_weight=round(regime_weight, 4),
            composite_weight=round(composite, 4),
            tier=tier,
            calculated_at=datetime.now(timezone.utc).isoformat(),
        )

        self._weight_cache[address] = weight
        return weight

    def _calc_performance_weight(self, metrics: dict[str, float]) -> float:
        """Calculate performance-based weight.

        Args:
            metrics: Performance metrics dict

        Returns:
            Performance weight (0-1.5)
        """
        cfg = self.config.performance

        sharpe = metrics.get("sharpe_ratio", 0)
        sortino = metrics.get("sortino_ratio", 0)
        consistency = metrics.get("consistency", 0)
        max_dd = metrics.get("max_drawdown", 0)
        win_rate = metrics.get("win_rate", 0.5)
        profit_factor = metrics.get("profit_factor", 1)

        # Normalize each metric
        sharpe_score = min(max(sharpe / 3.0, 0), 1)  # 3+ Sharpe is excellent
        sortino_score = min(max(sortino / 4.0, 0), 1)  # 4+ Sortino is excellent
        consistency_score = min(max(consistency, 0), 1)  # Already 0-1
        dd_score = min(max(1 - abs(max_dd), 0), 1)  # Lower DD is better
        win_score = win_rate  # Already 0-1
        pf_score = min(max((profit_factor - 1) / 2, 0), 1)  # 3+ PF is excellent

        # Weighted combination
        weight = (
            sharpe_score * cfg.sharpe_weight
            + sortino_score * cfg.sortino_weight
            + consistency_score * cfg.consistency_weight
            + dd_score * cfg.max_drawdown_weight
            + win_score * cfg.win_rate_weight
            + pf_score * cfg.profit_factor_weight
        )

        return min(weight * 1.5, 1.5)  # Scale up to 1.5 max

    def _calc_size_weight(self, account_value: float) -> float:
        """Calculate size-based weight.

        Args:
            account_value: Account value in USD

        Returns:
            Size weight (0.5 to 3.0)
        """
        cfg = self.config.size

        if account_value >= cfg.alpha_whale_threshold:
            return cfg.alpha_whale_weight
        elif account_value >= cfg.whale_threshold:
            return cfg.whale_weight
        elif account_value >= cfg.large_threshold:
            return cfg.large_weight
        elif account_value >= cfg.medium_threshold:
            return cfg.medium_weight
        elif account_value >= cfg.standard_threshold:
            return cfg.standard_weight
        else:
            return cfg.small_weight

    def _calc_recency_weight(self, last_trade_at: datetime | None) -> float:
        """Calculate recency-based weight.

        Args:
            last_trade_at: Timestamp of most recent trade

        Returns:
            Recency weight (0.5 to 1.5)
        """
        if last_trade_at is None:
            return self.config.recency.min_recency

        now = datetime.now(timezone.utc)
        days_since = (now - last_trade_at).total_seconds() / 86400

        cfg = self.config.recency

        if days_since <= 1:
            return cfg.day_weight * 3.0  # Scale to max
        elif days_since <= 7:
            # Linear interpolation between day and week weight
            ratio = (days_since - 1) / 6
            base = cfg.day_weight + (cfg.week_weight - cfg.day_weight) * ratio
            return base * 2.5
        elif days_since <= 30:
            # Linear interpolation between week and month weight
            ratio = (days_since - 7) / 23
            base = cfg.week_weight + (cfg.month_weight - cfg.week_weight) * ratio
            return base * 2.0
        else:
            # Decay after a month
            decay = max(0.5, 1 - (days_since - 30) / 60)  # Decay over 60 days
            return cfg.month_weight * decay * 2.0

    def _calc_regime_weight(self, alignment: float) -> float:
        """Calculate regime-based weight.

        Args:
            alignment: How well trader aligns with current regime (0-1)

        Returns:
            Regime weight (0.5 to 1.5)
        """
        cfg = self.config.recency
        # Scale alignment to weight range
        return cfg.min_recency + (cfg.max_recency - cfg.min_recency) * alignment

    def _determine_tier(self, account_value: float) -> str:
        """Determine trader tier based on account value.

        Args:
            account_value: Account value in USD

        Returns:
            Tier name string
        """
        cfg = self.config.size

        if account_value >= cfg.alpha_whale_threshold:
            return "alpha_whale"
        elif account_value >= cfg.whale_threshold:
            return "whale"
        elif account_value >= cfg.large_threshold:
            return "large"
        elif account_value >= cfg.medium_threshold:
            return "medium"
        elif account_value >= cfg.standard_threshold:
            return "standard"
        else:
            return "small"

    def get_weight(self, address: str) -> TraderWeight | None:
        """Get cached weight for a trader.

        Args:
            address: Trader's Ethereum address

        Returns:
            Cached TraderWeight or None
        """
        return self._weight_cache.get(address)

    def get_whale_weights(self, min_tier: str = "whale") -> list[TraderWeight]:
        """Get weights for all traders at or above a tier.

        Args:
            min_tier: Minimum tier to include

        Returns:
            List of TraderWeight for qualifying traders
        """
        tier_order = ["alpha_whale", "whale", "large", "medium", "standard", "small"]
        min_idx = tier_order.index(min_tier) if min_tier in tier_order else 0

        return [
            w
            for w in self._weight_cache.values()
            if tier_order.index(w.tier) <= min_idx
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics.

        Returns:
            Dict with engine stats
        """
        weights = list(self._weight_cache.values())
        tiers = {}
        for w in weights:
            tiers[w.tier] = tiers.get(w.tier, 0) + 1

        return {
            "current_regime": self._current_regime,
            "cached_traders": len(self._weight_cache),
            "tier_distribution": tiers,
            "avg_composite_weight": (
                sum(w.composite_weight for w in weights) / len(weights) if weights else 0
            ),
        }
