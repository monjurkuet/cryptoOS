"""Tests for Market Regime Detection."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from signal_system.ml.regime_detection import (
    MarketRegimeDetector,
    RegimeInfo,
    REGIME_DEFINITIONS,
)


class TestRegimeInfo:
    """Tests for RegimeInfo dataclass."""

    def test_creation(self) -> None:
        """Test creating RegimeInfo."""
        info = RegimeInfo(
            regime_id=0,
            name="test_regime",
            description="Test description",
            signal_multiplier=1.5,
            characteristics={"volatility": "low"},
        )
        assert info.regime_id == 0
        assert info.name == "test_regime"
        assert info.signal_multiplier == 1.5


class TestRegimeDefinitions:
    """Tests for predefined regime definitions."""

    def test_all_regimes_defined(self) -> None:
        """Test all 6 regimes are defined."""
        assert len(REGIME_DEFINITIONS) == 6

    def test_regime_ids_sequential(self) -> None:
        """Test regime IDs are 0-5."""
        assert set(REGIME_DEFINITIONS.keys()) == {0, 1, 2, 3, 4, 5}

    def test_signal_multipliers_valid(self) -> None:
        """Test all signal multipliers are in valid range."""
        for regime_id, info in REGIME_DEFINITIONS.items():
            assert 0 < info.signal_multiplier <= 2.0


class TestMarketRegimeDetector:
    """Tests for MarketRegimeDetector class."""

    def test_init(self, tmp_path: Path) -> None:
        """Test initialization."""
        detector = MarketRegimeDetector(model_path=tmp_path / "model.joblib")

        assert detector.n_clusters == 6
        assert detector._model is None
        assert detector._scaler is None
        assert detector._current_regime is None

    def test_init_custom_params(self, tmp_path: Path) -> None:
        """Test initialization with custom parameters."""
        detector = MarketRegimeDetector(
            model_path=tmp_path / "model.joblib",
            n_clusters=4,
            random_state=123,
            max_history=500,
        )

        assert detector.n_clusters == 4
        assert detector.random_state == 123
        assert detector.max_history == 500

    def test_train(self, tmp_path: Path) -> None:
        """Test model training."""
        detector = MarketRegimeDetector(model_path=tmp_path / "model.joblib")

        # Create sample training data
        np.random.seed(42)
        X = pd.DataFrame(
            np.random.randn(100, 8),
            columns=[
                "volatility_annual",
                "range_ratio",
                "price_change",
                "adx",
                "volume_ratio",
                "volume_cv",
                "upper_wick",
                "lower_wick",
            ],
        )

        result = detector.train(X)

        assert "n_clusters" in result
        assert result["n_clusters"] == 6
        assert "cluster_counts" in result
        assert detector._model is not None
        assert detector._scaler is not None

    def test_detect_without_model(self, tmp_path: Path) -> None:
        """Test detection raises error without trained model."""
        detector = MarketRegimeDetector(model_path=tmp_path / "model.joblib")

        features = np.random.randn(8)

        with pytest.raises(RuntimeError, match="Model not trained"):
            detector.detect(features)

    def test_detect_with_model(self, tmp_path: Path) -> None:
        """Test detection with trained model."""
        detector = MarketRegimeDetector(model_path=tmp_path / "model.joblib")

        # Train model first
        np.random.seed(42)
        X = pd.DataFrame(np.random.randn(100, 8))
        detector.train(X)

        # Detect regime
        features = np.random.randn(8)
        result = detector.detect(features)

        assert isinstance(result, RegimeInfo)
        assert result.regime_id in REGIME_DEFINITIONS
        assert detector._current_regime == result.regime_id

    def test_history_bounded(self, tmp_path: Path) -> None:
        """Test that history is bounded by maxlen."""
        detector = MarketRegimeDetector(
            model_path=tmp_path / "model.joblib",
            max_history=10,
        )

        # Train model
        np.random.seed(42)
        X = pd.DataFrame(np.random.randn(100, 8))
        detector.train(X)

        # Detect multiple times
        for _ in range(20):
            features = np.random.randn(8)
            detector.detect(features)

        # History should be bounded
        assert len(detector._regime_history) <= 10

    def test_get_signal_multiplier_no_regime(self, tmp_path: Path) -> None:
        """Test signal multiplier when no regime detected."""
        detector = MarketRegimeDetector(model_path=tmp_path / "model.joblib")

        assert detector.get_signal_multiplier() == 1.0

    def test_get_current_regime_none(self, tmp_path: Path) -> None:
        """Test getting current regime when none detected."""
        detector = MarketRegimeDetector(model_path=tmp_path / "model.joblib")

        assert detector.get_current_regime() is None

    def test_get_stats(self, tmp_path: Path) -> None:
        """Test getting detector stats."""
        detector = MarketRegimeDetector(model_path=tmp_path / "model.joblib")

        stats = detector.get_stats()

        assert "model_loaded" in stats
        assert "current_regime" in stats
        assert "history_entries" in stats
        assert stats["model_loaded"] is False

    def test_load_model_not_found(self, tmp_path: Path) -> None:
        """Test loading model when file doesn't exist."""
        detector = MarketRegimeDetector(model_path=tmp_path / "nonexistent.joblib")

        result = detector.load_model()

        assert result is False

    def test_save_analysis(self, tmp_path: Path) -> None:
        """Test saving analysis to JSON."""
        detector = MarketRegimeDetector(model_path=tmp_path / "model.joblib")

        # Train model
        np.random.seed(42)
        X = pd.DataFrame(np.random.randn(100, 8))
        detector.train(X)

        # Detect regime
        features = np.random.randn(8)
        detector.detect(features)

        # Save analysis
        detector.save_analysis()

        # Check file was created
        json_path = tmp_path / "model.json"
        assert json_path.exists()
