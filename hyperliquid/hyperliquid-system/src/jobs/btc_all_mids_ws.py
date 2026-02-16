"""
All Mids (Mark Prices) WebSocket Collection Job.

This module collects real-time mark prices for all coins using WebSocket.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName
from src.api.websocket import WebSocketManager


class AllMidsWebSocketCollector:
    """
    Real-time mark prices collector using WebSocket.

    Subscribes to allMids for real-time price updates across all coins.
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        ws_manager: WebSocketManager,
    ):
        """
        Initialize the allMids collector.

        Args:
            db: MongoDB database
            ws_manager: WebSocket manager instance
        """
        self.db = db
        self.ws_manager = ws_manager
        self.collection = db[CollectionName.ALL_MIDS]
        self._running = False

        # Track prices for change detection
        self._previous_prices: Dict[str, float] = {}

        # Buffer for batch insertion
        self._price_buffer: List[Dict] = []
        self._buffer_size = 50
        self._buffer_timeout = 10.0  # seconds

    async def start(self) -> None:
        """Start collecting allMids data via WebSocket."""
        if self._running:
            logger.warning("AllMids collector already running")
            return

        self._running = True

        # Subscribe to allMids updates
        await self.ws_manager.subscribe_all_mids(
            handler=self._handle_all_mids,
        )

        logger.info("Started WebSocket allMids collector")

        # Start buffer flush task
        asyncio.create_task(self._periodic_flush())

    async def stop(self) -> None:
        """Stop collecting allMids data."""
        self._running = False
        # Flush remaining buffer
        await self._flush_buffer()
        logger.info("Stopped WebSocket allMids collector")

    async def _handle_all_mids(self, data: Any) -> None:
        """
        Handle incoming allMids data from WebSocket.

        Args:
            data: AllMids data from WebSocket
        """
        try:
            # Format: {"mids": {"BTC": "95420.5", "ETH": "3245.0", ...}}
            if isinstance(data, dict):
                mids = data.get("mids", {})

                if not mids:
                    return

                now = datetime.utcnow()

                for coin, price_str in mids.items():
                    try:
                        price = float(price_str)
                        previous_price = self._previous_prices.get(coin)

                        # Only record if price changed
                        if previous_price is None or price != previous_price:
                            doc = {
                                "t": now,
                                "coin": coin,
                                "price": price,
                                "previousPrice": previous_price,
                                "change": price - previous_price if previous_price else 0,
                                "changePercent": ((price - previous_price) / previous_price * 100)
                                if previous_price and previous_price != 0
                                else 0,
                                "createdAt": now,
                                "source": "websocket",
                            }

                            self._price_buffer.append(doc)
                            self._previous_prices[coin] = price

                            # Log significant changes
                            if coin == settings.target_coin:
                                logger.debug(f"WS BTC price: ${price:.2f}")

                    except (ValueError, TypeError) as e:
                        continue

        except Exception as e:
            logger.error(f"Error handling allMids data: {e}")

    async def _periodic_flush(self) -> None:
        """Periodically flush price buffer to database."""
        while self._running:
            await asyncio.sleep(self._buffer_timeout)
            await self._flush_buffer()

    async def _flush_buffer(self) -> None:
        """Flush buffered prices to database."""
        if not self._price_buffer:
            return

        prices_to_insert = self._price_buffer.copy()
        self._price_buffer.clear()

        if not prices_to_insert:
            return

        try:
            # Insert all prices
            await self.collection.insert_many(prices_to_insert, ordered=False)
            logger.debug(f"Flushed {len(prices_to_insert)} price updates to database")
        except Exception as e:
            if "duplicate key error" not in str(e).lower():
                logger.error(f"Error inserting price updates: {e}")

    def get_current_price(self, coin: str = None) -> Optional[float]:
        """
        Get current price for a coin.

        Args:
            coin: Coin symbol (default: target coin)

        Returns:
            Current price or None
        """
        coin = coin or settings.target_coin
        return self._previous_prices.get(coin)


async def get_current_price_from_ws(
    db: AsyncIOMotorDatabase,
    coin: str = None,
) -> float:
    """
    Get current price from the latest allMids data.
    This is a fallback to the REST-based get_current_price.

    Args:
        db: MongoDB database
        coin: Coin symbol (default: target coin)

    Returns:
        Current price or 0 if not available
    """
    coin = coin or settings.target_coin
    collection = db[CollectionName.ALL_MIDS]

    latest = await collection.find_one(
        {"coin": coin},
        sort=[("t", -1)],
    )

    if latest:
        return latest.get("price", 0)
    return 0
