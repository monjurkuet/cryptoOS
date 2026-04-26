"""Thread-safe parameter server for live RL inference.

Holds the current RL-adjusted signal parameters in memory,
providing fast reads for the signal generation pipeline.
Parameters are updated either:
1. Directly via update_params() (called after online training)
2. From a checkpoint file via load_from_checkpoint()
"""

from __future__ import annotations

import threading
import time
from typing import Any

import structlog

from signal_system.rl.environment import (
    DEFAULT_BIAS_THRESHOLD,
    DEFAULT_CONF_SCALE,
    DEFAULT_MIN_CONFIDENCE,
)

logger = structlog.get_logger(__name__)

# Valid parameter ranges
PARAM_RANGES = {
    "bias_threshold": (0.05, 0.8),
    "conf_scale": (0.1, 3.0),
    "min_confidence": (0.05, 0.9),
}


class RLParameterServer:
    """Thread-safe holder for RL-adjusted signal parameters.

    The signal generation pipeline calls get_params() on every signal
    computation. Training updates params via update_params() or
    load_from_checkpoint(). A threading lock ensures consistency.
    """

    def __init__(
        self,
        bias_threshold: float = DEFAULT_BIAS_THRESHOLD,
        conf_scale: float = DEFAULT_CONF_SCALE,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        self._lock = threading.RLock()
        self._params: dict[str, float] = {
            "bias_threshold": bias_threshold,
            "conf_scale": conf_scale,
            "min_confidence": min_confidence,
        }
        self._last_updated: float = time.time()
        self._checkpoint_path: str | None = None

    def get_params(self) -> dict[str, float]:
        """Get current signal parameters (thread-safe copy).

        Returns:
            Dict with bias_threshold, conf_scale, min_confidence
        """
        with self._lock:
            return dict(self._params)

    def update_params(self, **kwargs: float) -> None:
        """Update signal parameters (thread-safe).

        Only known parameter names are accepted. Values are clamped
        to their valid ranges.

        Keyword Args:
            bias_threshold: BUY/SELL threshold (0.05-0.8)
            conf_scale: Confidence scaling factor (0.1-3.0)
            min_confidence: Minimum confidence to emit signal (0.05-0.9)
        """
        with self._lock:
            for key, value in kwargs.items():
                if key in PARAM_RANGES:
                    lo, hi = PARAM_RANGES[key]
                    self._params[key] = max(lo, min(hi, value))
                else:
                    logger.warning("param_server_unknown_param", key=key)

            self._last_updated = time.time()

        logger.debug("param_server_updated", params=self._params)

    def load_from_checkpoint(self, path: str) -> bool:
        """Load parameters from a PPO checkpoint file.

        Args:
            path: Path to .pt checkpoint file

        Returns:
            True if loaded successfully, False otherwise
        """
        import torch

        try:
            checkpoint = torch.load(path, map_location="cpu", weights_only=True)
            params = checkpoint.get("params", {})
            if params:
                self.update_params(**params)
                self._checkpoint_path = path
                logger.info("param_server_loaded_checkpoint", path=path, params=params)
                return True
            else:
                logger.warning("param_server_checkpoint_no_params", path=path)
                return False
        except Exception as e:
            logger.warning("param_server_load_failed", path=path, error=str(e))
            return False

    def get_status(self) -> dict[str, Any]:
        """Get server status including current params and metadata.

        Returns:
            Dict with params, last_updated, checkpoint_path
        """
        with self._lock:
            return {
                "params": dict(self._params),
                "last_updated": self._last_updated,
                "checkpoint_path": self._checkpoint_path,
            }
