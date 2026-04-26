"""Unit tests for PPO ActorCritic and PPOAgent."""

import pytest
import numpy as np

from signal_system.rl.policy import ActorCritic, PPOAgent


class TestActorCritic:
    def test_creation(self):
        """ActorCritic can be created with obs/action dims."""
        model = ActorCritic(obs_dim=12, action_dim=7)
        assert model is not None

    def test_forward_pass(self):
        """Forward pass returns action_probs, value, and log_probs."""
        import torch
        model = ActorCritic(obs_dim=12, action_dim=7)
        obs = torch.randn(1, 12)
        action_probs, value, log_probs = model(obs)
        assert action_probs.shape == (1, 7)
        assert value.shape == (1, 1)
        assert log_probs.shape == (1, 7)

    def test_action_probs_sum_to_one(self):
        """Action probabilities sum to 1."""
        import torch
        model = ActorCritic(obs_dim=12, action_dim=7)
        obs = torch.randn(1, 12)
        action_probs, _, _ = model(obs)
        assert abs(action_probs.sum().item() - 1.0) < 1e-5

    def test_get_action(self):
        """get_action returns action and log_prob."""
        import torch
        model = ActorCritic(obs_dim=12, action_dim=7)
        obs = torch.randn(1, 12)
        action, log_prob, value = model.get_action(obs)
        assert 0 <= action.item() < 7
        assert isinstance(log_prob.item(), float)
        assert isinstance(value.item(), float)


class TestPPOAgent:
    def test_creation(self):
        """PPOAgent can be created with default params."""
        agent = PPOAgent(obs_dim=12, action_dim=7)
        assert agent is not None

    def test_select_action(self):
        """select_action returns a valid action."""
        agent = PPOAgent(obs_dim=12, action_dim=7)
        obs = np.random.randn(12).astype(np.float32)
        action, log_prob, value = agent.select_action(obs)
        assert 0 <= action < 7

    def test_store_transition(self):
        """store_transition buffers experience."""
        agent = PPOAgent(obs_dim=12, action_dim=7)
        obs = np.random.randn(12).astype(np.float32)
        action, log_prob, value = agent.select_action(obs)
        agent.store_transition(obs, action, log_prob, value, reward=0.01, done=False)
        assert len(agent._observations) == 1

    def test_update_after_sufficient_data(self):
        """update() works when enough transitions stored."""
        agent = PPOAgent(obs_dim=12, action_dim=7, batch_size=4, update_epochs=2)
        for _ in range(8):
            obs = np.random.randn(12).astype(np.float32)
            action, log_prob, value = agent.select_action(obs)
            agent.store_transition(obs, action, log_prob, value, reward=0.01, done=False)
        loss = agent.update()
        assert isinstance(loss, dict)
        assert "policy_loss" in loss
        assert "value_loss" in loss

    def test_update_clears_buffer(self):
        """update() clears the experience buffer."""
        agent = PPOAgent(obs_dim=12, action_dim=7, batch_size=4, update_epochs=2)
        for _ in range(8):
            obs = np.random.randn(12).astype(np.float32)
            action, log_prob, value = agent.select_action(obs)
            agent.store_transition(obs, action, log_prob, value, reward=0.01, done=False)
        agent.update()
        assert len(agent._observations) == 0

    def test_save_load(self, tmp_path):
        """Agent can save and load state."""
        agent1 = PPOAgent(obs_dim=12, action_dim=7)
        obs = np.random.randn(12).astype(np.float32)
        action1, _, _ = agent1.select_action(obs)

        path = str(tmp_path / "model.pt")
        agent1.save(path)

        agent2 = PPOAgent(obs_dim=12, action_dim=7)
        agent2.load(path)
        # Same obs should give same action (deterministic in eval mode)
        agent1._model.eval()
        agent2._model.eval()
        import torch
        with torch.no_grad():
            obs_t = torch.FloatTensor(obs).unsqueeze(0)
            a1 = agent1._model(obs_t)[0].argmax(dim=-1).item()
            a2 = agent2._model(obs_t)[0].argmax(dim=-1).item()
        assert a1 == a2

    def test_get_params(self):
        """get_params returns current signal parameters."""
        agent = PPOAgent(obs_dim=12, action_dim=7)
        params = agent.get_params()
        assert "bias_threshold" in params
        assert "conf_scale" in params
        assert "min_confidence" in params
