#!/usr/bin/env python3
"""
Optimized Trader Positions WebSocket Collection Job.

This optimized version uses persistent WebSocket connections and batch processing
to reduce execution time and prevent job overlap.
"""

"""
Trader Positions WebSocket Collection Job.

This module collects trader positions in real-time using WebSocket.
Uses webData2 subscription to get positions for tracked traders.
"""

import asyncio
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName


class TraderWebSocketCollector:
    """
    Real-time trader positions collector using WebSocket.

    Connects to Hyperliquid WebSocket and subscribes to webData2
    for tracked traders to get their positions in real-time.
    """

    WS_URL = "wss://api.hyperliquid.xyz/ws"

    def __init__(
        self,
        db: AsyncIOMotorDatabase,
    ):
        """
        Initialize the trader positions WebSocket collector.

        Args:
            db: MongoDB database
        """
        self.db = db
        self._running = False
        self._ws_clients: List[aiohttp.ClientWebSocketConnection] = []
        self._sessions: List[aiohttp.ClientSession] = []

        # Track trader states for change detection
        self._trader_states: Dict[str, Dict] = {}

        # Configuration
        self._num_connections = settings.trader_ws_connections
        self._timeout = settings.trader_ws_timeout
        self._delay_min = settings.trader_ws_delay_min
        self._delay_max = settings.trader_ws_delay_max

    async def start(self) -> None:
        """Start collecting trader positions via WebSocket."""
        if self._running:
            logger.warning("Trader WS collector already running")
            return

        self._running = True
        logger.info(f"Starting Trader WebSocket collector with {self._num_connections} connections")

        # Get tracked trader addresses
        from src.jobs.leaderboard import get_tracked_trader_addresses

        addresses = await get_tracked_trader_addresses(self.db, active_only=True)

        if not addresses:
            logger.warning("No tracked traders found")
            return

        logger.info(f"Fetching positions for {len(addresses)} traders via WebSocket")

        # Process traders in batches using multiple WS connections
        await self._process_traders_parallel(addresses)

        logger.info("Trader WebSocket collector finished")

    async def stop(self) -> None:
        """Stop collecting trader positions."""
        self._running = False

        # Close all WebSocket connections
        for ws in self._ws_clients:
            try:
                await ws.close()
            except:
                pass

        for session in self._sessions:
            try:
                await session.close()
            except:
                pass

        self._ws_clients.clear()
        self._sessions.clear()

        logger.info("Stopped Trader WebSocket collector")

    async def _process_traders_parallel(self, addresses: List[str]) -> None:
        """
        Process traders using multiple WebSocket connections in parallel.

        Args:
            addresses: List of trader addresses
        """
        # Split addresses into batches for each connection
        batch_size = len(addresses) // self._num_connections + 1
        batches = [addresses[i : i + batch_size] for i in range(0, len(addresses), batch_size)]

        logger.info(f"Split {len(addresses)} traders into {len(batches)} batches")

        # Process each batch with a separate WebSocket connection
        tasks = []
        for i, batch in enumerate(batches):
            if batch:
                task = asyncio.create_task(self._process_batch(batch, connection_id=i))
                tasks.append(task)

        # Wait for all batches to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Summarize results
        total_traders = 0
        total_with_positions = 0
        total_errors = 0

        for result in results:
            if isinstance(result, dict):
                total_traders += result.get("processed", 0)
                total_with_positions += result.get("with_positions", 0)
                total_errors += result.get("errors", 0)

        logger.info(
            f"WS Trader collection: {total_traders} processed, "
            f"{total_with_positions} with positions, {total_errors} errors"
        )

    async def _process_batch(self, addresses: List[str], connection_id: int) -> Dict:
        """
        Process a batch of traders using a single WebSocket connection.

        Args:
            addresses: List of trader addresses
            connection_id: Connection identifier for logging

        Returns:
            Dictionary with results
        """
        results = {
            "processed": 0,
            "with_positions": 0,
            "errors": 0,
        }

        session = aiohttp.ClientSession()
        self._sessions.append(session)

        try:
            ws = await session.ws_connect(
                self.WS_URL,
                heartbeat=30,
                timeout=aiohttp.ClientTimeout(total=self._timeout * 2),
            )
            self._ws_clients.append(ws)

            logger.debug(f"WS Connection {connection_id}: Processing {len(addresses)} traders")

            for i, address in enumerate(addresses):
                if not self._running:
                    break

                # Add human-like delay between subscriptions
                if i > 0:
                    delay = random.uniform(self._delay_min, self._delay_max)
                    await asyncio.sleep(delay)

                # Subscribe to this trader's data
                try:
                    await ws.send_json(
                        {
                            "method": "subscribe",
                            "subscription": {"type": "webData2", "user": address},
                        }
                    )

                    # Wait for response
                    has_positions = await self._wait_for_trader_data(ws, address)

                    results["processed"] += 1
                    if has_positions:
                        results["with_positions"] += 1

                except Exception as e:
                    logger.debug(f"WS Connection {connection_id}: Error for {address[:10]}...: {e}")
                    results["errors"] += 1

                    # Small delay on error
                    await asyncio.sleep(random.uniform(0.1, 0.3))

            # Unsubscribe (optional - connection will close anyway)
            # Note: Hyperliquid doesn't support unsubscribe via WS

        except Exception as e:
            logger.error(f"WS Connection {connection_id} error: {e}")
            results["errors"] += len(addresses)

        finally:
            try:
                await ws.close()
            except:
                pass
            try:
                await session.close()
            except:
                pass

        return results

    async def _wait_for_trader_data(
        self,
        ws: aiohttp.ClientWebSocketResponse,
        address: str,
    ) -> bool:
        """
        Wait for trader data response from WebSocket.

        Args:
            ws: WebSocket connection
            address: Trader address

        Returns:
            True if trader has positions, False otherwise
        """
        try:
            # Wait for subscription response and data
            for _ in range(10):  # Max 10 messages
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=self._timeout)

                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = msg.json()
                        channel = data.get("channel")

                        if channel == "error":
                            # Error response - trader likely has no data
                            return False

                        elif channel == "subscriptionResponse":
                            # Subscription confirmed, data should follow
                            continue

                        elif channel == "webData2":
                            # Got trader data!
                            payload = data.get("data", {})
                            return await self._process_trader_data(address, payload)

                except asyncio.TimeoutError:
                    # Timeout - treat as no positions
                    return False

        except Exception as e:
            logger.debug(f"Error waiting for {address[:10]}...: {e}")

        return False

    async def _process_trader_data(
        self,
        address: str,
        data: Dict,
    ) -> bool:
        """
        Process trader data from WebSocket.

        Args:
            address: Trader address
            data: WebData2 payload

        Returns:
            True if trader has positions
        """
        try:
            # Extract positions from clearinghouseState
            clearinghouse = data.get("clearinghouseState", {})
            positions = clearinghouse.get("assetPositions", [])

            if not positions:
                return False

            # Get previous state for change detection
            prev_state = self._trader_states.get(address, {})

            # Process each position
            position_changes = []
            now = datetime.utcnow()

            for pos in positions:
                position_data = pos.get("position", {})

                coin = position_data.get("coin", "")
                szi = float(position_data.get("szi", 0))
                position_value = float(position_data.get("positionValue", 0))

                # Skip zero positions
                if szi == 0:
                    continue

                # Detect change from previous state
                prev_pos = prev_state.get(coin, {})
                prev_szi = prev_pos.get("szi", 0)

                if szi != prev_szi:
                    position_changes.append(
                        {
                            "coin": coin,
                            "szi": szi,
                            "positionValue": position_value,
                            "side": "long" if szi > 0 else "short",
                            "change": szi - prev_szi,
                        }
                    )

                # Update state
                prev_state[coin] = {
                    "szi": szi,
                    "positionValue": position_value,
                }

            # Store current state
            self._trader_states[address] = prev_state

            # Only store if there are BTC positions
            btc_positions = [p for p in position_changes if p["coin"] == "BTC"]

            if not btc_positions:
                # Check if any BTC position exists (not just changes)
                btc_any = any(p.get("coin") == "BTC" for p in positions)
                if not btc_any:
                    return False

            # Store position snapshot
            await self._store_position_snapshot(
                address=address,
                positions=positions,
                clearinghouse=clearinghouse,
                timestamp=now,
            )

            # Generate signals if there were changes
            if btc_positions:
                await self._generate_signals(address, btc_positions)

            return True

        except Exception as e:
            logger.error(f"Error processing trader data for {address[:10]}...: {e}")
            return False

    async def _store_position_snapshot(
        self,
        address: str,
        positions: List[Dict],
        clearinghouse: Dict,
        timestamp: datetime,
    ) -> None:
        """Store position snapshot in MongoDB."""
        try:
            collection = self.db[CollectionName.TRADER_POSITIONS]

            # Calculate total value
            total_value = sum(
                float(p.get("position", {}).get("positionValue", 0)) for p in positions
            )

            # Get margin summary
            margin_summary = clearinghouse.get("marginSummary", {})

            doc = {
                "ethAddress": address,
                "t": timestamp,
                "positions": positions,
                "totalValue": total_value,
                "marginSummary": margin_summary,
                "source": "websocket",
                "createdAt": timestamp,
            }

            await collection.insert_one(doc)

            # Update current state
            state_collection = self.db[CollectionName.TRADER_CURRENT_STATE]
            await state_collection.update_one(
                {"ethAddress": address},
                {"$set": {"positions": positions, "updatedAt": timestamp}},
                upsert=True,
            )

        except Exception as e:
            logger.error(f"Error storing position snapshot: {e}")

    async def _generate_signals(
        self,
        address: str,
        position_changes: List[Dict],
    ) -> None:
        """Generate signals for BTC position changes."""
        try:
            from src.strategies.signal_generation import generate_individual_signal

            signals_collection = self.db[CollectionName.BTC_SIGNALS]

            # Get trader score
            tracked_collection = self.db[CollectionName.TRACKED_TRADERS]
            trader = await tracked_collection.find_one({"ethAddress": address})
            trader_score = trader.get("score", 50) if trader else 50

            # Get current BTC price
            ticker_collection = self.db[CollectionName.BTC_TICKER]
            ticker = await ticker_collection.find_one({"_id": "btc_ticker"})
            current_price = ticker.get("px", 0) if ticker else 0

            for change in position_changes:
                signal = generate_individual_signal(
                    eth_address=address,
                    position_change=change,
                    trader_score=trader_score,
                    current_price=current_price,
                )

                if signal:
                    await signals_collection.insert_one(signal)

        except Exception as e:
            logger.error(f"Error generating signals: {e}")


# =============================================================================
# REST Fallback - Only for failed WebSocket connections
# =============================================================================


async def collect_all_positions(
    client,
    db: AsyncIOMotorDatabase,
) -> Dict:
    """
    Collect trader positions via REST API (fallback).

    This is kept as fallback when WebSocket is unavailable.

    Args:
        client: Hyperliquid API client
        db: MongoDB database

    Returns:
        Dictionary with collection results
    """
    from src.jobs.trader_positions import collect_all_positions as rest_collect

    return await rest_collect(client, db)
