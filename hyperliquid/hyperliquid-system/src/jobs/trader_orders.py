"""
Trader Orders Collection Job.

This module collects order history for tracked traders.
"""

import asyncio
from datetime import datetime
from typing import Dict, List

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName


async def collect_trader_orders(
    client,
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Collect orders for all tracked traders.

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

    results = {
        "processed": 0,
        "newOrders": 0,
        "errors": 0,
    }

    semaphore = asyncio.Semaphore(settings.trader_concurrency_limit)

    batch_results = await asyncio.gather(
        *[_collect_orders_safe(client, db, addr, semaphore) for addr in addresses]
    )

    for addr, count, success in batch_results:
        results["processed"] += 1
        if success:
            results["newOrders"] += count
        else:
            results["errors"] += 1

    logger.info(
        f"Processed {results['processed']} traders, "
        f"{results['newOrders']} new orders, "
        f"{results['errors']} errors"
    )

    return {"success": True, **results}


async def _collect_orders_safe(
    client,
    db: AsyncIOMotorDatabase,
    address: str,
    semaphore: asyncio.Semaphore,
) -> tuple:
    """Safe wrapper for collecting orders."""
    async with semaphore:
        try:
            count = await _collect_single_trader_orders(client, db, address)
            return address, count, True
        except Exception as e:
            logger.warning(f"Error collecting orders for {address}: {e}")
            return address, 0, False


async def _collect_single_trader_orders(
    client,
    db: AsyncIOMotorDatabase,
    eth_address: str,
) -> int:
    """
    Collect orders for a single trader.

    Args:
        client: Hyperliquid API client
        db: MongoDB database
        eth_address: Trader's Ethereum address

    Returns:
        Count of new orders inserted
    """
    collection = db[CollectionName.TRADER_ORDERS]

    # Get last known order ID for this trader
    last_order = await collection.find_one(
        {"ethAddress": eth_address},
        sort=[("timestamp", -1)],
    )
    last_oid = last_order.get("oid", 0) if last_order else 0

    # Fetch historical orders from API
    orders_data = await client.get_historical_orders(eth_address)

    if not orders_data:
        return 0

    # Filter new orders
    new_orders = []
    for order_data in orders_data:
        order = order_data.get("order", {})
        oid = order.get("oid", 0)

        if oid <= last_oid:
            continue

        doc = {
            "ethAddress": eth_address,
            "oid": oid,
            "coin": order.get("coin"),
            "side": order.get("side"),
            "limitPx": float(order.get("limitPx", 0)),
            "sz": float(order.get("sz", 0)),
            "orderType": order.get("orderType"),
            "tif": order.get("tif"),
            "status": order_data.get("status"),
            "timestamp": datetime.utcfromtimestamp(order.get("timestamp", 0) / 1000),
            "statusTimestamp": datetime.utcfromtimestamp(
                order_data.get("statusTimestamp", 0) / 1000
            ),
            "createdAt": datetime.utcnow(),
        }
        new_orders.append(doc)

    if not new_orders:
        return 0

    # Insert with deduplication
    try:
        await collection.insert_many(new_orders, ordered=False)
    except Exception as e:
        if "duplicate key error" not in str(e).lower():
            raise

    return len(new_orders)


async def get_trader_orders(
    db: AsyncIOMotorDatabase,
    eth_address: str,
    limit: int = 100,
) -> List[Dict]:
    """
    Get recent orders for a trader.

    Args:
        db: MongoDB database
        eth_address: Trader's Ethereum address
        limit: Maximum number of orders

    Returns:
        List of order documents
    """
    collection = db[CollectionName.TRADER_ORDERS]

    cursor = (
        collection.find(
            {"ethAddress": eth_address},
        )
        .sort("timestamp", -1)
        .limit(limit)
    )

    return await cursor.to_list(length=limit)


async def get_btc_orders(
    db: AsyncIOMotorDatabase,
    hours: int = 24,
    limit: int = 500,
) -> List[Dict]:
    """
    Get recent BTC orders from all tracked traders.

    Args:
        db: MongoDB database
        hours: Hours of history
        limit: Maximum number of orders

    Returns:
        List of BTC order documents
    """
    from datetime import timedelta

    collection = db[CollectionName.TRADER_ORDERS]
    threshold = datetime.utcnow() - timedelta(hours=hours)

    cursor = (
        collection.find(
            {"coin": settings.target_coin, "timestamp": {"$gte": threshold}},
        )
        .sort("timestamp", -1)
        .limit(limit)
    )

    return await cursor.to_list(length=limit)


async def get_order_summary(
    db: AsyncIOMotorDatabase,
    eth_address: str,
) -> Dict:
    """
    Get order summary for a trader.

    Args:
        db: MongoDB database
        eth_address: Trader's Ethereum address

    Returns:
        Dictionary with order summary
    """
    collection = db[CollectionName.TRADER_ORDERS]

    pipeline = [
        {"$match": {"ethAddress": eth_address}},
        {
            "$group": {
                "_id": None,
                "totalOrders": {"$sum": 1},
                "filledOrders": {"$sum": {"$cond": [{"$eq": ["$status", "filled"]}, 1, 0]}},
                "canceledOrders": {"$sum": {"$cond": [{"$eq": ["$status", "canceled"]}, 1, 0]}},
                "buyOrders": {"$sum": {"$cond": [{"$eq": ["$side", "B"]}, 1, 0]}},
                "sellOrders": {"$sum": {"$cond": [{"$eq": ["$side", "A"]}, 1, 0]}},
            }
        },
    ]

    result = await collection.aggregate(pipeline).to_list(length=1)

    if not result:
        return {
            "totalOrders": 0,
            "filledOrders": 0,
            "canceledOrders": 0,
            "buyOrders": 0,
            "sellOrders": 0,
        }

    summary = result[0]
    del summary["_id"]

    return summary
