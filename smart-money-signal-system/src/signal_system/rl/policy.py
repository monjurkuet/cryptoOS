"""PPO Actor-Critic network and PPOAgent for signal optimization.

Implements Proximal Policy Optimization (PPO) with:
- Shared encoder + separate actor/critic heads
- Generalized Advantage Estimation (GAE)
- Clipped surrogate objective
- Value function clipping
"""

from __future__ import annotations


import numpy as np
import structlog
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Categorical

from signal_system.rl.environment import (
    DEFAULT_BIAS_THRESHOLD,
    DEFAULT_CONF_SCALE,
    DEFAULT_MIN_CONFIDENCE,
)

logger = structlog.get_logger(__name__)


class ActorCritic(nn.Module):
    """Shared feature extractor with actor and critic heads.

    Architecture:
        encoder: obs_dim -> 128 -> 128 (shared)
        actor:   128 -> action_dim (policy logits)
        critic:  128 -> 1 (state value)
    """

    def __init__(
        self,
        obs_dim: int = 12,
        action_dim: int = 7,
        hidden_dim: int = 128,
    ) -> None:
        super().__init__()

        self.encoder = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )

        self.actor = nn.Sequential(
            nn.Linear(hidden_dim, action_dim),
        )

        self.critic = nn.Sequential(
            nn.Linear(hidden_dim, 1),
        )

    def forward(
        self, obs: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Forward pass.

        Args:
            obs: Observation tensor (batch_size, obs_dim)

        Returns:
            Tuple of (action_probs, value, log_probs)
        """
        features = self.encoder(obs)
        action_logits = self.actor(features)
        action_probs = torch.softmax(action_logits, dim=-1)
        log_probs = torch.log_softmax(action_logits, dim=-1)
        value = self.critic(features)
        return action_probs, value, log_probs

    def get_action(
        self, obs: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Sample an action and return its log probability and value.

        Args:
            obs: Observation tensor (1, obs_dim)

        Returns:
            Tuple of (action, log_prob, value)
        """
        action_probs, value, log_probs = self.forward(obs)
        dist = Categorical(action_probs)
        action = dist.sample()
        log_prob = dist.log_prob(action)
        return action, log_prob, value.squeeze(-1)


class PPOAgent:
    """PPO agent for signal parameter optimization.

    Manages experience collection, advantage estimation, and
    periodic policy updates using clipped surrogate loss.
    """

    def __init__(
        self,
        obs_dim: int = 12,
        action_dim: int = 7,
        hidden_dim: int = 128,
        lr: float = 3e-4,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_epsilon: float = 0.2,
        value_coeff: float = 0.5,
        entropy_coeff: float = 0.01,
        batch_size: int = 32,
        update_epochs: int = 4,
        max_grad_norm: float = 0.5,
    ) -> None:
        self._obs_dim = obs_dim
        self._action_dim = action_dim
        self._gamma = gamma
        self._gae_lambda = gae_lambda
        self._clip_epsilon = clip_epsilon
        self._value_coeff = value_coeff
        self._entropy_coeff = entropy_coeff
        self._batch_size = batch_size
        self._update_epochs = update_epochs
        self._max_grad_norm = max_grad_norm

        self._model = ActorCritic(obs_dim, action_dim, hidden_dim)
        self._optimizer = optim.Adam(self._model.parameters(), lr=lr)

        # Experience buffer
        self._observations: list[np.ndarray] = []
        self._actions: list[int] = []
        self._log_probs: list[float] = []
        self._values: list[float] = []
        self._rewards: list[float] = []
        self._dones: list[bool] = []

        # Current adjustable signal parameters
        self._bias_threshold = DEFAULT_BIAS_THRESHOLD
        self._conf_scale = DEFAULT_CONF_SCALE
        self._min_confidence = DEFAULT_MIN_CONFIDENCE

    def select_action(
        self, obs: np.ndarray
    ) -> tuple[int, float, float]:
        """Select an action given an observation.

        Args:
            obs: Observation vector (obs_dim,)

        Returns:
            Tuple of (action, log_prob, value)
        """
        obs_t = torch.FloatTensor(obs).unsqueeze(0)
        with torch.no_grad():
            action, log_prob, value = self._model.get_action(obs_t)
        return action.item(), log_prob.item(), value.item()

    def store_transition(
        self,
        obs: np.ndarray,
        action: int,
        log_prob: float,
        value: float,
        reward: float,
        done: bool,
    ) -> None:
        """Store a transition in the experience buffer.

        Args:
            obs: Observation
            action: Action taken
            log_prob: Log probability of action
            value: Value estimate
            reward: Reward received
            done: Whether episode ended
        """
        self._observations.append(obs)
        self._actions.append(action)
        self._log_probs.append(log_prob)
        self._values.append(value)
        self._rewards.append(reward)
        self._dones.append(done)

    def update(self) -> dict[str, float]:
        """Update the policy using collected experience.

        Returns:
            Dict with training metrics
        """
        if len(self._observations) < self._batch_size:
            logger.debug("ppo_skip_update", buffer=len(self._observations))
            return {}

        # Convert buffers to tensors
        obs_t = torch.FloatTensor(np.array(self._observations))
        actions_t = torch.LongTensor(self._actions)
        old_log_probs_t = torch.FloatTensor(self._log_probs)
        old_values_t = torch.FloatTensor(self._values)
        rewards_t = torch.FloatTensor(self._rewards)
        dones_t = torch.FloatTensor([float(d) for d in self._dones])

        # Compute advantages using GAE
        advantages = self._compute_gae(rewards_t, old_values_t, dones_t)
        returns = advantages + old_values_t

        # Normalize advantages
        if len(advantages) > 1:
            advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # PPO update
        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        n_updates = 0

        for _ in range(self._update_epochs):
            # Get current policy outputs
            action_probs, values, log_probs = self._model(obs_t)
            values = values.squeeze(-1)

            dist = Categorical(action_probs)
            new_log_probs = dist.log_prob(actions_t)
            entropy = dist.entropy().mean()

            # Clipped surrogate loss
            ratio = torch.exp(new_log_probs - old_log_probs_t)
            surr1 = ratio * advantages
            surr2 = torch.clamp(
                ratio, 1 - self._clip_epsilon, 1 + self._clip_epsilon
            ) * advantages
            policy_loss = -torch.min(surr1, surr2).mean()

            # Value loss
            value_loss = nn.MSELoss()(values, returns)

            # Total loss
            loss = (
                policy_loss
                + self._value_coeff * value_loss
                - self._entropy_coeff * entropy
            )

            self._optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self._model.parameters(), self._max_grad_norm)
            self._optimizer.step()

            total_policy_loss += policy_loss.item()
            total_value_loss += value_loss.item()
            total_entropy += entropy.item()
            n_updates += 1

        # Clear buffers
        self._clear_buffers()

        # Update signal parameters based on latest action
        if self._actions:
            last_action = self._actions[-1] if self._actions else 6
            self._apply_action_to_params(last_action)

        metrics = {
            "policy_loss": total_policy_loss / max(n_updates, 1),
            "value_loss": total_value_loss / max(n_updates, 1),
            "entropy": total_entropy / max(n_updates, 1),
        }

        logger.debug("ppo_update", **metrics)
        return metrics

    def _compute_gae(
        self,
        rewards: torch.Tensor,
        values: torch.Tensor,
        dones: torch.Tensor,
    ) -> torch.Tensor:
        """Compute Generalized Advantage Estimation.

        Args:
            rewards: Reward tensor
            values: Value estimates tensor
            dones: Done flags tensor

        Returns:
            Advantages tensor
        """
        advantages = torch.zeros_like(rewards)
        last_advantage = 0.0

        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                next_value = 0.0
            else:
                next_value = values[t + 1].item()

            delta = rewards[t].item() + self._gamma * next_value * (1 - dones[t].item()) - values[t].item()
            last_advantage = delta + self._gamma * self._gae_lambda * (1 - dones[t].item()) * last_advantage
            advantages[t] = last_advantage

        return advantages

    def _apply_action_to_params(self, action: int) -> None:
        """Apply last action to update signal parameters."""
        if action == 0:
            self._bias_threshold = max(0.05, self._bias_threshold - 0.05)
        elif action == 1:
            self._bias_threshold = min(0.8, self._bias_threshold + 0.05)
        elif action == 2:
            self._conf_scale = max(0.1, self._conf_scale - 0.1)
        elif action == 3:
            self._conf_scale = min(3.0, self._conf_scale + 0.1)
        elif action == 4:
            self._min_confidence = max(0.05, self._min_confidence - 0.05)
        elif action == 5:
            self._min_confidence = min(0.9, self._min_confidence + 0.05)

    def _clear_buffers(self) -> None:
        """Clear experience buffers."""
        self._observations.clear()
        self._actions.clear()
        self._log_probs.clear()
        self._values.clear()
        self._rewards.clear()
        self._dones.clear()

    def get_params(self) -> dict[str, float]:
        """Get current RL-adjusted signal parameters.

        Returns:
            Dict with bias_threshold, conf_scale, min_confidence
        """
        return {
            "bias_threshold": self._bias_threshold,
            "conf_scale": self._conf_scale,
            "min_confidence": self._min_confidence,
        }

    def save(self, path: str) -> None:
        """Save model and parameters to file.

        Args:
            path: File path for saving
        """
        torch.save({
            "model_state": self._model.state_dict(),
            "optimizer_state": self._optimizer.state_dict(),
            "params": self.get_params(),
        }, path)
        logger.info("ppo_model_saved", path=path)

    def load(self, path: str) -> None:
        """Load model and parameters from file.

        Args:
            path: File path to load from
        """
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        self._model.load_state_dict(checkpoint["model_state"])
        self._optimizer.load_state_dict(checkpoint["optimizer_state"])
        if "params" in checkpoint:
            self._bias_threshold = checkpoint["params"]["bias_threshold"]
            self._conf_scale = checkpoint["params"]["conf_scale"]
            self._min_confidence = checkpoint["params"]["min_confidence"]
        logger.info("ppo_model_loaded", path=path)
