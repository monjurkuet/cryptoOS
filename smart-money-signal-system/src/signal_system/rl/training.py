"""Offline training pipeline for PPO signal optimization.

Loads historical signal outcomes from OutcomeStore, replays them
through the SignalOptEnv, and trains the PPOAgent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import structlog

from signal_system.rl.environment import SignalOptEnv
from signal_system.rl.outcome_tracker import SignalOutcome
from signal_system.rl.policy import PPOAgent

logger = structlog.get_logger(__name__)


@dataclass
class TrainingResult:
    """Result of a training run."""

    episodes: int
    total_steps: int
    mean_reward: float
    mean_policy_loss: float
    mean_value_loss: float
    final_params: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "episodes": self.episodes,
            "total_steps": self.total_steps,
            "mean_reward": self.mean_reward,
            "mean_policy_loss": self.mean_policy_loss,
            "mean_value_loss": self.mean_value_loss,
            "final_params": self.final_params,
        }


class OfflineTrainer:
    """Train PPO agent on historical signal outcomes.

    Replays resolved outcomes through the SignalOptEnv, feeding them
    as observations so the agent learns to adjust signal parameters
    based on past performance.
    """

    def __init__(
        self,
        episodes: int = 10,
        max_steps_per_episode: int = 100,
        obs_dim: int = 12,
        action_dim: int = 7,
        hidden_dim: int = 128,
        lr: float = 3e-4,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_epsilon: float = 0.2,
        batch_size: int = 32,
        update_epochs: int = 4,
        recent_window: int = 50,
    ) -> None:
        self._episodes = episodes
        self._max_steps = max_steps_per_episode

        self._env = SignalOptEnv(
            max_steps=max_steps_per_episode,
            recent_window=recent_window,
        )
        self._agent = PPOAgent(
            obs_dim=obs_dim,
            action_dim=action_dim,
            hidden_dim=hidden_dim,
            lr=lr,
            gamma=gamma,
            gae_lambda=gae_lambda,
            clip_epsilon=clip_epsilon,
            batch_size=batch_size,
            update_epochs=update_epochs,
        )

    def train(self, outcomes: list[SignalOutcome]) -> TrainingResult:
        """Run offline training on historical outcomes.

        Args:
            outcomes: List of resolved signal outcomes from OutcomeStore

        Returns:
            TrainingResult with metrics
        """
        # Feed all outcomes into the environment so observations are meaningful
        for outcome in outcomes:
            self._env.feed_outcome(outcome)

        total_rewards = []
        total_policy_losses = []
        total_value_losses = []
        total_steps = 0

        for ep in range(self._episodes):
            obs, info = self._env.reset()
            # Re-feed outcomes after reset (reset clears step counter but keeps outcomes)
            for outcome in outcomes:
                self._env.feed_outcome(outcome)

            episode_reward = 0.0
            done = False

            while not done:
                # Select action
                action, log_prob, value = self._agent.select_action(obs)

                # Step environment
                next_obs, reward, terminated, truncated, info = self._env.step(action)
                episode_reward += reward
                total_steps += 1

                # Store transition
                self._agent.store_transition(
                    obs, action, log_prob, value, reward, terminated or truncated,
                )

                # Update if enough data
                if len(self._agent._observations) >= self._agent._batch_size:
                    metrics = self._agent.update()
                    if metrics:
                        total_policy_losses.append(metrics.get("policy_loss", 0.0))
                        total_value_losses.append(metrics.get("value_loss", 0.0))

                obs = next_obs
                done = terminated or truncated

            total_rewards.append(episode_reward)

        # Final update for remaining buffer
        final_metrics = self._agent.update()
        if final_metrics:
            total_policy_losses.append(final_metrics.get("policy_loss", 0.0))
            total_value_losses.append(final_metrics.get("value_loss", 0.0))

        # Sync env params from agent params
        agent_params = self._agent.get_params()

        result = TrainingResult(
            episodes=self._episodes,
            total_steps=total_steps,
            mean_reward=float(np.mean(total_rewards)) if total_rewards else 0.0,
            mean_policy_loss=float(np.mean(total_policy_losses)) if total_policy_losses else 0.0,
            mean_value_loss=float(np.mean(total_value_losses)) if total_value_losses else 0.0,
            final_params=agent_params,
        )

        logger.info(
            "offline_training_complete",
            episodes=result.episodes,
            total_steps=result.total_steps,
            mean_reward=result.mean_reward,
            final_params=result.final_params,
        )

        return result

    def save_model(self, path: str) -> None:
        """Save the trained PPO model.

        Args:
            path: File path for the model checkpoint
        """
        self._agent.save(path)
