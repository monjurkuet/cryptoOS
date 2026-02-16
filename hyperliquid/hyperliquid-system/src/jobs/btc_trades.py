"""
BTC Trades Collection Job.

This module collects public trades for BTC.
"""

from datetime import datetime
from typing import Dict, List

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName


async def collect_trades(
    client,
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Collect and store BTC public trades.

    Args:
        client: Hyperliquid API client
        db: MongoDB database

    Returns:
        Dictionary with collection results
    """
    collection = db[CollectionName.BTC_TRADES]

    try:
        # Get last known trade ID
        last_trade = await collection.find_one(sort=[("tid", -1)])
        last_tid = last_trade["tid"] if last_trade else 0

        # Fetch trades from API
        trades_data = await client.get_trades(settings.target_coin)

        if not trades_data:
            logger.warning("No trades data received")
            return {"success": False, "error": "No data", "new_trades": 0}

        # Filter new trades
        new_trades = [trade for trade in trades_data if trade.get("tid", 0) > last_tid]

        if not new_trades:
            logger.debug("No new trades to insert")
            return {"success": True, "new_trades": 0}

        # Prepare documents
        documents = []
        for trade in new_trades:
            px = float(trade.get("px", 0))
            sz = float(trade.get("sz", 0))
            trade_time = trade.get("time", 0)

            doc = {
                "tid": trade.get("tid"),
                "t": datetime.utcfromtimestamp(trade_time / 1000)
                if trade_time
                else datetime.utcnow(),
                "px": px,
                "sz": sz,
                "side": trade.get("side"),
                "hash": trade.get("hash", ""),
                "usdValue": px * sz,
                "createdAt": datetime.utcnow(),
            }
            documents.append(doc)

        # Insert with deduplication
        try:
            await collection.insert_many(documents, ordered=False)
        except Exception as e:
            if "duplicate key error" not in str(e).lower():
                raise

        logger.info(f"Collected {len(documents)} new trades")

        return {
            "success": True,
            "new_trades": len(documents),
            "last_tid": max(t.get("tid", 0) for t in new_trades),
        }

    except Exception as e:
        logger.error(f"Error collecting trades: {e}")
        return {"success": False, "error": str(e), "new_trades": 0}


async def get_recent_trades(
    db: AsyncIOMotorDatabase,
    limit: int = 100,
) -> List[Dict]:
    """
    Get recent BTC trades.

    Args:
        db: MongoDB database
        limit: Maximum number of trades to return

    Returns:
        List of trade documents
    """
    collection = db[CollectionName.BTC_TRADES]

    cursor = collection.find().sort("t", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_trades_summary(
    db: AsyncIOMotorDatabase,
    minutes: int = 60,
) -> Dict:
    """
    Get summary of trades in the last N minutes.

    Args:
        db: MongoDB database
        minutes: Number of minutes to analyze

    Returns:
        Dictionary with trade summary
    """
    from datetime import timedelta

    collection = db[CollectionName.BTC_TRADES]
    threshold = datetime.utcnow() - timedelta(minutes=minutes)

    # Aggregate trade data
    pipeline = [
        {"$match": {"t": {"$gte": threshold}}},
        {
            "$group": {
                "_id": None,
                "count": {"$sum": 1},
                "totalVolume": {"$sum": "$sz"},
                "totalValue": {"$sum": "$usdValue"},
                "buyVolume": {"$sum": {"$cond": [{"$eq": ["$side", "B"]}, "$sz", 0]}},
                "sellVolume": {"$sum": {"$cond": [{"$eq": ["$side", "A"]}, "$sz", 0]}},
                "avgPrice": {"$avg": "$px"},
                "maxPrice": {"$max": "$px"},
                "minPrice": {"$min": "$px"},
            }
        },
    ]

    result = await collection.aggregate(pipeline).to_list(length=1)

    if not result:
        return {
            "count": 0,
            "totalVolume": 0,
            "totalValue": 0,
            "buyVolume": 0,
            "sellVolume": 0,
            "buyRatio": 0,
        }

    summary = result[0]
    total_volume = summary.get("totalVolume", 0)
    buy_volume = summary.get("buyVolume", 0)
    sell_volume = summary.get("sellVolume", 0)

    summary["buyRatio"] = buy_volume / total_volume if total_volume > 0 else 0.5
    summary["sellRatio"] = sell_volume / total_volume if total_volume > 0 else 0.5
    del summary["_id"]

    return summary
