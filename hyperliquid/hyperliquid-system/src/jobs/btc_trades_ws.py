"""
BTC Trades WebSocket Collection Job.

This module collects trades in real-time using WebSocket.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName
from src.api.websocket import WebSocketManager


class TradesWebSocketCollector:
    """
    Real-time trades collector using WebSocket.

    This collector maintains a persistent WebSocket connection and
    processes trades as they occur.
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        ws_manager: WebSocketManager,
    ):
        """
        Initialize the trades collector.

        Args:
            db: MongoDB database
            ws_manager: WebSocket manager instance
        """
        self.db = db
        self.ws_manager = ws_manager
        self.collection = db[CollectionName.BTC_TRADES]
        self._running = False

        # Track last trade ID to avoid duplicates
        self._last_tid: int = 0

        # Buffer for batch insertion
        self._trade_buffer: List[Dict] = []
        self._buffer_timeout = 5.0  # seconds

    async def start(self) -> None:
        """Start collecting trades data via WebSocket."""
        if self._running:
            logger.warning("Trades collector already running")
            return

        # Get last trade ID from database
        await self._load_last_tid()

        self._running = True

        # Subscribe to trades updates
        await self.ws_manager.subscribe_trades(
            coin=settings.target_coin,
            handler=self._handle_trade,
        )

        # Start buffer flush task
        asyncio.create_task(self._periodic_flush())

        logger.info(f"Started WebSocket trades collector for {settings.target_coin}")

    async def stop(self) -> None:
        """Stop collecting trades data."""
        self._running = False
        # Flush remaining buffer
        await self._flush_buffer()
        logger.info("Stopped WebSocket trades collector")

    async def _load_last_tid(self) -> None:
        """Load the last trade ID from database."""
        try:
            last_trade = await self.collection.find_one(sort=[("tid", -1)])
            if last_trade:
                self._last_tid = last_trade.get("tid", 0)
                logger.debug(f"Loaded last trade ID: {self._last_tid}")
        except Exception as e:
            logger.warning(f"Could not load last trade ID: {e}")

    async def _handle_trade(self, data: Dict) -> None:
        """
        Handle incoming trade data from WebSocket.
        Only stores trades with USD value >= threshold ($1,000).
        """
        try:
            # Extract trade data
            trades_data = None
            if isinstance(data, dict):
                if "data" in data:
                    trades_data = data["data"]
                elif isinstance(data.get("events"), list):
                    trades_data = data.get("events", [])
            elif isinstance(data, list):
                trades_data = data

            if trades_data is None:
                return

            # Handle both single trade and array of trades
            if not isinstance(trades_data, list):
                trades_data = [trades_data]

            new_trades = []
            skipped_count = 0

            for trade in trades_data:
                tid = trade.get("tid", 0)

                # Skip duplicates
                if tid <= self._last_tid:
                    continue

                px = float(trade.get("px", 0))
                sz = float(trade.get("sz", 0))
                usd_value = px * sz

                # FILTER: Only store trades >= threshold
                if usd_value < settings.trade_min_value_usd:
                    skipped_count += 1
                    continue

                trade_time = trade.get("time", 0)

                doc = {
                    "tid": tid,
                    "t": datetime.utcfromtimestamp(trade_time / 1000)
                    if trade_time
                    else datetime.utcnow(),
                    "px": px,
                    "sz": sz,
                    "side": trade.get("side"),
                    "hash": trade.get("hash", ""),
                    "usdValue": usd_value,
                    "createdAt": datetime.utcnow(),
                    "source": "websocket",
                }

                new_trades.append(doc)
                self._trade_buffer.append(doc)

                if tid > self._last_tid:
                    self._last_tid = tid

            if new_trades:
                logger.info(
                    f"WS Trade: {len(new_trades)} trades stored (>= ${settings.trade_min_value_usd:,.0f}), "
                    f"{skipped_count} skipped (< ${settings.trade_min_value_usd:,.0f}), "
                    f"last tid={self._last_tid}"
                )
            elif skipped_count > 0:
                logger.debug(
                    f"WS Trade: {skipped_count} small trades skipped (< ${settings.trade_min_value_usd:,.0f})"
                )

        except Exception as e:
            logger.error(f"Error handling trade data: {e}")

    async def _periodic_flush(self) -> None:
        """Periodically flush trade buffer to database."""
        while self._running:
            await asyncio.sleep(self._buffer_timeout)
            await self._flush_buffer()

    async def _flush_buffer(self) -> None:
        """Flush buffered trades to database."""
        if not self._trade_buffer:
            return

        trades_to_insert = self._trade_buffer.copy()
        self._trade_buffer.clear()

        if not trades_to_insert:
            return

        try:
            # Insert with deduplication (in case of duplicates)
            await self.collection.insert_many(trades_to_insert, ordered=False)
            logger.info(f"Flushed {len(trades_to_insert)} trades to database")
        except Exception as e:
            if "duplicate key error" not in str(e).lower():
                logger.error(f"Error inserting trades: {e}")
            else:
                logger.debug("Some trades were duplicates (already in DB)")

    async def get_recent_trades(
        self,
        limit: int = 100,
    ) -> List[Dict]:
        """
        Get recent BTC trades.

        Args:
            limit: Maximum number of trades to return

        Returns:
            List of trade documents
        """
        cursor = self.collection.find().sort("t", -1).limit(limit)
        return await cursor.to_list(length=limit)


# =============================================================================
# Backward compatibility - Keep REST-based collector as fallback
# =============================================================================


async def collect_trades(
    client,
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Collect and store BTC public trades (REST fallback).

    This is kept for backward compatibility when WebSocket is unavailable.

    Args:
        client: Hyperliquid API client
        db: MongoDB database

    Returns:
        Dictionary with collection results
    """
    from src.jobs.btc_trades import collect_trades as rest_collect_trades

    # Use REST-based collector as fallback
    return await rest_collect_trades(client, db)
