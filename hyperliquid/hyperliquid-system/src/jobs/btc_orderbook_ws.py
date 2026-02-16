"""
BTC Orderbook WebSocket Collection Job.

This module collects orderbook snapshots in real-time using WebSocket.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName
from src.api.websocket import WebSocketManager


class OrderbookWebSocketCollector:
    """
    Real-time orderbook collector using WebSocket.

    Optimized to only save on significant price changes (>1%)
    or maximum interval (600 seconds).
    """

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        ws_manager: WebSocketManager,
    ):
        """
        Initialize the orderbook collector.

        Args:
            db: MongoDB database
            ws_manager: WebSocket manager instance
        """
        self.db = db
        self.ws_manager = ws_manager
        self.collection = db[CollectionName.BTC_ORDERBOOK]
        self._running = False

        # Optimization: Track last saved state
        self._last_mid_price: float = 0.0
        self._last_save_time: datetime = datetime.min
        self._price_change_threshold = (
            settings.orderbook_price_change_threshold_pct / 100
        )  # Convert % to decimal
        self._max_save_interval = settings.orderbook_max_save_interval

        # Buffer for current orderbook (always keep latest in memory)
        self._latest_orderbook: Optional[Dict] = None

    async def start(self) -> None:
        """Start collecting orderbook data via WebSocket."""
        if self._running:
            logger.warning("Orderbook collector already running")
            return

        self._running = True
        self._last_save_time = datetime.utcnow()

        # Subscribe to orderbook updates
        await self.ws_manager.subscribe_orderbook(
            coin=settings.target_coin,
            handler=self._handle_orderbook,
        )

        logger.info(f"Started optimized WebSocket orderbook collector for {settings.target_coin}")
        logger.info(
            f"Save threshold: {settings.orderbook_price_change_threshold_pct}% change or {self._max_save_interval}s max interval"
        )

    async def stop(self) -> None:
        """Stop collecting orderbook data."""
        self._running = False
        # Save final snapshot if we have one
        if self._latest_orderbook:
            try:
                await self.collection.insert_one(self._latest_orderbook)
                logger.info("Saved final orderbook snapshot on shutdown")
            except Exception as e:
                logger.error(f"Error saving final orderbook: {e}")
        logger.info("Stopped WebSocket orderbook collector")

    async def _handle_orderbook(self, data: Dict) -> None:
        """
        Handle incoming orderbook data from WebSocket.
        Only saves to database on significant price changes or max interval.
        """
        try:
            # Extract orderbook data
            orderbook_data = None
            if isinstance(data, dict):
                if "data" in data:
                    orderbook_data = data["data"]
                elif "levels" in data:
                    orderbook_data = data

            if orderbook_data is None:
                return

            # Parse levels
            levels = orderbook_data.get("levels", [])
            asks = levels[0] if len(levels) > 0 else []
            bids = levels[1] if len(levels) > 1 else []

            # Calculate derived metrics
            bid_levels = _parse_levels(bids)
            ask_levels = _parse_levels(asks)

            if not bid_levels or not ask_levels:
                return

            spread = ask_levels[0]["px"] - bid_levels[0]["px"]
            mid_price = (ask_levels[0]["px"] + bid_levels[0]["px"]) / 2

            bid_depth = sum(level["sz"] for level in bid_levels)
            ask_depth = sum(level["sz"] for level in ask_levels)
            total_depth = bid_depth + ask_depth
            imbalance = (bid_depth - ask_depth) / total_depth if total_depth > 0 else 0

            # Create document
            doc = {
                "t": datetime.utcnow(),
                "bids": bid_levels[:50],  # Top 50 levels
                "asks": ask_levels[:50],
                "spread": spread,
                "midPrice": mid_price,
                "bidDepth": bid_depth,
                "askDepth": ask_depth,
                "imbalance": imbalance,
                "createdAt": datetime.utcnow(),
                "source": "websocket",
            }

            # Always keep latest in memory
            self._latest_orderbook = doc

            # Determine if we should save to DB
            current_time = datetime.utcnow()
            time_since_last_save = (current_time - self._last_save_time).total_seconds()

            # Check price change
            price_change_pct = 0.0
            if self._last_mid_price > 0:
                price_change_pct = abs(mid_price - self._last_mid_price) / self._last_mid_price
            else:
                price_change_pct = 1.0  # Force save on first valid data

            # Save if: significant price change OR max interval reached
            should_save = (
                price_change_pct >= self._price_change_threshold
                or time_since_last_save >= self._max_save_interval
            )

            if should_save:
                try:
                    await self.collection.insert_one(doc)
                    self._last_mid_price = mid_price
                    self._last_save_time = current_time
                    logger.info(
                        f"Orderbook saved: mid=${mid_price:.2f}, "
                        f"change={price_change_pct * 100:.2f}%, "
                        f"interval={time_since_last_save:.0f}s"
                    )
                except Exception as e:
                    logger.error(f"Error saving orderbook: {e}")
            else:
                logger.debug(
                    f"Orderbook skipped: mid=${mid_price:.2f}, "
                    f"change={price_change_pct * 100:.2f}% (< {self._price_change_threshold * 100}%), "
                    f"interval={time_since_last_save:.0f}s"
                )

        except Exception as e:
            logger.error(f"Error handling orderbook data: {e}")

    async def get_latest_orderbook(self) -> Optional[Dict]:
        """Get the latest orderbook snapshot (from memory)."""
        return self._latest_orderbook


def _parse_levels(levels: List) -> List[Dict]:
    """
    Parse orderbook levels from WebSocket response.

    Args:
        levels: Raw levels from WebSocket

    Returns:
        List of parsed level dictionaries
    """
    parsed = []
    for level in levels:
        try:
            parsed.append(
                {
                    "px": float(level.get("px", 0)),
                    "sz": float(level.get("sz", 0)),
                    "n": int(level.get("n", 0)),
                }
            )
        except (ValueError, TypeError):
            continue
    return parsed


# =============================================================================
# Backward compatibility - Keep REST-based collector as fallback
# =============================================================================


async def collect_orderbook(
    client,
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Collect and store BTC orderbook snapshot (REST fallback).

    This is kept for backward compatibility when WebSocket is unavailable.

    Args:
        client: Hyperliquid API client
        db: MongoDB database

    Returns:
        Dictionary with collection results
    """
    from src.jobs.btc_orderbook import collect_orderbook as rest_collect_orderbook

    # Use REST-based collector as fallback
    return await rest_collect_orderbook(client, db)
