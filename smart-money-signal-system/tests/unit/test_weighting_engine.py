"""Unit tests for the Trader Weighting Engine."""

from datetime import datetime, timedelta, timezone

import pytest

from signal_system.weighting_engine.engine import TraderWeight, TraderWeightingEngine
from signal_system.weighting_engine.config import (
    PerformanceWeightConfig,
    SizeWeightConfig,
    RecencyWeightConfig,
    WeightingConfig,
)


class TestWeightingEngine:
    """Tests for TraderWeightingEngine."""

    def test_init_default_config(self):
        """Test engine initializes with default config."""
        engine = TraderWeightingEngine()
        assert engine.config is not None
        assert engine._current_regime == "unknown"

    def test_init_custom_config(self):
        """Test engine initializes with custom config."""
        config = WeightingConfig(
            performance_dimension_weight=0.5,
            size_dimension_weight=0.3,
        )
        engine = TraderWeightingEngine(config=config)
        assert engine.config.performance_dimension_weight == 0.5

    def test_set_regime(self):
        """Test setting market regime."""
        engine = TraderWeightingEngine()
        engine.set_regime("early_bull")
        assert engine._current_regime == "early_bull"

    def test_calculate_weight_basic(self):
        """Test basic weight calculation."""
        engine = TraderWeightingEngine()

        weight = engine.calculate_weight(
            address="0xtest123",
            performance_metrics={"sharpe_ratio": 1.5, "win_rate": 0.6},
            account_value=1_000_000,
        )

        assert isinstance(weight, TraderWeight)
        assert weight.address == "0xtest123"
        assert 0 <= weight.performance_weight <= 1.5
        assert 0.5 <= weight.size_weight <= 3.0
        assert 0.5 <= weight.recency_weight <= 1.5
        assert 0.5 <= weight.regime_weight <= 1.5
        assert weight.tier in ["alpha_whale", "whale", "large", "medium", "standard", "small"]

    def test_performance_weight_excellent(self):
        """Test performance weight for excellent trader."""
        engine = TraderWeightingEngine()

        # Excellent trader metrics
        metrics = {
            "sharpe_ratio": 3.0,
            "sortino_ratio": 4.0,
            "consistency": 0.9,
            "max_drawdown": -0.1,
            "win_rate": 0.7,
            "profit_factor": 3.0,
        }

        perf_weight = engine._calc_performance_weight(metrics)
        # Should be high (close to 1.5)
        assert perf_weight > 1.0

    def test_performance_weight_poor(self):
        """Test performance weight for poor trader."""
        engine = TraderWeightingEngine()

        # Poor trader metrics
        metrics = {
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "consistency": 0.3,
            "max_drawdown": -0.5,
            "win_rate": 0.3,
            "profit_factor": 0.8,
        }

        perf_weight = engine._calc_performance_weight(metrics)
        # Should be low
        assert perf_weight < 0.8

    def test_size_weight_alpha_whale(self):
        """Test size weight for alpha whale."""
        engine = TraderWeightingEngine()

        size_weight = engine._calc_size_weight(25_000_000)  # $25M
        assert size_weight == engine.config.size.alpha_whale_weight  # 3.0

    def test_size_weight_whale(self):
        """Test size weight for whale."""
        engine = TraderWeightingEngine()

        size_weight = engine._calc_size_weight(12_000_000)  # $12M
        assert size_weight == engine.config.size.whale_weight  # 2.5

    def test_size_weight_large(self):
        """Test size weight for large trader."""
        engine = TraderWeightingEngine()

        size_weight = engine._calc_size_weight(7_000_000)  # $7M
        assert size_weight == engine.config.size.large_weight  # 2.0

    def test_size_weight_medium(self):
        """Test size weight for medium trader."""
        engine = TraderWeightingEngine()

        size_weight = engine._calc_size_weight(2_000_000)  # $2M
        assert size_weight == engine.config.size.medium_weight  # 1.5

    def test_size_weight_standard(self):
        """Test size weight for standard trader."""
        engine = TraderWeightingEngine()

        size_weight = engine._calc_size_weight(500_000)  # $500K
        assert size_weight == engine.config.size.standard_weight  # 1.0

    def test_size_weight_small(self):
        """Test size weight for small trader."""
        engine = TraderWeightingEngine()

        size_weight = engine._calc_size_weight(50_000)  # $50K
        assert size_weight == engine.config.size.small_weight  # 0.5

    def test_recency_weight_day(self):
        """Test recency weight for recent trade (within day)."""
        engine = TraderWeightingEngine()

        last_trade = datetime.now(timezone.utc) - timedelta(hours=12)
        recency_weight = engine._calc_recency_weight(last_trade)
        # Should be high for recent trade
        assert recency_weight > 1.0

    def test_recency_weight_week(self):
        """Test recency weight for trade within week."""
        engine = TraderWeightingEngine()

        last_trade = datetime.now(timezone.utc) - timedelta(days=5)
        recency_weight = engine._calc_recency_weight(last_trade)
        # Should be moderate
        assert 0.5 < recency_weight < 2.0

    def test_recency_weight_month(self):
        """Test recency weight for trade within month."""
        engine = TraderWeightingEngine()

        last_trade = datetime.now(timezone.utc) - timedelta(days=20)
        recency_weight = engine._calc_recency_weight(last_trade)
        # Should be lower
        assert recency_weight < 1.5

    def test_recency_weight_none(self):
        """Test recency weight for no trade history."""
        engine = TraderWeightingEngine()

        recency_weight = engine._calc_recency_weight(None)
        # Should be minimum
        assert recency_weight == engine.config.recency.min_recency

    def test_regime_weight_high_alignment(self):
        """Test regime weight for high alignment."""
        engine = TraderWeightingEngine()

        regime_weight = engine._calc_regime_weight(1.0)
        # Should be max
        assert regime_weight == engine.config.recency.max_recency

    def test_regime_weight_low_alignment(self):
        """Test regime weight for low alignment."""
        engine = TraderWeightingEngine()

        regime_weight = engine._calc_regime_weight(0.0)
        # Should be min
        assert regime_weight == engine.config.recency.min_recency

    def test_determine_tier_alpha_whale(self):
        """Test tier determination for alpha whale."""
        engine = TraderWeightingEngine()

        tier = engine._determine_tier(25_000_000)
        assert tier == "alpha_whale"

    def test_determine_tier_whale(self):
        """Test tier determination for whale."""
        engine = TraderWeightingEngine()

        tier = engine._determine_tier(15_000_000)
        assert tier == "whale"

    def test_determine_tier_large(self):
        """Test tier determination for large trader."""
        engine = TraderWeightingEngine()

        tier = engine._determine_tier(6_000_000)
        assert tier == "large"

    def test_determine_tier_medium(self):
        """Test tier determination for medium trader."""
        engine = TraderWeightingEngine()

        tier = engine._determine_tier(1_500_000)
        assert tier == "medium"

    def test_determine_tier_standard(self):
        """Test tier determination for standard trader."""
        engine = TraderWeightingEngine()

        tier = engine._determine_tier(200_000)
        assert tier == "standard"

    def test_determine_tier_small(self):
        """Test tier determination for small trader."""
        engine = TraderWeightingEngine()

        tier = engine._determine_tier(50_000)
        assert tier == "small"

    def test_composite_weight_calculation(self):
        """Test composite weight combines all dimensions."""
        engine = TraderWeightingEngine()

        weight = engine.calculate_weight(
            address="0xcomposite",
            performance_metrics={"sharpe_ratio": 2.0, "win_rate": 0.6},
            account_value=15_000_000,
            last_trade_at=datetime.now(timezone.utc) - timedelta(hours=6),
            regime_alignment=0.8,
        )

        # Composite should be weighted average
        expected = (
            weight.performance_weight * engine.config.performance_dimension_weight
            + weight.size_weight * engine.config.size_dimension_weight
            + weight.recency_weight * engine.config.recency_dimension_weight
            + weight.regime_weight * engine.config.regime_dimension_weight
        )
        assert abs(weight.composite_weight - expected) < 0.001

    def test_get_weight_cached(self):
        """Test getting cached weight."""
        engine = TraderWeightingEngine()

        engine.calculate_weight(
            address="0xcached",
            performance_metrics={"sharpe_ratio": 1.5},
            account_value=1_000_000,
        )

        cached = engine.get_weight("0xcached")
        assert cached is not None
        assert cached.address == "0xcached"

    def test_get_weight_not_found(self):
        """Test getting weight for unknown trader."""
        engine = TraderWeightingEngine()

        weight = engine.get_weight("0xunknown")
        assert weight is None

    def test_get_whale_weights(self):
        """Test getting weights for whales and above."""
        engine = TraderWeightingEngine()

        # Add traders at different tiers
        engine.calculate_weight("0xalpha", {"sharpe_ratio": 2.0}, 25_000_000)
        engine.calculate_weight("0xwhale", {"sharpe_ratio": 1.5}, 12_000_000)
        engine.calculate_weight("0xlarge", {"sharpe_ratio": 1.0}, 6_000_000)
        engine.calculate_weight("0xsmall", {"sharpe_ratio": 0.5}, 50_000)

        # Get whale and above
        whale_weights = engine.get_whale_weights(min_tier="whale")
        addresses = [w.address for w in whale_weights]

        assert "0xalpha" in addresses
        assert "0xwhale" in addresses
        assert "0xlarge" not in addresses  # Large is below whale
        assert "0xsmall" not in addresses

    def test_get_stats(self):
        """Test getting engine statistics."""
        engine = TraderWeightingEngine()

        engine.calculate_weight("0x1", {"sharpe_ratio": 1.5}, 25_000_000)
        engine.calculate_weight("0x2", {"sharpe_ratio": 1.0}, 5_000_000)

        stats = engine.get_stats()

        assert stats["cached_traders"] == 2
        assert stats["current_regime"] == "unknown"
        assert "tier_distribution" in stats
        assert "avg_composite_weight" in stats


class TestWeightingConfig:
    """Tests for weighting configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = WeightingConfig()

        # Dimension weights should sum to 1.0
        total = (
            config.performance_dimension_weight
            + config.size_dimension_weight
            + config.recency_dimension_weight
            + config.regime_dimension_weight
        )
        assert abs(total - 1.0) < 0.0001  # Account for floating point precision

    def test_performance_config_defaults(self):
        """Test performance weight configuration defaults."""
        config = PerformanceWeightConfig()

        # Weights should sum to 1.0
        total = (
            config.sharpe_weight
            + config.sortino_weight
            + config.consistency_weight
            + config.max_drawdown_weight
            + config.win_rate_weight
            + config.profit_factor_weight
        )
        assert total == 1.0

    def test_size_config_thresholds(self):
        """Test size thresholds are in descending order."""
        config = SizeWeightConfig()

        assert config.alpha_whale_threshold > config.whale_threshold
        assert config.whale_threshold > config.large_threshold
        assert config.large_threshold > config.medium_threshold
        assert config.medium_threshold > config.standard_threshold

    def test_size_config_weights(self):
        """Test size weights are in descending order."""
        config = SizeWeightConfig()

        assert config.alpha_whale_weight > config.whale_weight
        assert config.whale_weight > config.large_weight
        assert config.large_weight > config.medium_weight
        assert config.medium_weight > config.standard_weight
        assert config.standard_weight > config.small_weight
