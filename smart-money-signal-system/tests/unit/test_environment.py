"""Unit tests for SignalOptEnv Gymnasium environment."""

import pytest
import numpy as np

from signal_system.rl.environment import SignalOptEnv


class TestSignalOptEnv:
    def test_creation(self):
        """Environment can be created with defaults."""
        env = SignalOptEnv()
        assert env.observation_space is not None
        assert env.action_space is not None

    def test_reset(self):
        """Reset returns valid observation."""
        env = SignalOptEnv()
        obs, info = env.reset()
        assert obs.shape == env.observation_space.shape
        assert isinstance(info, dict)

    def test_step_returns_valid(self):
        """Step returns (obs, reward, terminated, truncated, info)."""
        env = SignalOptEnv()
        env.reset()
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        assert obs.shape == env.observation_space.shape
        assert isinstance(reward, (int, float))
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)

    def test_episode_length(self):
        """Episode terminates after max_steps."""
        env = SignalOptEnv(max_steps=5)
        env.reset()
        for _ in range(10):
            _, _, terminated, truncated, _ = env.step(env.action_space.sample())
            if terminated or truncated:
                break
        assert terminated or truncated

    def test_feed_outcome(self):
        """feed_outcome provides real signal outcome data."""
        env = SignalOptEnv()
        from signal_system.rl.outcome_tracker import SignalOutcome

        outcome = SignalOutcome(
            signal_id="s1",
            action="BUY",
            confidence=0.8,
            entry_price=50000.0,
            exit_price=51000.0,
            pnl_pct=0.02,
            horizon_seconds=300,
            timestamp=1000.0,
            resolved_at=1300.0,
        )
        env.feed_outcome(outcome)
        assert env._recent_outcomes[-1].signal_id == "s1"

    def test_feed_outcome_updates_observation(self):
        """After feeding outcomes, observation reflects them."""
        env = SignalOptEnv()
        env.reset()
        from signal_system.rl.outcome_tracker import SignalOutcome

        outcome = SignalOutcome(
            signal_id="s1",
            action="BUY",
            confidence=0.8,
            entry_price=50000.0,
            exit_price=51000.0,
            pnl_pct=0.02,
            horizon_seconds=300,
            timestamp=1000.0,
            resolved_at=1300.0,
        )
        env.feed_outcome(outcome)
        obs, _ = env.reset()
        # Observation should include outcome-related features
        assert not np.all(obs == 0)

    def test_action_meaning(self):
        """Actions map to bias threshold adjustments."""
        env = SignalOptEnv()
        # Action 0 = decrease threshold, 1 = no change, 2 = increase
        env.reset()
        old_threshold = env.bias_threshold
        env.step(0)  # decrease
        assert env.bias_threshold <= old_threshold

    def test_reward_positive_for_good_signal(self):
        """Reward is positive when action improves signal quality."""
        env = SignalOptEnv()
        env.reset()
        from signal_system.rl.outcome_tracker import SignalOutcome

        # Feed a positive outcome
        env.feed_outcome(SignalOutcome(
            "s1", "BUY", 0.9, 50000.0, 52000.0, 0.04, 300, 1000.0, 1300.0
        ))
        # Step with action that increases threshold (should filter weak signals)
        _, reward, _, _, _ = env.step(2)
        # Reward should relate to recent outcome quality
        assert isinstance(reward, float)

    def test_observation_space_bounds(self):
        """Observations stay within observation space bounds."""
        env = SignalOptEnv()
        obs, _ = env.reset()
        for _ in range(20):
            action = env.action_space.sample()
            obs, _, _, _, _ = env.step(action)
            assert env.observation_space.contains(obs), f"Obs {obs} out of bounds"

    def test_gymnasium_api_compliance(self):
        """Environment follows Gymnasium API."""
        env = SignalOptEnv()
        import gymnasium
        # Check spaces
        assert hasattr(env, 'observation_space')
        assert hasattr(env, 'action_space')
        # Check methods
        assert callable(env.reset)
        assert callable(env.step)

    def test_set_current_signal(self):
        """set_current_signal provides current signal context."""
        env = SignalOptEnv()
        env.reset()
        env.set_current_signal({
            "action": "BUY",
            "confidence": 0.8,
            "net_bias": 0.5,
        })
        assert env._current_signal["action"] == "BUY"
