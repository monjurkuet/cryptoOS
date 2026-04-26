#!/usr/bin/env python3
"""Retraining script for RL signal optimization agent.

Loads recent signal outcomes from MongoDB, runs an offline
training session, saves the new checkpoint, and optionally
pushes updated params to the live signal system.

Usage:
    python -m signal_system.rl.retrain
    python -m signal_system.rl.retrain --episodes 200
    python -m signal_system.rl.retrain --push
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import structlog

from signal_system.config import get_settings
from signal_system.rl.outcome_store import OutcomeStore
from signal_system.rl.training import OfflineTrainer

logger = structlog.get_logger(__name__)

DEFAULT_CHECKPOINT_DIR = Path(__file__).parent.parent.parent.parent / "checkpoints"
DEFAULT_EPISODES = 100


def retrain(
    episodes: int = DEFAULT_EPISODES,
    checkpoint_dir: Path | None = None,
    push: bool = False,
) -> bool:
    """Run offline retraining from stored outcomes.

    Args:
        episodes: Number of training episodes
        checkpoint_dir: Where to save checkpoints
        push: If True, push updated params to live system

    Returns:
        True if training succeeded
    """
    if checkpoint_dir is None:
        checkpoint_dir = DEFAULT_CHECKPOINT_DIR

    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    settings = get_settings()

    # Initialize outcome store
    store = OutcomeStore()

    # Fetch recent outcomes
    outcomes = store.get_recent_outcomes(limit=500)
    if not outcomes:
        logger.warning("retrain_no_outcomes_available")
        store.close()
        return False

    logger.info(
        "retrain_starting",
        outcomes=len(outcomes),
        episodes=episodes,
        checkpoint_dir=str(checkpoint_dir),
    )

    # Train
    trainer = OfflineTrainer()
    result = trainer.train(outcomes, num_episodes=episodes)

    logger.info(
        "retrain_complete",
        episodes=result.episodes,
        mean_reward=result.mean_reward,
        params=result.final_params,
    )

    # Save checkpoint
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    checkpoint_path = checkpoint_dir / f"rl_agent_{timestamp}.pt"
    trainer.agent.save(str(checkpoint_path))

    logger.info("retrain_checkpoint_saved", path=str(checkpoint_path))

    # Push to live system if requested
    if push:
        _push_params(result.final_params, settings)

    store.close()
    return True


def _push_params(params: dict, settings) -> None:
    """Push updated params to the live signal system via API.

    Args:
        params: New RL params to push
        settings: System settings for API URL
    """
    import httpx

    api_url = f"http://localhost:{settings.api_port}/api/v1/rl/params"
    try:
        resp = httpx.put(api_url, json=params, timeout=10.0)
        if resp.status_code == 200:
            logger.info("retrain_params_pushed", params=params)
        else:
            logger.warning(
                "retrain_push_failed",
                status=resp.status_code,
                body=resp.text,
            )
    except Exception as e:
        logger.warning("retrain_push_error", error=str(e))


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Retrain RL signal agent")
    parser.add_argument(
        "--episodes", type=int, default=DEFAULT_EPISODES,
        help="Number of training episodes",
    )
    parser.add_argument(
        "--checkpoint-dir", type=Path, default=None,
        help="Checkpoint output directory",
    )
    parser.add_argument(
        "--push", action="store_true",
        help="Push updated params to live system after training",
    )
    args = parser.parse_args()

    success = retrain(
        episodes=args.episodes,
        checkpoint_dir=args.checkpoint_dir,
        push=args.push,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
