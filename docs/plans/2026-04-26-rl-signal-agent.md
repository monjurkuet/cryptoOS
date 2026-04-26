# RL Signal Agent Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a PPO-based reinforcement learning agent that learns optimal signal generation parameters (thresholds, weighting coefficients, confidence scaling) from market rewards, replacing the current hardcoded heuristic approach.

**Architecture:** The RL agent wraps the existing signal generation pipeline as a Gymnasium environment. The agent's policy network observes market state (regime, trader distribution, price features) and outputs continuous actions that modulate signal generation parameters. A reward signal is computed from subsequent price moves after each signal. The agent trains offline on historical signal/price data and serves parameters online via a lightweight API, with periodic retraining.

**Tech Stack:** PyTorch (policy/critic networks), Gymnasium (environment interface), stable-baselines3 or custom PPO loop, Redis (existing event bus), MongoDB (signal/episode storage), numpy/pandas (feature prep)

---

## Phase 1: Signal Outcome Tracking (Reward Infrastructure)

Before any RL, we need to know whether past signals were profitable. This is the foundation -- no reward = no learning.

### Task 1: Create SignalOutcomeTracker

**Objective:** Track price movement after each signal to compute reward.

**Files:**
- Create: `src/signal_system/rl/outcome_tracker.py`
- Create: `tests/unit/test_outcome_tracker.py`

**Step 1: Write failing test**

```python
# tests/unit/test_outcome_tracker.py
import pytest
import time
from signal_system.rl.outcome_tracker import SignalOutcomeTracker, SignalOutcome


class TestSignalOutcomeTracker:
    def test_register_signal(self):
        tracker = SignalOutcomeTracker()
        tracker.register_signal("sig1", "BUY", 0.7, 50000.0)
        pending = tracker.get_pending_outcomes()
        assert len(pending) == 1
        assert pending[0].signal_id == "sig1"

    def test_update_price_resolves_outcomes(self):
        tracker = SignalOutcomeTracker(evaluation_horizons=[60])  # 60s horizon
        tracker.register_signal("sig1", "BUY", 0.7, 50000.0, timestamp=time.time() - 61)
        outcomes = tracker.update_price(50500.0)  # +1% price move
        assert len(outcomes) == 1
        assert outcomes[0].signal_id == "sig1"
        assert outcomes[0].pnl_pct > 0  # BUY + price up = profit

    def test_sell_signal_reward_negative_on_price_up(self):
        tracker = SignalOutcomeTracker(evaluation_horizons=[60])
        tracker.register_signal("sig1", "SELL", 0.7, 50000.0, timestamp=time.time() - 61)
        outcomes = tracker.update_price(50500.0)
        assert outcomes[0].pnl_pct < 0  # SELL + price up = loss

    def test_neutral_signal_zero_reward(self):
        tracker = SignalOutcomeTracker(evaluation_horizons=[60])
        tracker.register_signal("sig1", "NEUTRAL", 0.3, 50000.0, timestamp=time.time() - 61)
        outcomes = tracker.update_price(50500.0)
        assert outcomes[0].pnl_pct == 0.0

    def test_multiple_horizons(self):
        tracker = SignalOutcomeTracker(evaluation_horizons=[60, 300, 900])
        ts = time.time() - 301  # 5+ minutes old
        tracker.register_signal("sig1", "BUY", 0.7, 50000.0, timestamp=ts)
        outcomes = tracker.update_price(50750.0)
        assert len(outcomes) == 2  # resolved at 60s and 300s horizons

    def test_pending_cleanup(self):
        tracker = SignalOutcomeTracker(max_pending=3)
        for i in range(5):
            tracker.register_signal(f"sig{i}", "BUY", 0.5, 50000.0)
        pending = tracker.get_pending_outcomes()
        assert len(pending) <= 3
```

**Step 2: Run test to verify failure**

Run: `cd smart-money-signal-system && python -m pytest tests/unit/test_outcome_tracker.py -v`
Expected: FAIL -- module not found

**Step 3: Write implementation**

```python
# src/signal_system/rl/__init__.py
"""Reinforcement Learning components for signal optimization."""
```

```python
# src/signal_system/rl/outcome_tracker.py
"""Track signal outcomes for reward computation."""

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Default horizons: 1min, 5min, 15min, 1h
DEFAULT_HORIZONS = [60, 300, 900, 3600]


@dataclass
class SignalOutcome:
    """Outcome of a signal after evaluation."""

    signal_id: str
    action: str
    confidence: float
    entry_price: float
    exit_price: float
    pnl_pct: float
    horizon_seconds: int
    timestamp: float
    resolved_at: float


@dataclass
class PendingSignal:
    """A signal awaiting outcome evaluation."""

    signal_id: str
    action: str
    confidence: float
    entry_price: float
    timestamp: float
    resolved_horizons: set[int] = field(default_factory=set)


class SignalOutcomeTracker:
    """Tracks price movement after signals to compute reward.

    Registers signals with entry prices, then resolves them as price
    updates arrive and evaluation horizons expire.
    """

    def __init__(
        self,
        evaluation_horizons: list[int] | None = None,
        max_pending: int = 10000,
        max_outcomes: int = 50000,
    ) -> None:
        self._horizons = evaluation_horizons or DEFAULT_HORIZONS
        self._max_pending = max_pending
        self._pending: deque[PendingSignal] = deque(maxlen=max_pending)
        self._outcomes: deque[SignalOutcome] = deque(maxlen=max_outcomes)
        self._last_price: float | None = None

    def register_signal(
        self,
        signal_id: str | None,
        action: str,
        confidence: float,
        price: float,
        timestamp: float | None = None,
    ) -> str:
        sid = signal_id or str(uuid.uuid4())[:8]
        ts = timestamp or time.time()
        self._pending.append(PendingSignal(
            signal_id=sid,
            action=action,
            confidence=confidence,
            entry_price=price,
            timestamp=ts,
        ))
        logger.debug("signal_registered_for_tracking", signal_id=sid, action=action)
        return sid

    def update_price(self, price: float) -> list[SignalOutcome]:
        now = time.time()
        self._last_price = price
        resolved: list[SignalOutcome] = []

        for pending in list(self._pending):
            elapsed = now - pending.timestamp
            for horizon in self._horizons:
                if horizon in pending.resolved_horizons:
                    continue
                if elapsed >= horizon:
                    pnl = self._compute_pnl(pending.action, pending.entry_price, price)
                    outcome = SignalOutcome(
                        signal_id=pending.signal_id,
                        action=pending.action,
                        confidence=pending.confidence,
                        entry_price=pending.entry_price,
                        exit_price=price,
                        pnl_pct=pnl,
                        horizon_seconds=horizon,
                        timestamp=pending.timestamp,
                        resolved_at=now,
                    )
                    resolved.append(outcome)
                    self._outcomes.append(outcome)
                    pending.resolved_horizons.add(horizon)

        # Remove fully resolved signals
        self._pending = deque(
            [p for p in self._pending if len(p.resolved_horizons) < len(self._horizons)],
            maxlen=self._max_pending,
        )

        if resolved:
            logger.debug("outcomes_resolved", count=len(resolved))

        return resolved

    def _compute_pnl(self, action: str, entry: float, exit_price: float) -> float:
        if action == "NEUTRAL" or entry == 0:
            return 0.0
        price_change = (exit_price - entry) / entry
        return price_change if action == "BUY" else -price_change

    def get_pending_outcomes(self) -> list[PendingSignal]:
        return list(self._pending)

    def get_resolved_outcomes(self, limit: int = 1000) -> list[SignalOutcome]:
        return list(self._outcomes)[-limit:]

    def get_stats(self) -> dict[str, Any]:
        outcomes = list(self._outcomes)
        return {
            "pending_signals": len(self._pending),
            "resolved_outcomes": len(outcomes),
            "avg_pnl": sum(o.pnl_pct for o in outcomes) / len(outcomes) if outcomes else 0,
            "last_price": self._last_price,
        }
```

**Step 4: Run test to verify pass**

Run: `cd smart-money-signal-system && python -m pytest tests/unit/test_outcome_tracker.py -v`
Expected: 6 passed

**Step 5: Commit**

```bash
git add src/signal_system/rl/__init__.py src/signal_system/rl/outcome_tracker.py tests/unit/test_outcome_tracker.py
git commit -m "feat(rl): add SignalOutcomeTracker for reward computation"
```

---

### Task 2: Wire OutcomeTracker into EventProcessor

**Objective:** Connect the outcome tracker to the live signal pipeline so every generated signal is tracked.

**Files:**
- Modify: `src/signal_system/services/event_processor.py`
- Modify: `src/signal_system/__main__.py`

**Step 1: Write failing test**

```python
# tests/unit/test_event_processor_outcome.py
import pytest
import time
from unittest.mock import AsyncMock, MagicMock

from signal_system.rl.outcome_tracker import SignalOutcomeTracker
from signal_system.services.event_processor import EventProcessor
from signal_system.signal_generation.processor import SignalGenerationProcessor
from signal_system.signal_store import SignalStore
from signal_system.whale_alerts.detector import WhaleAlertDetector
from signal_system.config import SignalSystemSettings


class TestEventProcessorOutcomeTracking:
    @pytest.mark.asyncio
    async def test_outcome_tracker_receives_signals(self):
        processor = SignalGenerationProcessor()
        # Pre-populate so signal generates
        processor._trader_scores = {"0x1": 80}
        now = time.time()
        processor._trader_positions = {
            "0x1": ({"positions": [{"position": {"coin": "BTC", "szi": "10.0"}}]}, now),
        }

        whale = WhaleAlertDetector()
        store = SignalStore()
        settings = SignalSystemSettings()
        tracker = SignalOutcomeTracker()

        ep = EventProcessor(
            signal_processor=processor,
            whale_detector=whale,
            signal_store=store,
            settings=settings,
            outcome_tracker=tracker,
        )

        event = {
            "payload": {
                "address": "0x1",
                "accountValue": "5000000",
                "positions": [{"position": {"coin": "BTC", "szi": "10.0"}}],
            }
        }

        await ep.handle_position_event(event)
        pending = tracker.get_pending_outcomes()
        assert len(pending) >= 1
```

**Step 2: Run test to verify failure**

Run: `cd smart-money-signal-system && python -m pytest tests/unit/test_event_processor_outcome.py -v`
Expected: FAIL -- EventProcessor doesn't accept outcome_tracker

**Step 3: Implement**

In `event_processor.py`, add optional `outcome_tracker` param and call `register_signal` when a signal is generated. Also need to add `mark_price` event handler that calls `tracker.update_price()`.

In `__main__.py`, instantiate `SignalOutcomeTracker` and pass to `EventProcessor`, register a `mark_price` handler.

**Step 4: Run test to verify pass**

Run: `cd smart-money-signal-system && python -m pytest tests/unit/test_event_processor_outcome.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/signal_system/services/event_processor.py src/signal_system/__main__.py tests/unit/test_event_processor_outcome.py
git commit -m "feat(rl): wire outcome tracker into event pipeline"
```

---

### Task 3: Add Outcome Storage to MongoDB

**Objective:** Persist signal outcomes to MongoDB for offline training data.

**Files:**
- Create: `src/signal_system/rl/outcome_store.py`
- Create: `tests/unit/test_outcome_store.py`

**Step 1: Write failing test**

```python
# tests/unit/test_outcome_store.py
import pytest
from signal_system.rl.outcome_store import OutcomeStore
from signal_system.rl.outcome_tracker import SignalOutcome


class TestOutcomeStore:
    def test_store_and_retrieve(self):
        store = OutcomeStore(collection_name="test_outcomes")
        outcome = SignalOutcome(
            signal_id="sig1", action="BUY", confidence=0.7,
            entry_price=50000.0, exit_price=50500.0,
            pnl_pct=0.01, horizon_seconds=60,
            timestamp=1000.0, resolved_at=1060.0,
        )
        store.store(outcome)
        results = store.get_outcomes(limit=10)
        assert len(results) >= 1
        assert results[-1].signal_id == "sig1"

    def test_get_training_data(self):
        store = OutcomeStore(collection_name="test_outcomes")
        data = store.get_training_data(min_samples=1)
        assert "states" in data
        assert "rewards" in data
```

**Step 2-4: TDD cycle**

Implement OutcomeStore using pymongo (same pattern as market-scraper's MongoRepository). Store outcomes as documents. `get_training_data()` returns (states, actions, rewards) arrays for offline RL.

**Step 5: Commit**

```bash
git add src/signal_system/rl/outcome_store.py tests/unit/test_outcome_store.py
git commit -m "feat(rl): add MongoDB outcome storage"
```

---

## Phase 2: RL Environment (Gymnasium)

### Task 4: Create SignalOptEnv -- Gymnasium Environment

**Objective:** Wrap the signal generation pipeline as a Gymnasium environment where the agent controls signal parameters.

**Files:**
- Create: `src/signal_system/rl/environment.py`
- Create: `tests/unit/test_rl_environment.py`

**Step 1: Write failing test**

```python
# tests/unit/test_rl_environment.py
import pytest
import numpy as np
from signal_system.rl.environment import SignalOptEnv


class TestSignalOptEnv:
    def test_observation_space(self):
        env = SignalOptEnv()
        obs, info = env.reset()
        assert obs.shape == env.observation_space.shape
        assert env.observation_space.dtype == np.float32

    def test_action_space(self):
        env = SignalOptEnv()
        assert env.action_space.shape == (7,)  # 7 controllable params
        # All actions in [-1, 1]
        sample = env.action_space.sample()
        assert np.all(sample >= -1) and np.all(sample <= 1)

    def test_step_returns_tuple(self):
        env = SignalOptEnv()
        env.reset()
        action = env.action_space.sample()
        result = env.step(action)
        assert len(result) == 5  # obs, reward, terminated, truncated, info

    def test_reward_from_outcomes(self):
        env = SignalOptEnv()
        env.reset()
        # Simulate: provide a positive outcome, reward should be positive
        env._last_outcome_pnl = 0.02
        action = np.zeros(7)
        obs, reward, term, trunc, info = env.step(action)
        assert reward > 0
```

**Step 2: Run test to verify failure**

Run: `cd smart-money-signal-system && python -m pytest tests/unit/test_rl_environment.py -v`
Expected: FAIL

**Step 3: Implement**

```python
# src/signal_system/rl/environment.py
"""Gymnasium environment for signal parameter optimization."""

import gymnasium as gym
import numpy as np
from gymnasium import spaces
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SignalOptEnv(gym.Env):
    """Environment where agent learns optimal signal generation parameters.

    Observation (state): Market features that describe the current context
    - regime_id (one-hot, 6 dims)
    - long_bias, short_bias, net_bias (3 dims)
    - confidence (1 dim)
    - trader_count_long, trader_count_short (2 dims)
    - price_change_1m, price_change_5m, price_change_15m (3 dims)
    - volatility (1 dim)
    Total: 16 dims

    Action (continuous): Signal generation parameters to modulate
    - 0: recommendation_threshold (mapped from [-1,1] to [0.05, 0.5])
    - 1: confidence_scale (mapped to [0.5, 3.0])
    - 2: emission_bias_delta (mapped to [0.01, 0.3])
    - 3: long_weight_boost (mapped to [0.5, 2.0])
    - 4: short_weight_boost (mapped to [0.5, 2.0])
    - 5: recency_decay_factor (mapped to [0.5, 2.0])
    - 6: regime_multiplier_adj (mapped to [0.5, 1.5])
    Total: 7 dims

    Reward: PnL of generated signal at evaluation horizon.
    """

    metadata = {"render_modes": []}

    # Action bounds: [low, high] after mapping from [-1, 1]
    ACTION_BOUNDS = [
        (0.05, 0.50),   # recommendation_threshold
        (0.50, 3.00),   # confidence_scale
        (0.01, 0.30),   # emission_bias_delta
        (0.50, 2.00),   # long_weight_boost
        (0.50, 2.00),   # short_weight_boost
        (0.50, 2.00),   # recency_decay_factor
        (0.50, 1.50),   # regime_multiplier_adj
    ]

    def __init__(self) -> None:
        super().__init__()

        # 16-dim observation
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(16,), dtype=np.float32,
        )
        # 7-dim continuous action
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(7,), dtype=np.float32,
        )

        self._state = np.zeros(16, dtype=np.float32)
        self._last_outcome_pnl: float = 0.0
        self._step_count = 0
        self._max_steps = 1000

    def reset(self, seed: int | None = None, options: dict | None = None) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        self._state = np.zeros(16, dtype=np.float32)
        self._last_outcome_pnl = 0.0
        self._step_count = 0
        return self._state.copy(), {}

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
        self._step_count += 1

        # Map action from [-1, 1] to parameter ranges
        params = self._map_action(action)

        # Reward from last signal outcome
        reward = self._compute_reward(self._last_outcome_pnl, params)

        # In live mode, state is updated externally via update_state()
        # In training mode, state comes from replay buffer
        terminated = False
        truncated = self._step_count >= self._max_steps
        info = {"params": params, "raw_pnl": self._last_outcome_pnl}

        return self._state.copy(), reward, terminated, truncated, info

    def update_state(self, state_dict: dict[str, Any]) -> None:
        """Update environment state from live market data."""
        regime_onehot = np.zeros(6, dtype=np.float32)
        regime_id = state_dict.get("regime_id", 0)
        if 0 <= regime_id < 6:
            regime_onehot[regime_id] = 1.0

        features = np.array([
            state_dict.get("long_bias", 0.0),
            state_dict.get("short_bias", 0.0),
            state_dict.get("net_bias", 0.0),
            state_dict.get("confidence", 0.0),
            state_dict.get("traders_long", 0),
            state_dict.get("traders_short", 0),
            state_dict.get("price_change_1m", 0.0),
            state_dict.get("price_change_5m", 0.0),
            state_dict.get("price_change_15m", 0.0),
            state_dict.get("volatility", 0.0),
        ], dtype=np.float32)

        self._state = np.concatenate([regime_onehot, features])

    def set_last_outcome(self, pnl: float) -> None:
        """Set the PnL from the most recent signal outcome."""
        self._last_outcome_pnl = pnl

    def _map_action(self, action: np.ndarray) -> dict[str, float]:
        """Map raw action [-1, 1] to parameter ranges."""
        param_names = [
            "recommendation_threshold",
            "confidence_scale",
            "emission_bias_delta",
            "long_weight_boost",
            "short_weight_boost",
            "recency_decay_factor",
            "regime_multiplier_adj",
        ]
        params = {}
        for i, name in enumerate(param_names):
            low, high = self.ACTION_BOUNDS[i]
            # Map from [-1, 1] to [low, high]
            params[name] = low + (high - low) * (action[i] + 1) / 2
        return params

    def _compute_reward(self, pnl: float, params: dict[str, float]) -> float:
        """Compute shaped reward from PnL and parameter choices.

        Base reward = PnL.
        Bonus for high confidence when correct, penalty when wrong.
        Small penalty for extreme parameter values (regularization).
        """
        # Base: signal PnL
        reward = pnl * 100  # Scale up for gradient signal

        # Confidence alignment bonus
        if pnl > 0:
            reward += 0.1 * params["confidence_scale"]
        else:
            reward -= 0.1 * params["confidence_scale"]

        # Regularization: penalize extreme values
        for name, val in params.items():
            low, high = self.ACTION_BOUNDS[list(params.keys()).index(name)]
            mid = (low + high) / 2
            half_range = (high - low) / 2
            if half_range > 0:
                deviation = abs(val - mid) / half_range
                reward -= 0.01 * deviation  # Small L2-like penalty

        return float(reward)
```

**Step 4: Run tests**

Run: `cd smart-money-signal-system && python -m pytest tests/unit/test_rl_environment.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add src/signal_system/rl/environment.py tests/unit/test_rl_environment.py
git commit -m "feat(rl): add Gymnasium SignalOptEnv for parameter optimization"
```

---

## Phase 3: PPO Agent

### Task 5: Create PPO Policy Network

**Objective:** Build the actor-critic networks and PPO training loop.

**Files:**
- Create: `src/signal_system/rl/policy.py`
- Create: `tests/unit/test_policy.py`

**Step 1: Write failing test**

```python
# tests/unit/test_policy.py
import pytest
import numpy as np
import torch
from signal_system.rl.policy import ActorCritic, PPOAgent


class TestActorCritic:
    def test_forward_pass(self):
        model = ActorCritic(obs_dim=16, act_dim=7)
        obs = torch.randn(1, 16)
        action, log_prob, value = model.act(obs)
        assert action.shape == (1, 7)
        assert isinstance(log_prob.item(), float)
        assert isinstance(value.item(), float)

    def test_evaluate_actions(self):
        model = ActorCritic(obs_dim=16, act_dim=7)
        obs = torch.randn(4, 16)
        actions = torch.randn(4, 7)
        log_probs, values, entropy = model.evaluate(obs, actions)
        assert log_probs.shape == (4,)
        assert values.shape == (4,)
        assert entropy.shape == ()


class TestPPOAgent:
    def test_act(self):
        agent = PPOAgent(obs_dim=16, act_dim=7)
        obs = np.zeros(16, dtype=np.float32)
        action, log_prob, value = agent.act(obs)
        assert action.shape == (7,)
        assert np.all(action >= -1) and np.all(action <= 1)

    def test_learn_from_buffer(self):
        agent = PPOAgent(obs_dim=16, act_dim=7)
        # Create a small rollout buffer
        for _ in range(64):
            obs = np.random.randn(16).astype(np.float32)
            action, log_prob, value = agent.act(obs)
            reward = np.random.randn()
            next_obs = np.random.randn(16).astype(np.float32)
            done = False
            agent.store(obs, action, log_prob, reward, done, value)

        loss_dict = agent.learn()
        assert "policy_loss" in loss_dict
        assert "value_loss" in loss_dict
```

**Step 2: Run test to verify failure**

Run: `cd smart-money-signal-system && python -m pytest tests/unit/test_policy.py -v`
Expected: FAIL

**Step 3: Implement**

```python
# src/signal_system/rl/policy.py
"""PPO Actor-Critic and training loop for signal optimization."""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal
from collections import deque
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ActorCritic(nn.Module):
    """Actor-Critic network with Gaussian policy."""

    def __init__(
        self,
        obs_dim: int = 16,
        act_dim: int = 7,
        hidden_dim: int = 128,
        log_std_init: float = -0.5,
    ) -> None:
        super().__init__()

        # Shared backbone
        self.backbone = nn.Sequential(
            nn.Linear(obs_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )

        # Actor head (policy)
        self.actor_mean = nn.Linear(hidden_dim, act_dim)
        self.actor_log_std = nn.Parameter(torch.ones(act_dim) * log_std_init)

        # Critic head (value)
        self.critic = nn.Linear(hidden_dim, 1)

        # Initialize weights
        self._init_weights()

    def _init_weights(self) -> None:
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.orthogonal_(module.weight, gain=np.sqrt(2))
                nn.init.constant_(module.bias, 0)
        # Smaller init for policy output
        nn.init.orthogonal_(self.actor_mean.weight, gain=0.01)
        nn.init.orthogonal_(self.critic.weight, gain=1.0)

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.backbone(obs)
        mean = torch.tanh(self.actor_mean(features))  # Bounded [-1, 1]
        std = torch.exp(self.actor_log_std)
        value = self.critic(features).squeeze(-1)
        return mean, std, value

    def act(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        mean, std, value = self.forward(obs)
        dist = Normal(mean, std)
        action = dist.sample()
        action = torch.clamp(action, -1, 1)
        log_prob = dist.log_prob(action).sum(dim=-1)
        return action, log_prob, value

    def evaluate(
        self, obs: torch.Tensor, actions: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        mean, std, value = self.forward(obs)
        dist = Normal(mean, std)
        log_prob = dist.log_prob(actions).sum(dim=-1)
        entropy = dist.entropy().sum(dim=-1).mean()
        return log_prob, value, entropy


class RolloutBuffer:
    """Buffer for storing rollout data."""

    def __init__(self) -> None:
        self.obs: list[np.ndarray] = []
        self.actions: list[np.ndarray] = []
        self.log_probs: list[float] = []
        self.rewards: list[float] = []
        self.dones: list[bool] = []
        self.values: list[float] = []

    def store(
        self,
        obs: np.ndarray,
        action: np.ndarray,
        log_prob: float,
        reward: float,
        done: bool,
        value: float,
    ) -> None:
        self.obs.append(obs)
        self.actions.append(action)
        self.log_probs.append(log_prob)
        self.rewards.append(reward)
        self.dones.append(done)
        self.values.append(value)

    def __len__(self) -> int:
        return len(self.obs)

    def clear(self) -> None:
        self.obs.clear()
        self.actions.clear()
        self.log_probs.clear()
        self.rewards.clear()
        self.dones.clear()
        self.values.clear()


class PPOAgent:
    """PPO agent for signal parameter optimization."""

    def __init__(
        self,
        obs_dim: int = 16,
        act_dim: int = 7,
        lr: float = 3e-4,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_epsilon: float = 0.2,
        epochs: int = 10,
        batch_size: int = 64,
        value_coeff: float = 0.5,
        entropy_coeff: float = 0.01,
        max_grad_norm: float = 0.5,
    ) -> None:
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_epsilon = clip_epsilon
        self.epochs = epochs
        self.batch_size = batch_size
        self.value_coeff = value_coeff
        self.entropy_coeff = entropy_coeff
        self.max_grad_norm = max_grad_norm

        self.model = ActorCritic(obs_dim, act_dim)
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
        self.buffer = RolloutBuffer()
        self._device = torch.device("cpu")
        self.model.to(self._device)

    def act(self, obs: np.ndarray) -> tuple[np.ndarray, float, float]:
        self.model.eval()
        with torch.no_grad():
            obs_t = torch.FloatTensor(obs).unsqueeze(0).to(self._device)
            action, log_prob, value = self.model.act(obs_t)
        return (
            action.cpu().numpy().flatten(),
            log_prob.item(),
            value.item(),
        )

    def store(
        self,
        obs: np.ndarray,
        action: np.ndarray,
        log_prob: float,
        reward: float,
        done: bool,
        value: float,
    ) -> None:
        self.buffer.store(obs, action, log_prob, reward, done, value)

    def learn(self) -> dict[str, float]:
        if len(self.buffer) < self.batch_size:
            return {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}

        self.model.train()

        # Compute GAE advantages
        advantages, returns = self._compute_gae()

        # Convert buffer to tensors
        obs_t = torch.FloatTensor(np.array(self.buffer.obs)).to(self._device)
        actions_t = torch.FloatTensor(np.array(self.buffer.actions)).to(self._device)
        old_log_probs_t = torch.FloatTensor(self.buffer.log_probs).to(self._device)
        advantages_t = torch.FloatTensor(advantages).to(self._device)
        returns_t = torch.FloatTensor(returns).to(self._device)

        # Normalize advantages
        advantages_t = (advantages_t - advantages_t.mean()) / (advantages_t.std() + 1e-8)

        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0
        n_updates = 0

        for _ in range(self.epochs):
            indices = np.random.permutation(len(self.buffer))
            for start in range(0, len(self.buffer), self.batch_size):
                end = start + self.batch_size
                if end > len(self.buffer):
                    break
                batch_idx = indices[start:end]

                b_obs = obs_t[batch_idx]
                b_actions = actions_t[batch_idx]
                b_old_log_probs = old_log_probs_t[batch_idx]
                b_advantages = advantages_t[batch_idx]
                b_returns = returns_t[batch_idx]

                new_log_probs, values, entropy = self.model.evaluate(b_obs, b_actions)

                # PPO clipped objective
                ratio = torch.exp(new_log_probs - b_old_log_probs)
                surr1 = ratio * b_advantages
                surr2 = torch.clamp(ratio, 1 - self.clip_epsilon, 1 + self.clip_epsilon) * b_advantages
                policy_loss = -torch.min(surr1, surr2).mean()

                # Value loss
                value_loss = ((values - b_returns) ** 2).mean()

                # Total loss
                loss = policy_loss + self.value_coeff * value_loss - self.entropy_coeff * entropy

                self.optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), self.max_grad_norm)
                self.optimizer.step()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.item()
                n_updates += 1

        self.buffer.clear()

        return {
            "policy_loss": total_policy_loss / max(n_updates, 1),
            "value_loss": total_value_loss / max(n_updates, 1),
            "entropy": total_entropy / max(n_updates, 1),
        }

    def _compute_gae(self) -> tuple[list[float], list[float]]:
        rewards = self.buffer.rewards
        values = self.buffer.values
        dones = self.buffer.dones

        advantages = []
        returns = []
        gae = 0.0
        next_value = 0.0

        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                next_non_terminal = 1.0 - dones[t]
                next_val = next_value
            else:
                next_non_terminal = 1.0 - dones[t]
                next_val = values[t + 1]

            delta = rewards[t] + self.gamma * next_val * next_non_terminal - values[t]
            gae = delta + self.gamma * self.gae_lambda * next_non_terminal * gae
            advantages.insert(0, gae)
            returns.insert(0, gae + values[t])

        return advantages, returns

    def save(self, path: str) -> None:
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
        }, path)
        logger.info("agent_saved", path=path)

    def load(self, path: str) -> bool:
        try:
            checkpoint = torch.load(path, map_location=self._device, weights_only=True)
            self.model.load_state_dict(checkpoint["model_state_dict"])
            self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            logger.info("agent_loaded", path=path)
            return True
        except Exception as e:
            logger.error("agent_load_error", error=str(e))
            return False

    def get_params(self) -> dict[str, float]:
        """Get current policy parameters for live signal generation."""
        self.model.eval()
        with torch.no_grad():
            dummy_obs = torch.zeros(1, 16).to(self._device)
            mean, _, _ = self.model.forward(dummy_obs)
            action = torch.tanh(mean).cpu().numpy().flatten()
        return self._env_action_to_params(action)

    def _env_action_to_params(self, action: np.ndarray) -> dict[str, float]:
        from signal_system.rl.environment import SignalOptEnv
        env = SignalOptEnv()
        return env._map_action(action)
```

**Step 4: Run tests**

Run: `cd smart-money-signal-system && python -m pytest tests/unit/test_policy.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add src/signal_system/rl/policy.py tests/unit/test_policy.py
git commit -m "feat(rl): add PPO actor-critic and training loop"
```

---

### Task 6: Add torch/gymnasium Dependencies

**Objective:** Add PyTorch and Gymnasium to project dependencies.

**Files:**
- Modify: `pyproject.toml`

**Step 1: Update pyproject.toml**

Add to dependencies:
```
"torch>=2.2.0",
"gymnasium>=1.0.0",
```

**Step 2: Install and verify**

Run: `cd smart-money-signal-system && pip install -e ".[dev]" 2>&1 | tail -5`
Run: `python -c "import torch; import gymnasium; print('OK')"`

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat(rl): add torch and gymnasium dependencies"
```

---

## Phase 4: Training Pipeline

### Task 7: Offline Training Script

**Objective:** Script to train the PPO agent from historical signal outcome data.

**Files:**
- Create: `src/signal_system/rl/training.py`
- Create: `tests/unit/test_training.py`

**Step 1: Write failing test**

```python
# tests/unit/test_training.py
import pytest
from signal_system.rl.training import OfflineTrainer


class TestOfflineTrainer:
    def test_init(self):
        trainer = OfflineTrainer(obs_dim=16, act_dim=7)
        assert trainer.agent is not None
        assert trainer.env is not None

    def test_train_episode(self):
        trainer = OfflineTrainer(obs_dim=16, act_dim=7, max_steps=10)
        result = trainer.train_episode()
        assert "total_reward" in result
        assert "steps" in result
        assert result["steps"] == 10

    def test_train_multiple_episodes(self):
        trainer = OfflineTrainer(obs_dim=16, act_dim=7, max_steps=5)
        results = trainer.train(n_episodes=3)
        assert len(results) == 3
```

**Step 2-4: TDD cycle**

Implement OfflineTrainer that:
1. Loads historical outcomes from OutcomeStore
2. Creates synthetic environment transitions from outcome data
3. Runs PPO training loop
4. Saves model checkpoint
5. Logs metrics via structlog

The trainer replays historical market states and their outcomes, letting the agent learn which parameter configurations produced the best rewards.

**Step 5: Commit**

```bash
git add src/signal_system/rl/training.py tests/unit/test_training.py
git commit -m "feat(rl): add offline training pipeline"
```

---

### Task 8: RL Parameter Server (Live Inference)

**Objective:** Serve learned parameters to the signal generation pipeline in production.

**Files:**
- Create: `src/signal_system/rl/parameter_server.py`
- Create: `tests/unit/test_parameter_server.py`

**Step 1: Write failing test**

```python
# tests/unit/test_parameter_server.py
import pytest
from signal_system.rl.parameter_server import RLParameterServer


class TestRLParameterServer:
    def test_default_params_without_model(self):
        server = RLParameterServer()
        params = server.get_params()
        assert "recommendation_threshold" in params
        assert params["recommendation_threshold"] == 0.2  # default

    def test_load_model_and_get_params(self):
        server = RLParameterServer(model_path="nonexistent.pt")
        # Falls back to defaults when model missing
        params = server.get_params()
        assert "recommendation_threshold" in params

    def test_param_update_notification(self):
        server = RLParameterServer()
        server.update_params({"recommendation_threshold": 0.3})
        params = server.get_params()
        assert params["recommendation_threshold"] == 0.3
```

**Step 2-4: TDD cycle**

Implement RLParameterServer:
- On init, try to load latest checkpoint. If none, use defaults matching current hardcoded values.
- `get_params()` returns current parameter dict
- `update_params()` lets the training pipeline push new parameters
- Thread-safe with a lock
- Persists current params to Redis so signal processor can read them

**Step 5: Commit**

```bash
git add src/signal_system/rl/parameter_server.py tests/unit/test_parameter_server.py
git commit -m "feat(rl): add RL parameter server for live inference"
```

---

## Phase 5: Integration -- Wire RL into Signal Generation

### Task 9: Make SignalGenerationProcessor Accept RL Parameters

**Objective:** Replace hardcoded thresholds in signal generation with RL-sourced parameters.

**Files:**
- Modify: `src/signal_system/signal_generation/processor.py`
- Create: `tests/unit/test_signal_processor_rl.py`

**Step 1: Write failing test**

```python
# tests/unit/test_signal_processor_rl.py
import pytest
import time
from signal_system.signal_generation.processor import SignalGenerationProcessor


class TestSignalProcessorRLParams:
    def test_custom_threshold(self):
        processor = SignalGenerationProcessor(rl_params={
            "recommendation_threshold": 0.4,
            "confidence_scale": 1.5,
        })
        # Same setup as default test but higher threshold
        processor._trader_scores = {"0x1": 70, "0x2": 70}
        now = time.time()
        processor._trader_positions = {
            "0x1": ({"positions": [{"position": {"coin": "BTC", "szi": "10.0"}}]}, now),
            "0x2": ({"positions": [{"position": {"coin": "BTC", "szi": "-5.0"}}]}, now),
        }
        signal = processor._generate_signal()
        # With higher threshold (0.4), moderate bias should be NEUTRAL
        if signal and abs(signal["net_bias"]) < 0.4:
            assert signal["action"] == "NEUTRAL"

    def test_update_rl_params(self):
        processor = SignalGenerationProcessor()
        processor.update_rl_params({"recommendation_threshold": 0.3})
        assert processor._rl_params["recommendation_threshold"] == 0.3
```

**Step 2-4: TDD cycle**

Modify SignalGenerationProcessor:
- Add `rl_params` dict parameter to `__init__` with defaults matching current hardcoded values
- Add `update_rl_params()` method
- In `_generate_signal()`, use `self._rl_params["recommendation_threshold"]` instead of hardcoded `0.2`
- Use `self._rl_params["confidence_scale"]` instead of hardcoded `* 2`
- Use `self._rl_params["emission_bias_delta"]` instead of hardcoded `0.1`
- Add weight boost and recency decay from RL params

**Step 5: Commit**

```bash
git add src/signal_system/signal_generation/processor.py tests/unit/test_signal_processor_rl.py
git commit -m "feat(rl): make signal generation params configurable via RL"
```

---

### Task 10: Wire Everything Together in __main__.py

**Objective:** Full integration -- RL components connected to live pipeline.

**Files:**
- Modify: `src/signal_system/__main__.py`

**Step 1: Modify SignalSystem class**

Add to `__init__`:
```python
# RL components
self._outcome_tracker = SignalOutcomeTracker()
self._rl_param_server = RLParameterServer(model_path="models/ppo_agent.pt")
```

Wire outcome tracker to event processor (already done in Task 2).

Add `mark_price` handler:
```python
async def handle_mark_price(event: dict) -> None:
    price = event.get("payload", {}).get("price", 0)
    if price > 0:
        outcomes = self._outcome_tracker.update_price(price)
        for outcome in outcomes:
            # Store and feed to environment
            if self._signal_store:
                self._rl_outcome_store.store(outcome)
            # Update env state for online learning
            self._env.set_last_outcome(outcome.pnl_pct)

        # Update env state from current market data
        signal = self._signal_processor.get_latest_signal()
        if signal:
            self._env.update_state({
                "long_bias": signal.get("long_bias", 0),
                "short_bias": signal.get("short_bias", 0),
                "net_bias": signal.get("net_bias", 0),
                "confidence": signal.get("confidence", 0),
                "regime_id": self._weighting_engine._current_regime,
                ...
            })

        # Online learning step
        if len(self._outcome_tracker.get_resolved_outcomes()) > 10:
            action, _, _ = self._agent.act(self._env._state)
            params = self._env._map_action(action)
            self._rl_param_server.update_params(params)
            self._signal_processor.update_rl_params(params)
```

**Step 2: Verify existing tests still pass**

Run: `cd smart-money-signal-system && python -m pytest tests/ -v`
Expected: All pass

**Step 3: Commit**

```bash
git add src/signal_system/__main__.py
git commit -m "feat(rl): integrate RL agent into live signal pipeline"
```

---

## Phase 6: Scheduled Retraining

### Task 11: Retraining Cron Job

**Objective:** Periodically retrain the PPO agent on accumulated outcome data.

**Files:**
- Create: `scripts/retrain_rl_agent.py`
- Add cron job via Hermes

**Step 1: Create retraining script**

```python
#!/usr/bin/env python3
"""Retrain RL agent from accumulated signal outcomes."""
import sys
sys.path.insert(0, "src")

from signal_system.rl.outcome_store import OutcomeStore
from signal_system.rl.training import OfflineTrainer

def main():
    store = OutcomeStore()
    data = store.get_training_data(min_samples=500)
    if data is None:
        print("Not enough training data yet")
        return

    trainer = OfflineTrainer(
        obs_dim=16,
        act_dim=7,
        max_steps=500,
    )
    results = trainer.train(n_episodes=50, training_data=data)
    trainer.agent.save("models/ppo_agent.pt")
    print(f"Retrained. Avg reward: {sum(r['total_reward'] for r in results) / len(results):.4f}")

if __name__ == "__main__":
    main()
```

**Step 2: Set up cron job**

Schedule: every 6 hours
Model: z-ai/glm-5.1 (execution task)

**Step 3: Commit**

```bash
git add scripts/retrain_rl_agent.py
git commit -m "feat(rl): add scheduled retraining script"
```

---

## Phase 7: API & Monitoring

### Task 12: RL Status API Endpoint

**Objective:** Expose RL agent state via API for monitoring.

**Files:**
- Modify: `src/signal_system/api/routes.py`

**Step 1: Add endpoints**

```
GET /rl/status    -- agent status, current params, training history
GET /rl/params    -- current RL-controlled parameters
GET /rl/outcomes  -- recent signal outcomes with PnL
POST /rl/retrain  -- trigger manual retraining
```

**Step 2: Verify**

Run: `cd smart-money-signal-system && python -m pytest tests/ -v`

**Step 3: Commit**

```bash
git add src/signal_system/api/routes.py
git commit -m "feat(rl): add RL monitoring API endpoints"
```

---

### Task 13: Dashboard Metrics

**Objective:** Add Prometheus-style metrics for RL agent performance.

**Files:**
- Create: `src/signal_system/rl/metrics.py`

Metrics to expose:
- `rl_signal_pnl` -- per-signal PnL gauge
- `rl_avg_reward` -- rolling average reward
- `rl_param_*` -- current parameter values
- `rl_training_loss` -- policy/value loss from last training run
- `rl_outcomes_total` -- total resolved outcomes
- `rl_pending_signals` -- signals awaiting outcome

**Step 1-3: TDD, commit**

```bash
git add src/signal_system/rl/metrics.py tests/unit/test_rl_metrics.py
git commit -m "feat(rl): add Prometheus metrics for RL agent"
```

---

## Summary

| Phase | Tasks | What It Builds |
|-------|-------|---------------|
| 1: Reward Infrastructure | 1-3 | SignalOutcomeTracker, MongoDB outcome storage |
| 2: RL Environment | 4 | Gymnasium SignalOptEnv (16-dim obs, 7-dim action) |
| 3: PPO Agent | 5-6 | ActorCritic network, PPO training loop, torch/gymnasium deps |
| 4: Training Pipeline | 7-8 | OfflineTrainer, RLParameterServer |
| 5: Integration | 9-10 | Configurable signal params, live pipeline wiring |
| 6: Scheduled Retraining | 11 | 6h cron retraining job |
| 7: Monitoring | 12-13 | API endpoints, Prometheus metrics |

**Key Design Decisions:**
- PPO (not DQN) because action space is continuous -- we're modulating real-valued parameters
- 7 actionable parameters: recommendation threshold, confidence scale, emission delta, long/short weight boosts, recency decay, regime multiplier adjustment
- Multi-horizon reward evaluation (1m, 5m, 15m, 1h) to capture short and medium-term signal quality
- Shaped reward: PnL base + confidence alignment bonus + regularization penalty
- Offline-first training: learn from historical data before online deployment
- Graceful fallback: if no model loaded, defaults match current hardcoded values
- Online learning: agent takes actions on live state, updates params incrementally

**What the agent learns:**
1. When to require stronger consensus (higher threshold) vs act on weaker signals
2. How to scale confidence based on market conditions
3. How much bias change justifies signal emission
4. Whether to weight long vs short traders differently
5. How quickly to discount stale trader data
6. How to adjust regime multipliers from empirical outcomes
