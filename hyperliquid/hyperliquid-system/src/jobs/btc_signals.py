"""
BTC Signals Generation Job.

This module generates trading signals from trader position data.
"""

from datetime import datetime
from typing import Dict, List, Optional

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName
from src.strategies.signal_generation import (
    calculate_signal_metrics,
    generate_aggregated_signal,
    should_generate_alert,
)
from src.jobs.btc_ticker import get_current_price


async def generate_signals(
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Generate aggregated BTC signal from all tracked trader positions.

    Args:
        db: MongoDB database

    Returns:
        Dictionary with signal generation results
    """
    signals_collection = db[CollectionName.BTC_SIGNALS]
    tracked_collection = db[CollectionName.TRACKED_TRADERS]
    current_state_collection = db[CollectionName.TRADER_CURRENT_STATE]

    try:
        # Get all active tracked traders
        cursor = tracked_collection.find({"isActive": True}, {"ethAddress": 1, "score": 1})
        traders = await cursor.to_list(length=None)

        if not traders:
            logger.warning("No active tracked traders")
            return {"success": False, "error": "No traders"}

        # Get current states
        trader_states = {}
        trader_scores = {}

        for trader in traders:
            address = trader["ethAddress"]
            state = await current_state_collection.find_one({"ethAddress": address})

            if state:
                trader_states[address] = state
                trader_scores[address] = trader.get("score", 50)

        if not trader_states:
            logger.warning("No trader states found")
            return {"success": False, "error": "No states"}

        # Get current BTC price
        current_price = await get_current_price(db)

        # Generate aggregated signal
        signal = await generate_aggregated_signal(
            trader_states=trader_states,
            trader_scores=trader_scores,
            current_price=current_price,
        )

        # Store signal
        await signals_collection.insert_one(signal)

        # Get previous signal for comparison
        prev_signal = await signals_collection.find_one(
            {"signalType": "aggregated_bias"},
            sort=[("t", -1)],
        )

        # Check if alert should be generated
        if should_generate_alert(signal, prev_signal):
            logger.info(
                f"ALERT: {signal['recommendation']} signal "
                f"(long={signal['longBias']:.1%}, short={signal['shortBias']:.1%}, "
                f"confidence={signal['confidence']:.1%})"
            )

        logger.info(
            f"Generated signal: {signal['recommendation']} "
            f"(L:{signal['tradersLong']} S:{signal['tradersShort']} F:{signal['tradersFlat']})"
        )

        return {
            "success": True,
            "recommendation": signal["recommendation"],
            "confidence": signal["confidence"],
            "tradersLong": signal["tradersLong"],
            "tradersShort": signal["tradersShort"],
            "tradersFlat": signal["tradersFlat"],
        }

    except Exception as e:
        logger.error(f"Error generating signals: {e}")
        return {"success": False, "error": str(e)}


async def get_recent_signals(
    db: AsyncIOMotorDatabase,
    hours: int = 24,
    limit: int = 100,
) -> List[Dict]:
    """
    Get recent BTC signals.

    Args:
        db: MongoDB database
        hours: Hours of history
        limit: Maximum number of signals

    Returns:
        List of signal documents
    """
    from datetime import timedelta

    collection = db[CollectionName.BTC_SIGNALS]
    threshold = datetime.utcnow() - timedelta(hours=hours)

    cursor = (
        collection.find(
            {"t": {"$gte": threshold}},
        )
        .sort("t", -1)
        .limit(limit)
    )

    return await cursor.to_list(length=limit)


async def get_latest_signal(
    db: AsyncIOMotorDatabase,
) -> Optional[Dict]:
    """
    Get the latest aggregated BTC signal.

    Args:
        db: MongoDB database

    Returns:
        Latest signal document or None
    """
    collection = db[CollectionName.BTC_SIGNALS]

    return await collection.find_one(
        {"signalType": "aggregated_bias"},
        sort=[("t", -1)],
    )


async def get_signal_history(
    db: AsyncIOMotorDatabase,
    days: int = 7,
) -> List[Dict]:
    """
    Get signal history for analysis.

    Args:
        db: MongoDB database
        days: Days of history

    Returns:
        List of signal documents
    """
    from datetime import timedelta

    collection = db[CollectionName.BTC_SIGNALS]
    threshold = datetime.utcnow() - timedelta(days=days)

    cursor = collection.find(
        {"signalType": "aggregated_bias", "t": {"$gte": threshold}},
        {
            "t": 1,
            "recommendation": 1,
            "confidence": 1,
            "longBias": 1,
            "shortBias": 1,
            "tradersLong": 1,
            "tradersShort": 1,
            "price": 1,
        },
    ).sort("t", 1)

    return await cursor.to_list(length=None)


async def get_signal_statistics(
    db: AsyncIOMotorDatabase,
    days: int = 30,
) -> Dict:
    """
    Get signal statistics for the past N days.

    Args:
        db: MongoDB database
        days: Days to analyze

    Returns:
        Dictionary with signal statistics
    """
    from datetime import timedelta

    collection = db[CollectionName.BTC_SIGNALS]
    threshold = datetime.utcnow() - timedelta(days=days)

    pipeline = [
        {"$match": {"t": {"$gte": threshold}, "signalType": "aggregated_bias"}},
        {
            "$group": {
                "_id": "$recommendation",
                "count": {"$sum": 1},
                "avgConfidence": {"$avg": "$confidence"},
            }
        },
    ]

    results = await collection.aggregate(pipeline).to_list(length=None)

    stats = {
        "LONG": {"count": 0, "avgConfidence": 0},
        "SHORT": {"count": 0, "avgConfidence": 0},
        "NEUTRAL": {"count": 0, "avgConfidence": 0},
    }

    for r in results:
        rec = r["_id"]
        if rec in stats:
            stats[rec] = {
                "count": r["count"],
                "avgConfidence": r["avgConfidence"],
            }

    total = sum(s["count"] for s in stats.values())
    stats["total"] = total

    return stats
