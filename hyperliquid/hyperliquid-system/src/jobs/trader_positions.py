"""
Trader Positions Collection Job.

This module collects position snapshots for tracked traders.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName
from src.strategies.position_detection import (
    calculate_btc_exposure,
    calculate_account_summary,
    detect_position_changes,
    get_position_for_coin,
)


async def collect_all_positions(
    client,
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Collect positions for all tracked traders.

    Args:
        client: Hyperliquid API client
        db: MongoDB database

    Returns:
        Dictionary with collection results
    """
    from src.jobs.leaderboard import get_tracked_trader_addresses

    # Get tracked trader addresses
    addresses = await get_tracked_trader_addresses(db, active_only=True)

    if not addresses:
        logger.warning("No tracked traders found")
        return {"success": False, "error": "No traders", "processed": 0}

    # Collect positions concurrently
    results = {
        "processed": 0,
        "errors": 0,
        "positionChanges": 0,
    }

    semaphore = asyncio.Semaphore(settings.trader_concurrency_limit)

    batch_results = await asyncio.gather(
        *[_process_trader_safe(client, db, addr, semaphore) for addr in addresses]
    )

    for addr, changes, success in batch_results:
        results["processed"] += 1
        if success:
            results["positionChanges"] += changes
        else:
            results["errors"] += 1

    logger.info(
        f"Processed {results['processed']} traders, "
        f"{results['positionChanges']} position changes, "
        f"{results['errors']} errors"
    )

    return {"success": True, **results}


async def _process_trader_safe(
    client,
    db: AsyncIOMotorDatabase,
    address: str,
    semaphore: asyncio.Semaphore,
) -> Tuple[str, int, bool]:
    """Safe wrapper for processing a single trader."""
    async with semaphore:
        try:
            changes = await _collect_single_trader_position(client, db, address)
            return address, len(changes), True
        except Exception as e:
            logger.warning(f"Error processing trader {address}: {e}")
            return address, 0, False


async def _collect_single_trader_position(
    client,
    db: AsyncIOMotorDatabase,
    eth_address: str,
) -> List[Dict]:
    """
    Collect position for a single trader.

    Args:
        client: Hyperliquid API client
        db: MongoDB database
        eth_address: Trader's Ethereum address

    Returns:
        List of position changes detected
    """
    positions_collection = db[CollectionName.TRADER_POSITIONS]
    current_state_collection = db[CollectionName.TRADER_CURRENT_STATE]

    # Fetch current state from API
    state = await client.get_clearinghouse_state(eth_address)

    # Get previous state from database
    prev_state = await current_state_collection.find_one({"ethAddress": eth_address})

    # Detect position changes
    changes = detect_position_changes(prev_state, state)

    # Extract positions
    positions = []
    for pos in state.get("assetPositions", []):
        position = pos.get("position", {})
        positions.append(
            {
                "coin": position.get("coin"),
                "szi": float(position.get("szi", 0)),
                "entryPx": float(position.get("entryPx", 0)),
                "positionValue": float(position.get("positionValue", 0)),
                "unrealizedPnl": float(position.get("unrealizedPnl", 0)),
                "leverage": _extract_leverage(position),
                "liquidationPx": position.get("liquidationPx"),
                "marginUsed": float(position.get("marginUsed", 0)),
            }
        )

    # Calculate BTC exposure
    btc_exposure = calculate_btc_exposure(positions)

    # Get account summary
    margin_summary = state.get("marginSummary", {})

    # Store position snapshot
    snapshot = {
        "ethAddress": eth_address,
        "t": datetime.utcnow(),
        "accountValue": float(margin_summary.get("accountValue", 0)),
        "totalNotionalPos": float(margin_summary.get("totalNtlPos", 0)),
        "marginUsed": float(margin_summary.get("totalMarginUsed", 0)),
        "positions": positions,
        "btcExposure": btc_exposure,
        "createdAt": datetime.utcnow(),
    }

    await positions_collection.insert_one(snapshot)

    # Update current state
    current_state = {
        "ethAddress": eth_address,
        "accountValue": snapshot["accountValue"],
        "positions": positions,
        "btcExposure": btc_exposure,
        "updatedAt": datetime.utcnow(),
    }

    await current_state_collection.replace_one(
        {"ethAddress": eth_address},
        current_state,
        upsert=True,
    )

    # Generate signals for position changes
    if changes:
        await _generate_change_signals(db, eth_address, changes, state)

    return changes


def _extract_leverage(position: Dict) -> float:
    """Extract leverage from position data."""
    leverage = position.get("leverage", {})
    if isinstance(leverage, dict):
        return float(leverage.get("value", 0))
    return float(leverage) if leverage else 0


async def _generate_change_signals(
    db: AsyncIOMotorDatabase,
    eth_address: str,
    changes: List[Dict],
    state: Dict,
) -> None:
    """Generate signals for position changes."""
    from src.strategies.signal_generation import generate_individual_signal
    from src.jobs.btc_ticker import get_current_price

    signals_collection = db[CollectionName.BTC_SIGNALS]

    # Get current BTC price with error handling
    try:
        current_price = await get_current_price(db)
    except Exception as e:
        logger.warning(f"Failed to get current price for signals: {e}")
        current_price = None

    # Get trader score
    tracked_collection = db[CollectionName.TRACKED_TRADERS]
    trader = await tracked_collection.find_one({"ethAddress": eth_address})
    trader_score = trader.get("score", 50) if trader else 50

    for change in changes:
        # Only generate signals for BTC
        if change.get("coin") != "BTC":
            continue

        signal = generate_individual_signal(
            eth_address=eth_address,
            position_change=change,
            trader_score=trader_score,
            current_price=current_price,
        )

        if signal:
            await signals_collection.insert_one(signal)


async def get_trader_positions(
    db: AsyncIOMotorDatabase,
    eth_address: str,
    hours: int = 24,
) -> List[Dict]:
    """
    Get position history for a trader.

    Args:
        db: MongoDB database
        eth_address: Trader's Ethereum address
        hours: Hours of history to retrieve

    Returns:
        List of position snapshots
    """
    from datetime import timedelta

    collection = db[CollectionName.TRADER_POSITIONS]
    threshold = datetime.utcnow() - timedelta(hours=hours)

    cursor = collection.find(
        {"ethAddress": eth_address, "t": {"$gte": threshold}},
    ).sort("t", -1)

    return await cursor.to_list(length=None)


async def get_all_btc_exposures(
    db: AsyncIOMotorDatabase,
) -> Dict[str, float]:
    """
    Get BTC exposure for all tracked traders.

    Args:
        db: MongoDB database

    Returns:
        Dictionary mapping address to BTC exposure
    """
    collection = db[CollectionName.TRADER_CURRENT_STATE]

    cursor = collection.find({}, {"ethAddress": 1, "btcExposure": 1})
    docs = await cursor.to_list(length=None)

    return {doc["ethAddress"]: doc.get("btcExposure", 0) for doc in docs}
