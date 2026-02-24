"""Feature Importance Analyzer using RandomForest."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import structlog
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

logger = structlog.get_logger(__name__)


@dataclass
class FeatureImportanceResult:
    """Result of feature importance analysis."""

    feature_names: list[str]
    importances: list[float]
    ranked_features: list[tuple[str, float]]
    cross_val_score: float
    trained_at: str


class FeatureImportanceAnalyzer:
    """Analyzes feature importance using RandomForest.

    Discovers which trader metrics are most predictive of profitable trades.
    """

    def __init__(
        self,
        model_path: Path | None = None,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> None:
        """Initialize the analyzer.

        Args:
            model_path: Path to save/load the trained model
            n_estimators: Number of trees in the forest
            random_state: Random seed for reproducibility
        """
        self.model_path = model_path or Path("models/feature_importance.joblib")
        self.n_estimators = n_estimators
        self.random_state = random_state
        self._model: RandomForestClassifier | None = None
        self._last_result: FeatureImportanceResult | None = None

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        feature_names: list[str] | None = None,
    ) -> FeatureImportanceResult:
        """Train the RandomForest model and compute feature importance.

        Args:
            X: Feature matrix
            y: Target labels (1 for profitable, 0 for unprofitable)
            feature_names: Optional list of feature names

        Returns:
            FeatureImportanceResult with importance scores
        """
        if feature_names is None:
            feature_names = X.columns.tolist()

        # Train model
        self._model = RandomForestClassifier(
            n_estimators=self.n_estimators,
            random_state=self.random_state,
            n_jobs=-1,
        )
        self._model.fit(X, y)

        # Get feature importance
        importances = self._model.feature_importances_.tolist()

        # Rank features
        ranked = sorted(
            zip(feature_names, importances),
            key=lambda x: x[1],
            reverse=True,
        )

        # Cross-validation score
        cv_scores = cross_val_score(self._model, X, y, cv=5, scoring="accuracy")

        result = FeatureImportanceResult(
            feature_names=feature_names,
            importances=importances,
            ranked_features=ranked,
            cross_val_score=float(cv_scores.mean()),
            trained_at=datetime.now(timezone.utc).isoformat(),
        )

        self._last_result = result

        # Save model
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._model, self.model_path)
        logger.info(
            "model_trained",
            features=len(feature_names),
            cv_score=result.cross_val_score,
            top_feature=ranked[0][0] if ranked else None,
        )

        return result

    def load_model(self) -> bool:
        """Load a previously trained model.

        Returns:
            True if model loaded successfully
        """
        if not self.model_path.exists():
            logger.warning("model_not_found", path=str(self.model_path))
            return False

        try:
            self._model = joblib.load(self.model_path)
            logger.info("model_loaded", path=str(self.model_path))
            return True
        except Exception as e:
            logger.error("model_load_error", error=str(e))
            return False

    def get_top_features(self, n: int = 10) -> list[tuple[str, float]]:
        """Get top N most important features.

        Args:
            n: Number of top features to return

        Returns:
            List of (feature_name, importance) tuples
        """
        if self._last_result is None:
            return []
        return self._last_result.ranked_features[:n]

    def get_feature_weights(self) -> dict[str, float]:
        """Get normalized feature weights for use in weighting engine.

        Returns:
            Dict mapping feature name to normalized weight
        """
        if self._last_result is None:
            return {}

        total = sum(self._last_result.importances)
        if total == 0:
            return {name: 1.0 / len(self._last_result.feature_names)
                    for name in self._last_result.feature_names}

        return {
            name: imp / total
            for name, imp in zip(self._last_result.feature_names, self._last_result.importances)
        }

    def save_analysis(self, path: Path | None = None) -> None:
        """Save analysis results to JSON.

        Args:
            path: Optional path to save results
        """
        if self._last_result is None:
            return

        save_path = path or self.model_path.with_suffix(".json")
        data = {
            "feature_names": self._last_result.feature_names,
            "importances": self._last_result.importances,
            "ranked_features": self._last_result.ranked_features,
            "cross_val_score": self._last_result.cross_val_score,
            "trained_at": self._last_result.trained_at,
        }

        with open(save_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info("analysis_saved", path=str(save_path))

    def get_stats(self) -> dict[str, Any]:
        """Get analyzer statistics.

        Returns:
            Dict with analyzer stats
        """
        return {
            "model_loaded": self._model is not None,
            "last_trained": self._last_result.trained_at if self._last_result else None,
            "n_features": len(self._last_result.feature_names) if self._last_result else 0,
            "cv_score": self._last_result.cross_val_score if self._last_result else None,
        }
