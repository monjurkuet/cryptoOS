"""Unit tests for RLParameterServer."""

import pytest
import time
import numpy as np
from pathlib import Path

from signal_system.rl.parameter_server import RLParameterServer


class TestRLParameterServer:
    def test_creation_defaults(self):
        """Server starts with default signal params."""
        server = RLParameterServer()
        params = server.get_params()
        assert params["bias_threshold"] == 0.2
        assert params["conf_scale"] == 1.0
        assert params["min_confidence"] == 0.3

    def test_get_params_returns_copy(self):
        """get_params returns a copy so caller can't mutate state."""
        server = RLParameterServer()
        params = server.get_params()
        params["bias_threshold"] = 0.99
        # Original unchanged
        assert server.get_params()["bias_threshold"] == 0.2

    def test_update_params(self):
        """update_params changes the live parameters."""
        server = RLParameterServer()
        server.update_params(bias_threshold=0.35, conf_scale=1.2, min_confidence=0.4)
        params = server.get_params()
        assert params["bias_threshold"] == 0.35
        assert params["conf_scale"] == 1.2
        assert params["min_confidence"] == 0.4

    def test_update_params_partial(self):
        """update_params can update just one param."""
        server = RLParameterServer()
        server.update_params(bias_threshold=0.4)
        params = server.get_params()
        assert params["bias_threshold"] == 0.4
        assert params["conf_scale"] == 1.0  # unchanged

    def test_update_params_clamps_values(self):
        """update_params clamps values to valid ranges."""
        server = RLParameterServer()
        server.update_params(bias_threshold=-1.0, conf_scale=99.0, min_confidence=5.0)
        params = server.get_params()
        assert params["bias_threshold"] >= 0.05
        assert params["conf_scale"] <= 3.0
        assert params["min_confidence"] <= 0.9

    def test_load_from_checkpoint(self, tmp_path):
        """Can load params from a PPO checkpoint file."""
        from signal_system.rl.policy import PPOAgent
        agent = PPOAgent(obs_dim=12, action_dim=7)
        # Modify params from defaults
        agent._bias_threshold = 0.35
        agent._conf_scale = 1.3
        agent._min_confidence = 0.45
        path = str(tmp_path / "model.pt")
        agent.save(path)

        server = RLParameterServer()
        server.load_from_checkpoint(path)
        params = server.get_params()
        assert params["bias_threshold"] == 0.35
        assert params["conf_scale"] == 1.3
        assert params["min_confidence"] == 0.45

    def test_load_nonexistent_checkpoint(self):
        """Loading a missing checkpoint keeps defaults and logs warning."""
        server = RLParameterServer()
        server.load_from_checkpoint("/nonexistent/path/model.pt")
        # Should still have defaults
        params = server.get_params()
        assert params["bias_threshold"] == 0.2

    def test_get_status(self):
        """get_status returns server state info."""
        server = RLParameterServer()
        server.update_params(bias_threshold=0.3)
        status = server.get_status()
        assert "params" in status
        assert "last_updated" in status
        assert "checkpoint_path" in status
        assert status["params"]["bias_threshold"] == 0.3

    def test_last_updated_timestamp(self):
        """last_updated changes after update_params."""
        server = RLParameterServer()
        t1 = server.get_status()["last_updated"]
        server.update_params(bias_threshold=0.25)
        t2 = server.get_status()["last_updated"]
        assert t2 >= t1

    def test_auto_find_latest_checkpoint(self, tmp_path):
        """load_from_checkpoint auto-finds latest .pt in checkpoint_dir."""
        import time
        from signal_system.rl.policy import PPOAgent

        # Create two checkpoint files with different params
        agent1 = PPOAgent(obs_dim=12, action_dim=7)
        agent1._bias_threshold = 0.3
        agent1.save(str(tmp_path / "model_v1.pt"))
        time.sleep(0.1)

        agent2 = PPOAgent(obs_dim=12, action_dim=7)
        agent2._bias_threshold = 0.5
        agent2.save(str(tmp_path / "model_v2.pt"))

        # Auto-discover should pick the newest
        server = RLParameterServer(checkpoint_dir=tmp_path)
        server.load_from_checkpoint()
        params = server.get_params()
        assert params["bias_threshold"] == 0.5

    def test_auto_find_no_checkpoint_dir(self):
        """load_from_checkpoint with no dir returns False gracefully."""
        server = RLParameterServer()
        result = server.load_from_checkpoint()
        assert result is False
