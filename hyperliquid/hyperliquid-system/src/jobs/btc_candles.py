"""
BTC Candles Collection Job.

This module collects OHLCV candle data for BTC across all intervals.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName
from src.utils.helpers import datetime_to_timestamp, timestamp_to_datetime


async def collect_candles(
    client,
    db: AsyncIOMotorDatabase,
    intervals: List[str] = None,
) -> Dict[str, int]:
    """
    Collect candles for all intervals.

    Args:
        client: Hyperliquid API client
        db: MongoDB database
        intervals: List of intervals to collect (default: from settings)

    Returns:
        Dictionary with count of new candles per interval
    """
    intervals = intervals or settings.candle_intervals
    results = {}

    collection = db[CollectionName.BTC_CANDLES]

    for interval in intervals:
        try:
            count = await _collect_candles_for_interval(
                client=client,
                collection=collection,
                interval=interval,
            )
            results[interval] = count
            logger.info(f"Collected {count} new candles for {interval}")
        except Exception as e:
            logger.error(f"Error collecting candles for {interval}: {e}")
            results[interval] = 0

    return results


async def _collect_candles_for_interval(
    client,
    collection,
    interval: str,
) -> int:
    """
    Collect candles for a single interval.

    Args:
        client: Hyperliquid API client
        collection: MongoDB collection
        interval: Candle interval

    Returns:
        Count of new candles inserted
    """
    # Get the last candle timestamp for this interval
    last_candle = await collection.find_one(
        {"interval": interval},
        sort=[("t", -1)],
    )

    # Calculate start time
    if last_candle:
        # Start from last candle + interval
        last_time = last_candle["t"]
        start_time = datetime_to_timestamp(last_time) + _get_interval_ms(interval)
    else:
        # First run: get last 500 candles (API limit)
        interval_ms = _get_interval_ms(interval)
        start_time = datetime_to_timestamp(datetime.utcnow()) - (500 * interval_ms)

    # Fetch candles from API
    candles_data = await client.get_candles(
        coin=settings.target_coin,
        interval=interval,
        start_time=start_time,
    )

    if not candles_data:
        return 0

    # Prepare documents
    documents = []
    for candle in candles_data:
        doc = {
            "t": timestamp_to_datetime(candle["t"]),
            "interval": candle.get("i", interval),
            "o": float(candle["o"]),
            "h": float(candle["h"]),
            "l": float(candle["l"]),
            "c": float(candle["c"]),
            "v": float(candle["v"]),
            "n": candle.get("n", 0),  # number of trades
            "createdAt": datetime.utcnow(),
        }
        documents.append(doc)

    # Insert with deduplication
    if documents:
        try:
            await collection.insert_many(documents, ordered=False)
        except Exception as e:
            # Handle duplicate key errors
            if "duplicate key error" not in str(e).lower():
                raise

    return len(documents)


async def backfill_candles(
    client,
    db: AsyncIOMotorDatabase,
    start_date: datetime,
    intervals: List[str] = None,
) -> Dict[str, int]:
    """
    Backfill historical candles from a start date.

    Args:
        client: Hyperliquid API client
        db: MongoDB database
        start_date: Start date for backfill
        intervals: List of intervals to backfill

    Returns:
        Dictionary with count of candles per interval
    """
    intervals = intervals or settings.candle_intervals
    results = {}
    collection = db[CollectionName.BTC_CANDLES]

    for interval in intervals:
        try:
            count = 0
            interval_ms = _get_interval_ms(interval)
            current_time = datetime_to_timestamp(start_date)
            end_time = datetime_to_timestamp(datetime.utcnow())

            while current_time < end_time:
                candles_data = await client.get_candles(
                    coin=settings.target_coin,
                    interval=interval,
                    start_time=current_time,
                )

                if not candles_data:
                    break

                documents = []
                for candle in candles_data:
                    doc = {
                        "t": timestamp_to_datetime(candle["t"]),
                        "interval": interval,
                        "o": float(candle["o"]),
                        "h": float(candle["h"]),
                        "l": float(candle["l"]),
                        "c": float(candle["c"]),
                        "v": float(candle["v"]),
                        "createdAt": datetime.utcnow(),
                    }
                    documents.append(doc)

                if documents:
                    try:
                        await collection.insert_many(documents, ordered=False)
                        count += len(documents)
                    except Exception as e:
                        if "duplicate key error" not in str(e).lower():
                            raise

                # Move to next batch
                last_ts = max(c["t"] for c in candles_data)
                current_time = last_ts + interval_ms

                # Rate limiting
                await _sleep(0.1)

            results[interval] = count
            logger.info(f"Backfilled {count} candles for {interval}")

        except Exception as e:
            logger.error(f"Error backfilling candles for {interval}: {e}")
            results[interval] = 0

    return results


def _get_interval_ms(interval: str) -> int:
    """Convert interval string to milliseconds."""
    mapping = {
        "1m": 60 * 1000,
        "5m": 5 * 60 * 1000,
        "15m": 15 * 60 * 1000,
        "1h": 60 * 60 * 1000,
        "4h": 4 * 60 * 60 * 1000,
        "1d": 24 * 60 * 60 * 1000,
    }
    return mapping.get(interval, 60 * 1000)


async def _sleep(seconds: float):
    """Async sleep helper."""
    await asyncio.sleep(seconds)
