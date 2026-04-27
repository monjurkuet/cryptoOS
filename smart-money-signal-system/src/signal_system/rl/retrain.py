#!/usr/bin/env python3
"""Retraining script for RL signal optimization agent.

Loads recent signal outcomes from MongoDB, runs an offline
training session, saves the new checkpoint, and optionally
pushes updated params to the live signal system.

If no rl_outcomes collection exists (cold start), the script
will generate synthetic outcomes from the signals + candle data
in the market_scraper database.

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
from typing import Any

import structlog

from signal_system.config import get_settings
from signal_system.rl.outcome_store import OutcomeStore
from signal_system.rl.outcome_tracker import SignalOutcome
from signal_system.rl.training import OfflineTrainer

logger = structlog.get_logger(__name__)

DEFAULT_CHECKPOINT_DIR = Path(__file__).parent.parent.parent.parent / "checkpoints"
DEFAULT_EPISODES = 100


def _generate_outcomes_from_signals(
    mongo_client: Any,
    settings: Any,
) -> list[SignalOutcome]:
    """Generate synthetic SignalOutcomes from signals + candle data.

    Uses the market_scraper database signals and BTC candles to
    reconstruct what the PnL would have been at various horizons.

    Args:
        mongo_client: Connected pymongo MongoClient
        settings: Application settings

    Returns:
        List of SignalOutcome objects
    """
    import time
    from datetime import datetime as dt

    db = mongo_client["market_scraper"]

    # Load signals sorted by time
    signals = list(db["signals"].find().sort("t", 1))
    if not signals:
        logger.warning("generate_outcomes_no_signals")
        return []

    logger.info("generate_outcomes_from_signals", signal_count=len(signals))

    # Build candle lookup: map timestamp -> close price
    # Load 5m candles (good resolution for 1m/5m/15m/1h horizons)
    candle_cols = [
        ("btc_candles_5m", 300),
        ("btc_candles_15m", 900),
        ("btc_candles_1h", 3600),
    ]

    candle_map: dict[float, float] = {}
    for col_name, _interval in candle_cols:
        if col_name not in db.list_collection_names():
            continue
        for candle in db[col_name].find():
            t = candle.get("t")
            c = candle.get("c")
            if t is not None and c is not None:
                ts = t.timestamp() if isinstance(t, dt) else float(t)
                candle_map[ts] = float(c)

    logger.info("candles_loaded", candle_count=len(candle_map))

    # Also load 1m candles for finer resolution
    for candle in db["btc_candles_1m"].find():
        t = candle.get("t")
        c = candle.get("c")
        if t is not None and c is not None:
            ts = t.timestamp() if isinstance(t, dt) else float(t)
            candle_map[ts] = float(c)

    logger.info("candles_with_1m", candle_count=len(candle_map))

    # Sort candle timestamps for nearest-lookup
    sorted_ts = sorted(candle_map.keys())

    def _find_closest_price(target_ts: float, tolerance: float = 600) -> float | None:
        """Find the closest candle close price to target_ts."""
        # Binary search for nearest
        import bisect
        idx = bisect.bisect_left(sorted_ts, target_ts)
        best_ts = None
        best_dist = float("inf")
        for i in [idx - 1, idx, idx + 1]:
            if 0 <= i < len(sorted_ts):
                dist = abs(sorted_ts[i] - target_ts)
                if dist < best_dist:
                    best_dist = dist
                    best_ts = sorted_ts[i]
        if best_ts is not None and best_dist <= tolerance:
            return candle_map[best_ts]
        return None

    # Generate outcomes
    horizons = [60, 300, 900, 3600]  # 1m, 5m, 15m, 1h
    outcomes: list[SignalOutcome] = []

    for sig in signals:
        sig_t = sig.get("t")
        if sig_t is None:
            continue
        sig_ts = sig_t.timestamp() if isinstance(sig_t, dt) else float(sig_t)
        action = sig.get("rec", "NEUTRAL")
        if action not in ("BUY", "SELL"):
            continue

        entry_price = _find_closest_price(sig_ts)
        if entry_price is None:
            continue

        for horizon in horizons:
            exit_ts = sig_ts + horizon
            exit_price = _find_closest_price(exit_ts, tolerance=600)
            if exit_price is None:
                continue

            # Compute PnL
            if entry_price == 0:
                continue
            price_change = (exit_price - entry_price) / entry_price
            if action == "BUY":
                pnl = price_change
            elif action == "SELL":
                pnl = -price_change
            else:
                pnl = 0.0

            confidence = float(sig.get("conf", 0.0))
            outcome = SignalOutcome(
                signal_id=str(sig.get("_id", ""))[:8],
                action=action,
                confidence=confidence,
                entry_price=entry_price,
                exit_price=exit_price,
                pnl_pct=pnl,
                horizon_seconds=horizon,
                timestamp=sig_ts,
                resolved_at=exit_ts,
            )
            outcomes.append(outcome)

    logger.info("synthetic_outcomes_generated", count=len(outcomes))
    return outcomes


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

    # Initialize MongoDB connection using settings
    try:
        from pymongo import MongoClient

        mongo_url = settings.mongo.url
        mongo_client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
        # Verify connection
        mongo_client.admin.command("ping")
        logger.info("retrain_mongo_connected", url=mongo_url[:40])
    except Exception as e:
        logger.warning("retrain_mongo_unavailable", error=str(e))
        mongo_client = None

    # Initialize outcome store with MongoDB client
    store = OutcomeStore(
        mongo_client=mongo_client,
        database_name=settings.mongo.database,
    )

    # Fetch recent outcomes from rl_outcomes collection
    outcomes_raw = store.get_recent_outcomes(limit=500)

    if outcomes_raw:
        # Convert dicts to SignalOutcome objects
        outcomes = [
            SignalOutcome(
                signal_id=str(o.get("signal_id", "")),
                action=o.get("action", "NEUTRAL"),
                confidence=float(o.get("confidence", 0.0)),
                entry_price=float(o.get("entry_price", 0.0)),
                exit_price=float(o.get("exit_price", 0.0)),
                pnl_pct=float(o.get("pnl_pct", 0.0)),
                horizon_seconds=int(o.get("horizon_seconds", 300)),
                timestamp=float(o.get("timestamp", 0.0)),
                resolved_at=float(o.get("resolved_at", 0.0)),
            )
            for o in outcomes_raw
        ]
        logger.info("retrain_outcomes_from_store", count=len(outcomes))
    else:
        # No stored outcomes — generate from signals + candles
        logger.info("retrain_no_stored_outcomes_generating_from_signals")
        if mongo_client is not None:
            outcomes = _generate_outcomes_from_signals(mongo_client, settings)
        else:
            logger.warning("retrain_no_outcomes_no_mongo")
            store.close()
            if mongo_client:
                mongo_client.close()
            return False

    if not outcomes:
        logger.warning("retrain_no_outcomes_available")
        store.close()
        if mongo_client:
            mongo_client.close()
        return False

    logger.info(
        "retrain_starting",
        outcomes=len(outcomes),
        episodes=episodes,
        checkpoint_dir=str(checkpoint_dir),
    )

    # Train
    trainer = OfflineTrainer(episodes=episodes)
    result = trainer.train(outcomes)

    logger.info(
        "retrain_complete",
        episodes=result.episodes,
        mean_reward=result.mean_reward,
        params=result.final_params,
    )

    # Save checkpoint
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    checkpoint_path = checkpoint_dir / f"rl_agent_{timestamp}.pt"
    trainer.save_model(str(checkpoint_path))

    logger.info("retrain_checkpoint_saved", path=str(checkpoint_path))

    # Push to live system if requested
    push_status = "skipped"
    if push:
        push_status = _push_params(result.final_params, settings)

    # Store outcomes for future training runs
    store.store_batch(outcomes)
    logger.info("retrain_outcomes_stored_for_future", count=len(outcomes))

    store.close()
    if mongo_client:
        mongo_client.close()

    # Print summary for cron reporting
    print("=" * 60)
    print("RL RETRAIN SUMMARY")
    print("=" * 60)
    print(f"Episodes:       {result.episodes}")
    print(f"Total Steps:    {result.total_steps}")
    print(f"Mean Reward:    {result.mean_reward:.6f}")
    print(f"Policy Loss:    {result.mean_policy_loss:.6f}")
    print(f"Value Loss:     {result.mean_value_loss:.6f}")
    print(f"Final Params:   {result.final_params}")
    print(f"Checkpoint:     {checkpoint_path}")
    print(f"Push Status:    {push_status}")
    print(f"Outcomes Used:  {len(outcomes)}")
    print("=" * 60)

    return True


def _push_params(params: dict, settings) -> str:
    """Push updated params to the live signal system via API.

    Args:
        params: New RL params to push
        settings: System settings for API URL

    Returns:
        Status string
    """
    import httpx

    api_url = f"http://localhost:{settings.api_port}/api/v1/rl/params"
    try:
        resp = httpx.put(api_url, json=params, timeout=10.0)
        if resp.status_code == 200:
            logger.info("retrain_params_pushed", params=params)
            return "success"
        else:
            logger.warning(
                "retrain_push_failed",
                status=resp.status_code,
                body=resp.text,
            )
            return f"failed_http_{resp.status_code}"
    except Exception as e:
        logger.warning("retrain_push_error", error=str(e))
        return f"error: {e}"


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
