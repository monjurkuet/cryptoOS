"""Gymnasium environment for signal parameter optimization.

The agent observes recent signal outcomes and current market state,
then adjusts signal generation parameters (bias threshold, confidence
scaling, etc.) to maximize future signal quality (reward = PnL).

Observation space (12-dim):
  [0] recent_avg_pnl       - average PnL of last N resolved outcomes
  [1] recent_pnl_std       - std of PnL of last N outcomes
  [2] recent_win_rate      - fraction of positive PnL outcomes
  [3] recent_signal_count   - number of recent outcomes
  [4] current_bias_threshold - current BUY/SELL threshold
  [5] current_conf_scale   - current confidence scaling factor
  [6] current_net_bias     - net bias of current signal (if any)
  [7] current_confidence   - confidence of current signal (if any)
  [8] buy_outcome_ratio    - ratio of BUY outcomes in recent window
  [9] sell_outcome_ratio   - ratio of SELL outcomes in recent window
  [10] avg_horizon_pnl_1m  - avg PnL at 1-min horizon
  [11] avg_horizon_pnl_5m  - avg PnL at 5-min horizon

Action space (Discrete(7)):
  0 = decrease bias threshold by 0.05
  1 = increase bias threshold by 0.05
  2 = decrease confidence scale by 0.1
  3 = increase confidence scale by 0.1
  4 = decrease min confidence by 0.05
  5 = increase min confidence by 0.05
  6 = no change
"""

from __future__ import annotations

from collections import deque
from typing import Any

import gymnasium
import numpy as np
from gymnasium import spaces

import structlog

from signal_system.rl.outcome_tracker import SignalOutcome

logger = structlog.get_logger(__name__)

# Observation vector size
OBS_SIZE = 12

# Defaults
DEFAULT_BIAS_THRESHOLD = 0.2
DEFAULT_CONF_SCALE = 1.0
DEFAULT_MIN_CONFIDENCE = 0.3

# Action meanings
ACTION_MEANINGS = {
    0: "decrease_bias_threshold",
    1: "increase_bias_threshold",
    2: "decrease_conf_scale",
    3: "increase_conf_scale",
    4: "decrease_min_confidence",
    5: "increase_min_confidence",
    6: "no_change",
}


class SignalOptEnv(gymnasium.Env):
    """Gymnasium environment for RL-based signal parameter optimization.

    The agent adjusts signal generation parameters based on historical
    outcome data to maximize signal PnL.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        max_steps: int = 100,
        recent_window: int = 50,
        bias_threshold: float = DEFAULT_BIAS_THRESHOLD,
        conf_scale: float = DEFAULT_CONF_SCALE,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        super().__init__()

        self.max_steps = max_steps
        self._recent_window = recent_window

        # Adjustable parameters
        self.bias_threshold = bias_threshold
        self.conf_scale = conf_scale
        self.min_confidence = min_confidence

        # Spaces
        self.observation_space = spaces.Box(
            low=-5.0, high=5.0, shape=(OBS_SIZE,), dtype=np.float32,
        )
        self.action_space = spaces.Discrete(7)

        # Internal state
        self._recent_outcomes: deque[SignalOutcome] = deque(maxlen=recent_window)
        self._current_signal: dict[str, Any] = {}
        self._step_count = 0

    def reset(
        self, seed: int | None = None, options: dict | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Reset the environment.

        Returns:
            Tuple of (observation, info)
        """
        super().reset(seed=seed)
        self._step_count = 0

        obs = self._get_obs()
        info = {
            "bias_threshold": self.bias_threshold,
            "conf_scale": self.conf_scale,
            "min_confidence": self.min_confidence,
        }
        return obs, info

    def step(
        self, action: int
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """Take a step in the environment.

        Args:
            action: Action index (0-6)

        Returns:
            Tuple of (observation, reward, terminated, truncated, info)
        """
        self._apply_action(action)
        self._step_count += 1

        reward = self._compute_reward()
        obs = self._get_obs()

        terminated = False
        truncated = self._step_count >= self.max_steps

        info = {
            "bias_threshold": self.bias_threshold,
            "conf_scale": self.conf_scale,
            "min_confidence": self.min_confidence,
            "step": self._step_count,
            "action": ACTION_MEANINGS.get(action, "unknown"),
        }

        return obs, reward, terminated, truncated, info

    def feed_outcome(self, outcome: SignalOutcome) -> None:
        """Feed a real signal outcome into the environment.

        This is called by the live system when a signal is resolved,
        providing the agent with up-to-date performance data.

        Args:
            outcome: A resolved signal outcome
        """
        self._recent_outcomes.append(outcome)

    def set_current_signal(self, signal: dict[str, Any]) -> None:
        """Set the current signal context.

        Args:
            signal: Current signal dict with 'action', 'confidence', 'net_bias'
        """
        self._current_signal = signal

    def get_params(self) -> dict[str, float]:
        """Get current RL-adjusted signal parameters.

        Returns:
            Dict of current parameter values
        """
        return {
            "bias_threshold": self.bias_threshold,
            "conf_scale": self.conf_scale,
            "min_confidence": self.min_confidence,
        }

    def _apply_action(self, action: int) -> None:
        """Apply action to adjust signal parameters."""
        if action == 0:
            self.bias_threshold = max(0.05, self.bias_threshold - 0.05)
        elif action == 1:
            self.bias_threshold = min(0.8, self.bias_threshold + 0.05)
        elif action == 2:
            self.conf_scale = max(0.1, self.conf_scale - 0.1)
        elif action == 3:
            self.conf_scale = min(3.0, self.conf_scale + 0.1)
        elif action == 4:
            self.min_confidence = max(0.05, self.min_confidence - 0.05)
        elif action == 5:
            self.min_confidence = min(0.9, self.min_confidence + 0.05)
        # action 6 = no change

    def _compute_reward(self) -> float:
        """Compute reward from recent outcomes.

        Reward is the average PnL of recent outcomes, with a penalty
        for low signal count (encouraging the agent to not be too restrictive).
        """
        if not self._recent_outcomes:
            return 0.0

        outcomes = list(self._recent_outcomes)
        pnls = [o.pnl_pct for o in outcomes]
        avg_pnl = np.mean(pnls)

        # Small penalty if very few outcomes (too restrictive)
        count_penalty = 0.0
        if len(outcomes) < 5:
            count_penalty = -0.001 * (5 - len(outcomes))

        return float(avg_pnl + count_penalty)

    def _get_obs(self) -> np.ndarray:
        """Build observation vector from current state."""
        outcomes = list(self._recent_outcomes)
        pnls = [o.pnl_pct for o in outcomes] if outcomes else [0.0]

        buy_outcomes = [o for o in outcomes if o.action == "BUY"]
        sell_outcomes = [o for o in outcomes if o.action == "SELL"]
        winning = [o for o in outcomes if o.pnl_pct > 0]

        # Per-horizon PnL
        horizon_1m = [o for o in outcomes if o.horizon_seconds <= 60]
        horizon_5m = [o for o in outcomes if 60 < o.horizon_seconds <= 300]

        obs = np.array([
            float(np.mean(pnls)),                                          # 0: recent_avg_pnl
            float(np.std(pnls)) if len(pnls) > 1 else 0.0,                # 1: recent_pnl_std
            len(winning) / len(outcomes) if outcomes else 0.0,            # 2: recent_win_rate
            min(len(outcomes) / self._recent_window, 1.0),                # 3: recent_signal_count (normalized)
            self.bias_threshold,                                           # 4: current_bias_threshold
            self.conf_scale,                                               # 5: current_conf_scale
            float(self._current_signal.get("net_bias", 0.0)),             # 6: current_net_bias
            float(self._current_signal.get("confidence", 0.0)),           # 7: current_confidence
            len(buy_outcomes) / len(outcomes) if outcomes else 0.5,       # 8: buy_outcome_ratio
            len(sell_outcomes) / len(outcomes) if outcomes else 0.5,      # 9: sell_outcome_ratio
            float(np.mean([o.pnl_pct for o in horizon_1m])) if horizon_1m else 0.0,  # 10: avg_horizon_pnl_1m
            float(np.mean([o.pnl_pct for o in horizon_5m])) if horizon_5m else 0.0,  # 11: avg_horizon_pnl_5m
        ], dtype=np.float32)

        # Clip to observation space bounds
        obs = np.clip(obs, self.observation_space.low, self.observation_space.high)

        return obs
