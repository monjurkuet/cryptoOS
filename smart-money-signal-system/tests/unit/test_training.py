"""Unit tests for OfflineTrainer training pipeline."""

import pytest
import time
import numpy as np
from unittest.mock import MagicMock, patch

from signal_system.rl.outcome_tracker import SignalOutcome
from signal_system.rl.training import OfflineTrainer, TrainingResult


def make_outcome(i: int, pnl: float = 0.01, action: str = "BUY") -> SignalOutcome:
    """Helper to create a SignalOutcome with correct fields."""
    now = time.time()
    return SignalOutcome(
        signal_id=f"sig_{i}",
        action=action,
        confidence=0.6,
        entry_price=60000.0,
        exit_price=60000.0 * (1 + pnl),
        pnl_pct=pnl,
        horizon_seconds=60,
        timestamp=now - 120,
        resolved_at=now,
    )


class TestTrainingResult:
    def test_creation(self):
        result = TrainingResult(
            episodes=10,
            total_steps=100,
            mean_reward=0.05,
            mean_policy_loss=-0.01,
            mean_value_loss=0.02,
            final_params={"bias_threshold": 0.2, "conf_scale": 1.0, "min_confidence": 0.3},
        )
        assert result.episodes == 10
        assert result.total_steps == 100

    def test_to_dict(self):
        result = TrainingResult(
            episodes=5,
            total_steps=50,
            mean_reward=0.03,
            mean_policy_loss=-0.005,
            mean_value_loss=0.01,
            final_params={"bias_threshold": 0.25, "conf_scale": 1.1, "min_confidence": 0.35},
        )
        d = result.to_dict()
        assert d["episodes"] == 5
        assert "final_params" in d


class TestOfflineTrainer:
    def test_creation(self):
        trainer = OfflineTrainer()
        assert trainer is not None

    def test_creation_with_overrides(self):
        trainer = OfflineTrainer(
            episodes=5,
            max_steps_per_episode=50,
            lr=1e-4,
        )
        assert trainer._episodes == 5
        assert trainer._max_steps == 50

    def test_train_with_outcomes(self):
        """Training completes and returns a TrainingResult."""
        trainer = OfflineTrainer(episodes=2, max_steps_per_episode=10, batch_size=4, update_epochs=1)
        outcomes = [make_outcome(i, pnl=0.01 + i * 0.001) for i in range(20)]
        result = trainer.train(outcomes)
        assert isinstance(result, TrainingResult)
        assert result.episodes == 2
        assert result.total_steps > 0
        assert isinstance(result.final_params, dict)

    def test_train_with_empty_outcomes(self):
        """Training with empty outcomes still returns a result."""
        trainer = OfflineTrainer(episodes=1, max_steps_per_episode=5)
        result = trainer.train([])
        assert result.episodes == 1
        assert result.mean_reward == 0.0

    def test_train_updates_agent_params(self):
        """Training produces valid parameter ranges."""
        trainer = OfflineTrainer(episodes=3, max_steps_per_episode=20, batch_size=4, update_epochs=2)
        outcomes = [make_outcome(i, pnl=0.05, action="BUY") for i in range(30)]
        result = trainer.train(outcomes)
        params = result.final_params
        assert 0.05 <= params["bias_threshold"] <= 0.8
        assert 0.1 <= params["conf_scale"] <= 3.0
        assert 0.05 <= params["min_confidence"] <= 0.9

    def test_save_model_after_training(self, tmp_path):
        """Model can be saved after training."""
        trainer = OfflineTrainer(episodes=2, max_steps_per_episode=10, batch_size=4, update_epochs=1)
        outcomes = [make_outcome(i, pnl=0.01) for i in range(10)]
        trainer.train(outcomes)
        model_path = str(tmp_path / "trained_model.pt")
        trainer.save_model(model_path)
        import os
        assert os.path.exists(model_path)
