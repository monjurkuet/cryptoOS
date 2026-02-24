"""Market Regime Detection using KMeans clustering."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import structlog
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = structlog.get_logger(__name__)


@dataclass
class RegimeInfo:
    """Information about a detected market regime."""

    regime_id: int
    name: str
    description: str
    signal_multiplier: float
    characteristics: dict[str, float]


# Predefined regime definitions based on market conditions
REGIME_DEFINITIONS: dict[int, RegimeInfo] = {
    0: RegimeInfo(
        regime_id=0,
        name="deep_accumulation",
        description="Strong accumulation phase, smart money buying",
        signal_multiplier=1.5,
        characteristics={"volatility": "low", "volume": "increasing", "trend": "sideways"},
    ),
    1: RegimeInfo(
        regime_id=1,
        name="early_bull",
        description="Early bull market, momentum building",
        signal_multiplier=1.3,
        characteristics={"volatility": "moderate", "volume": "increasing", "trend": "up"},
    ),
    2: RegimeInfo(
        regime_id=2,
        name="mid_bull",
        description="Mid bull market, strong uptrend",
        signal_multiplier=1.0,
        characteristics={"volatility": "moderate", "volume": "high", "trend": "up"},
    ),
    3: RegimeInfo(
        regime_id=3,
        name="late_bull",
        description="Late bull market, potential top",
        signal_multiplier=0.7,
        characteristics={"volatility": "high", "volume": "extreme", "trend": "up_parabolic"},
    ),
    4: RegimeInfo(
        regime_id=4,
        name="distribution",
        description="Distribution phase, smart money selling",
        signal_multiplier=0.5,
        characteristics={"volatility": "increasing", "volume": "high", "trend": "sideways"},
    ),
    5: RegimeInfo(
        regime_id=5,
        name="bear",
        description="Bear market, downtrend",
        signal_multiplier=0.8,
        characteristics={"volatility": "high", "volume": "decreasing", "trend": "down"},
    ),
}


class MarketRegimeDetector:
    """Detects market regimes using KMeans clustering.

    Identifies 6 market regimes: deep_accumulation, early_bull, mid_bull,
    late_bull, distribution, bear.
    """

    def __init__(
        self,
        model_path: Path | None = None,
        n_clusters: int = 6,
        random_state: int = 42,
    ) -> None:
        """Initialize the detector.

        Args:
            model_path: Path to save/load the trained model
            n_clusters: Number of regime clusters
            random_state: Random seed for reproducibility
        """
        self.model_path = model_path or Path("models/regime_detector.joblib")
        self.n_clusters = n_clusters
        self.random_state = random_state
        self._model: KMeans | None = None
        self._scaler: StandardScaler | None = None
        self._current_regime: int | None = None
        self._regime_history: list[tuple[str, int]] = []

    def train(
        self,
        X: pd.DataFrame,
        feature_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """Train the KMeans model for regime detection.

        Args:
            X: Feature matrix with market indicators
            feature_names: Optional list of feature names

        Returns:
            Training results including cluster centers
        """
        if feature_names is None:
            feature_names = X.columns.tolist()

        # Scale features
        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        # Train KMeans
        self._model = KMeans(
            n_clusters=self.n_clusters,
            random_state=self.random_state,
            n_init=10,
        )
        self._model.fit(X_scaled)

        # Save model and scaler
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self._model, "scaler": self._scaler}, self.model_path)

        # Compute cluster statistics
        cluster_counts = pd.Series(self._model.labels_).value_counts().to_dict()

        logger.info(
            "regime_model_trained",
            n_clusters=self.n_clusters,
            samples=len(X),
            cluster_distribution=cluster_counts,
        )

        return {
            "n_clusters": self.n_clusters,
            "cluster_centers": self._model.cluster_centers_.tolist(),
            "cluster_counts": cluster_counts,
            "trained_at": datetime.now(timezone.utc).isoformat(),
        }

    def load_model(self) -> bool:
        """Load a previously trained model.

        Returns:
            True if model loaded successfully
        """
        if not self.model_path.exists():
            logger.warning("regime_model_not_found", path=str(self.model_path))
            return False

        try:
            data = joblib.load(self.model_path)
            self._model = data["model"]
            self._scaler = data["scaler"]
            logger.info("regime_model_loaded", path=str(self.model_path))
            return True
        except Exception as e:
            logger.error("regime_model_load_error", error=str(e))
            return False

    def detect(self, features: np.ndarray | pd.DataFrame) -> RegimeInfo:
        """Detect current market regime.

        Args:
            features: Feature vector for current market state

        Returns:
            RegimeInfo for detected regime
        """
        if self._model is None or self._scaler is None:
            raise RuntimeError("Model not trained or loaded")

        # Ensure 2D array
        if isinstance(features, pd.DataFrame):
            features = features.values
        if features.ndim == 1:
            features = features.reshape(1, -1)

        # Scale and predict
        features_scaled = self._scaler.transform(features)
        regime_id = int(self._model.predict(features_scaled)[0])

        self._current_regime = regime_id
        self._regime_history.append((datetime.now(timezone.utc).isoformat(), regime_id))

        return REGIME_DEFINITIONS.get(regime_id, REGIME_DEFINITIONS[0])

    def get_signal_multiplier(self) -> float:
        """Get signal multiplier for current regime.

        Returns:
            Signal multiplier (0.5 to 1.5)
        """
        if self._current_regime is None:
            return 1.0

        regime = REGIME_DEFINITIONS.get(self._current_regime)
        return regime.signal_multiplier if regime else 1.0

    def get_current_regime(self) -> RegimeInfo | None:
        """Get current regime info.

        Returns:
            Current RegimeInfo or None
        """
        if self._current_regime is None:
            return None
        return REGIME_DEFINITIONS.get(self._current_regime)

    def get_regime_history(self, limit: int = 100) -> list[tuple[str, int]]:
        """Get recent regime history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of (timestamp, regime_id) tuples
        """
        return self._regime_history[-limit:]

    def save_analysis(self, path: Path | None = None) -> None:
        """Save regime analysis to JSON.

        Args:
            path: Optional path to save results
        """
        save_path = path or self.model_path.with_suffix(".json")
        data = {
            "current_regime": self._current_regime,
            "current_regime_name": (
                REGIME_DEFINITIONS[self._current_regime].name
                if self._current_regime is not None
                else None
            ),
            "signal_multiplier": self.get_signal_multiplier(),
            "regime_history": self._regime_history[-100:],
            "regime_definitions": {
                rid: {
                    "name": r.name,
                    "description": r.description,
                    "signal_multiplier": r.signal_multiplier,
                }
                for rid, r in REGIME_DEFINITIONS.items()
            },
        }

        with open(save_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info("regime_analysis_saved", path=str(save_path))

    def get_stats(self) -> dict[str, Any]:
        """Get detector statistics.

        Returns:
            Dict with detector stats
        """
        return {
            "model_loaded": self._model is not None,
            "current_regime": self._current_regime,
            "current_regime_name": (
                REGIME_DEFINITIONS[self._current_regime].name
                if self._current_regime is not None
                else None
            ),
            "signal_multiplier": self.get_signal_multiplier(),
            "history_entries": len(self._regime_history),
        }
