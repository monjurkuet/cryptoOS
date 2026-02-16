"""
BTC Candles WebSocket Collection Job.

This module collects candle data in real-time using WebSocket.
Replaces REST polling with WebSocket for real-time updates.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName
from src.api.websocket import WebSocketManager


class CandleWebSocketCollector:
    """
    Real-time candles collector using WebSocket.

    Subscribes to candle updates for multiple intervals and stores them.
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        ws_manager: WebSocketManager,
    ):
        """
        Initialize the candles collector.

        Args:
            db: MongoDB database
            ws_manager: WebSocket manager instance
        """
        self.db = db
        self.ws_manager = ws_manager
        self.intervals = settings.candle_intervals  # ["1m", "5m", "15m", "1h", "4h", "1d"]
        self._running = False

        # Buffer for batch insertion
        self._candle_buffers: Dict[str, List[Dict]] = {interval: [] for interval in self.intervals}
        self._buffer_size = 10
        self._buffer_timeout = 5.0  # seconds

    async def start(self) -> None:
        """Start collecting candle data via WebSocket."""
        if self._running:
            logger.warning("Candle collector already running")
            return

        self._running = True

        # Subscribe to candle updates for each interval using the proper method
        for interval in self.intervals:
            # Use a lambda to capture the interval properly
            handler = lambda data, iv=interval: asyncio.create_task(self._handle_candle(data, iv))
            await self.ws_manager.subscribe_candles(
                coin=settings.target_coin,
                interval=interval,
                handler=handler,
            )
            logger.info(f"Started WebSocket candle collector for {settings.target_coin} {interval}")

        # Start buffer flush task
        asyncio.create_task(self._periodic_flush())

        logger.info(f"Started WebSocket candle collector for all intervals")

    async def stop(self) -> None:
        """Stop collecting candle data."""
        self._running = False
        # Flush remaining buffers
        await self._flush_all_buffers()
        logger.info("Stopped WebSocket candle collector")

    async def _handle_candle(self, data: Any, interval: str) -> None:
        """
        Handle incoming candle data from WebSocket.

        Args:
            data: Candle data from WebSocket
            interval: Candle interval
        """
        try:
            # WebSocket format: Array of candle objects or single candle
            candles_data = []

            if isinstance(data, list):
                candles_data = data
            elif isinstance(data, dict):
                # Single candle object
                candles_data = [data]

            for candle in candles_data:
                try:
                    # Parse candle data
                    # Format: {t, T, s, i, o, c, h, l, v, n}
                    doc = {
                        "t": datetime.utcfromtimestamp(candle.get("t", 0) / 1000),
                        "T": datetime.utcfromtimestamp(candle.get("T", 0) / 1000),
                        "coin": candle.get("s"),
                        "interval": interval,
                        "open": float(candle.get("o", 0)),
                        "close": float(candle.get("c", 0)),
                        "high": float(candle.get("h", 0)),
                        "low": float(candle.get("l", 0)),
                        "volume": float(candle.get("v", 0)),
                        "trades": int(candle.get("n", 0)),
                        "createdAt": datetime.utcnow(),
                        "source": "websocket",
                    }

                    # Add to buffer
                    self._candle_buffers[interval].append(doc)

                    # Log debug
                    logger.debug(
                        f"WS Candle {interval}: {doc['close']:.2f}, vol={doc['volume']:.4f}"
                    )

                except (ValueError, TypeError) as e:
                    logger.warning(f"Error parsing candle: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error handling candle data: {e}")

    async def _periodic_flush(self) -> None:
        """Periodically flush candle buffers to database."""
        while self._running:
            await asyncio.sleep(self._buffer_timeout)
            await self._flush_all_buffers()

    async def _flush_all_buffers(self) -> None:
        """Flush all interval buffers to database."""
        for interval, buffer in self._candle_buffers.items():
            if buffer:
                await self._flush_buffer(interval, buffer.copy())
                self._candle_buffers[interval].clear()

    async def _flush_buffer(self, interval: str, candles: List[Dict]) -> None:
        """Flush candles for a specific interval to database."""
        if not candles:
            return

        try:
            collection = self.db[CollectionName.BTC_CANDLES.format(interval=interval)]
            await collection.insert_many(candles, ordered=False)
            logger.debug(f"Flushed {len(candles)} {interval} candles to database")
        except Exception as e:
            if "duplicate key error" not in str(e).lower():
                logger.error(f"Error inserting {interval} candles: {e}")
            else:
                logger.debug(f"Some {interval} candles were duplicates")


# =============================================================================
# REST Fallback - Keep for when WebSocket is unavailable
# =============================================================================


async def collect_candles(
    client,
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Collect and store BTC candles using REST API (fallback).

    Args:
        client: Hyperliquid API client
        db: MongoDB database

    Returns:
        Dictionary with collection results
    """
    from src.jobs.btc_candles import collect_candles as rest_collect_candles

    # Use REST-based collector as fallback
    return await rest_collect_candles(client, db)
