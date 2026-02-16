"""
Persistent Trader WebSocket Manager.

Manages multiple persistent WebSocket connections for continuous
real-time position and order monitoring.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
import aiohttp
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName


@dataclass
class OrderState:
    """Track order state for change detection."""

    oid: int
    coin: str
    side: str
    limit_px: float
    sz: float
    status: str = "open"
    timestamp: datetime = field(default_factory=datetime.utcnow)


class PersistentTraderWebSocketManager:
    """
    Manages persistent WebSocket connections for trader position monitoring.

    Optimized features:
    - Event-driven: Only save when positions actually change
    - BTC-only: Filter for BTC positions only
    - Safety interval: Max 600 seconds between saves
    - Multiple persistent connections (configurable, default 5)
    - Auto-reconnect with exponential backoff
    """

    WS_URL = "wss://api.hyperliquid.xyz/ws"

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize the manager.

        Args:
            db: MongoDB database instance
        """
        self.db = db

        # Connection pool
        self._clients: List[TraderWSClient] = []
        self._num_clients = settings.trader_ws_clients

        # State tracking
        self._running = False
        self._subscribed_traders: Set[str] = set()

        # Event-driven optimization: Track last saved state per trader
        self._last_positions: Dict[str, Dict] = {}
        self._position_change_threshold = settings.position_change_threshold_pct
        self._position_max_interval = settings.position_max_save_interval
        self._position_only_btc = settings.position_only_btc

        # Message buffer for batch processing
        self._message_buffer: List[Dict] = []
        self._buffer_lock = asyncio.Lock()

    async def start(self) -> bool:
        """
        Start the persistent WebSocket manager.

        Returns:
            True if started successfully
        """
        if self._running:
            logger.warning("Manager already running")
            return True

        self._running = True
        logger.info(
            f"Starting Optimized Persistent Trader WebSocket Manager with {self._num_clients} clients"
        )
        logger.info(
            f"Optimization: BTC-only={self._position_only_btc}, "
            f"change_threshold={self._position_change_threshold * 100}%, "
            f"max_interval={self._position_max_interval}s"
        )

        # Get tracked traders
        traders = await self._get_tracked_traders()
        if not traders:
            logger.warning("No tracked traders found")
            return False

        logger.info(f"Found {len(traders)} tracked traders to monitor")

        # Split traders among clients
        batch_size = settings.trader_ws_batch_size
        trader_batches = [traders[i : i + batch_size] for i in range(0, len(traders), batch_size)]

        # Create and start clients
        for i, batch in enumerate(trader_batches[: self._num_clients]):
            client = TraderWSClient(
                client_id=i,
                db=self.db,
                traders=batch,
                on_message=self._handle_message,
                on_disconnect=self._handle_disconnect,
            )
            self._clients.append(client)

        # Start all clients
        start_tasks = [client.start() for client in self._clients]
        results = await asyncio.gather(*start_tasks, return_exceptions=True)

        successful = sum(1 for r in results if r is True)
        logger.info(f"Started {successful}/{len(self._clients)} WebSocket clients")

        # Start background tasks
        asyncio.create_task(self._process_messages_loop())
        asyncio.create_task(self._periodic_health_check())

        return successful > 0

    async def stop(self) -> None:
        """Stop all WebSocket connections gracefully."""
        logger.info("Stopping Persistent Trader WebSocket Manager")
        self._running = False

        # Flush remaining messages
        await self._flush_messages()

        # Stop all clients
        stop_tasks = [client.stop() for client in self._clients]
        await asyncio.gather(*stop_tasks, return_exceptions=True)

        self._clients.clear()
        self._subscribed_traders.clear()

        logger.info("Manager stopped")

    async def _get_tracked_traders(self) -> List[str]:
        """Get list of tracked trader addresses."""
        collection = self.db[CollectionName.TRACKED_TRADERS]
        cursor = collection.find({"isActive": True}, {"ethAddress": 1}).sort("score", -1)

        docs = await cursor.to_list(length=settings.max_tracked_traders)
        return [doc["ethAddress"] for doc in docs]

    async def _handle_message(self, data: Dict) -> None:
        """Handle incoming WebSocket message."""
        async with self._buffer_lock:
            self._message_buffer.append(data)

            # Flush if buffer is full
            if len(self._message_buffer) >= settings.trader_ws_message_buffer_size:
                await self._flush_messages()

    async def _handle_disconnect(self, client_id: int) -> None:
        """Handle client disconnection by recreating and restarting the client."""
        logger.warning(f"Client {client_id} disconnected, recreating...")

        # Find the disconnected client and remove it
        disconnected_client = None
        for i, client in enumerate(self._clients):
            if client.client_id == client_id:
                disconnected_client = client
                # Stop the old client if still running
                try:
                    await client.stop()
                except Exception as e:
                    logger.debug(f"Error stopping old client {client_id}: {e}")
                break

        if disconnected_client is None:
            logger.error(f"Client {client_id} not found in clients list")
            return

        # Get the traders batch for this client
        batch_size = settings.trader_ws_batch_size
        all_traders = await self._get_tracked_traders()

        if not all_traders:
            logger.warning("No tracked traders found, cannot recreate client")
            return

        # Calculate which batch this client was handling
        start_idx = client_id * batch_size
        end_idx = start_idx + batch_size
        trader_batch = all_traders[start_idx:end_idx]

        if not trader_batch:
            logger.warning(f"No traders in batch for client {client_id}")
            return

        # Wait a bit before recreating (prevent rapid reconnection loops)
        await asyncio.sleep(5)

        if not self._running:
            logger.info(f"Manager stopped, not recreating client {client_id}")
            return

        # Create new client
        logger.info(f"Recreating client {client_id} with {len(trader_batch)} traders...")
        new_client = TraderWSClient(
            client_id=client_id,
            db=self.db,
            traders=trader_batch,
            on_message=self._handle_message,
            on_disconnect=self._handle_disconnect,
        )

        # Replace old client in list
        for i, client in enumerate(self._clients):
            if client.client_id == client_id:
                self._clients[i] = new_client
                break
        else:
            self._clients.append(new_client)

        # Start the new client
        max_restart_attempts = 5
        for attempt in range(max_restart_attempts):
            try:
                success = await new_client.start()
                if success:
                    logger.info(f"Client {client_id} successfully recreated and started")
                    return
                else:
                    logger.warning(f"Client {client_id} restart attempt {attempt + 1} failed")
                    await asyncio.sleep(10 * (attempt + 1))  # Increasing delay
            except Exception as e:
                logger.error(f"Error restarting client {client_id}: {e}")
                await asyncio.sleep(10 * (attempt + 1))

        logger.error(f"Failed to recreate client {client_id} after {max_restart_attempts} attempts")

    async def _process_messages_loop(self) -> None:
        """Periodically process and flush messages."""
        while self._running:
            await asyncio.sleep(settings.trader_ws_flush_interval)
            await self._flush_messages()

    def _normalize_positions(self, positions: List[Dict]) -> str:
        """Normalize positions for comparison (event-driven detection)."""
        if not positions:
            return ""

        # Sort by coin for consistent comparison
        sorted_positions = sorted(positions, key=lambda x: x.get("position", {}).get("coin", ""))

        # Create comparable string
        parts = []
        for pos in sorted_positions:
            coin = pos.get("position", {}).get("coin", "")
            szi = float(pos.get("position", {}).get("szi", 0))
            leverage = pos.get("position", {}).get("leverage", {}).get("value", 0)
            parts.append(f"{coin}:{szi:.8f}:{leverage}")

        return "|".join(parts)

    def _has_significant_change(self, address: str, new_positions: List[Dict]) -> bool:
        """Check if positions have changed significantly from last saved."""
        last_saved = self._last_positions.get(address, {})

        # Check time since last save (safety interval)
        last_time = last_saved.get("timestamp", datetime.min)
        time_since_save = (datetime.utcnow() - last_time).total_seconds()

        if time_since_save >= self._position_max_interval:
            logger.debug(f"Force save for {address[:20]}... (interval: {time_since_save:.0f}s)")
            return True

        # Compare normalized positions
        last_normalized = last_saved.get("normalized", "")
        current_normalized = self._normalize_positions(new_positions)

        if last_normalized != current_normalized:
            logger.debug(f"Position change detected for {address[:20]}...")
            return True

        return False

    async def _flush_messages(self) -> None:
        """Flush buffered messages to database (event-driven)."""
        async with self._buffer_lock:
            if not self._message_buffer:
                return

            messages = self._message_buffer.copy()
            self._message_buffer.clear()

        if not messages:
            return

        # Process messages
        position_updates = []
        skipped_count = 0
        btc_only_count = 0

        for msg in messages:
            if msg.get("channel") == "webData2":
                data = msg.get("data", {})
                address = data.get("user", "")
                clearinghouse = data.get("clearinghouseState", {})
                positions = clearinghouse.get("assetPositions", [])

                # Filter for non-zero positions
                active_positions = [
                    p for p in positions if float(p.get("position", {}).get("szi", 0)) != 0
                ]

                if not active_positions:
                    skipped_count += 1
                    continue

                # BTC-ONLY FILTER
                if self._position_only_btc:
                    btc_positions = [
                        p for p in active_positions if p.get("position", {}).get("coin") == "BTC"
                    ]
                    if not btc_positions:
                        btc_only_count += 1
                        continue
                    active_positions = btc_positions

                # EVENT-DRIVEN: Check if position actually changed
                if not self._has_significant_change(address, active_positions):
                    skipped_count += 1
                    continue

                position_updates.append(
                    {
                        "ethAddress": address,
                        "positions": active_positions,
                        "marginSummary": clearinghouse.get("marginSummary", {}),
                        "timestamp": datetime.utcnow(),
                        "source": "websocket",
                    }
                )

        # Batch write to database
        if position_updates:
            await self._write_positions_batch(position_updates)

        if skipped_count > 0 or btc_only_count > 0:
            logger.debug(
                f"Position filtering: {len(position_updates)} saved, "
                f"{skipped_count} skipped (no change), "
                f"{btc_only_count} skipped (non-BTC)"
            )

    async def _write_positions_batch(self, updates: List[Dict]) -> None:
        """Write position updates to database."""
        collection = self.db[CollectionName.TRADER_POSITIONS]

        for update in updates:
            try:
                # Insert position snapshot
                doc = {
                    "ethAddress": update["ethAddress"],
                    "t": update["timestamp"],
                    "positions": update["positions"],
                    "marginSummary": update["marginSummary"],
                    "source": "websocket",
                    "createdAt": update["timestamp"],
                }
                await collection.insert_one(doc)

                # Update current state
                state_collection = self.db[CollectionName.TRADER_CURRENT_STATE]
                await state_collection.update_one(
                    {"ethAddress": update["ethAddress"]},
                    {
                        "$set": {
                            "positions": update["positions"],
                            "marginSummary": update["marginSummary"],
                            "updatedAt": update["timestamp"],
                        }
                    },
                    upsert=True,
                )

                # Update last saved state (event-driven tracking)
                self._last_positions[update["ethAddress"]] = {
                    "positions": update["positions"],
                    "normalized": self._normalize_positions(update["positions"]),
                    "timestamp": update["timestamp"],
                }

            except Exception as e:
                logger.error(f"Error writing position for {update['ethAddress'][:20]}: {e}")

        logger.info(f"Flushed {len(updates)} position updates to database (event-driven)")

    async def _periodic_health_check(self) -> None:
        """Periodically check health of connections."""
        while self._running:
            await asyncio.sleep(60)  # Check every minute

            alive_count = sum(1 for c in self._clients if c.is_connected())
            logger.info(f"Health check: {alive_count}/{len(self._clients)} clients connected")

    def get_stats(self) -> Dict:
        """Get manager statistics."""
        return {
            "running": self._running,
            "total_clients": len(self._clients),
            "connected_clients": sum(1 for c in self._clients if c.is_connected()),
            "subscribed_traders": len(self._subscribed_traders),
            "buffer_size": len(self._message_buffer),
            "tracked_last_positions": len(self._last_positions),
        }


class TraderWSClient:
    """Single WebSocket client managing a batch of traders."""

    def __init__(
        self,
        client_id: int,
        db: AsyncIOMotorDatabase,
        traders: List[str],
        on_message,
        on_disconnect,
    ):
        self.client_id = client_id
        self.db = db
        self.traders = traders
        self.on_message = on_message
        self.on_disconnect = on_disconnect

        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._running = False
        self._reconnect_attempts = 0

    async def start(self) -> bool:
        """Start the WebSocket client."""
        try:
            self._running = True
            self._session = aiohttp.ClientSession()

            self._ws = await self._session.ws_connect(
                PersistentTraderWebSocketManager.WS_URL,
                heartbeat=settings.trader_ws_heartbeat,
            )

            self._reconnect_attempts = 0
            logger.info(f"Client {self.client_id}: Connected to WebSocket")

            # Subscribe to all traders
            for address in self.traders:
                await self._ws.send_json(
                    {"method": "subscribe", "subscription": {"type": "webData2", "user": address}}
                )
                await asyncio.sleep(0.01)  # Small delay between subscriptions

            logger.info(f"Client {self.client_id}: Subscribed to {len(self.traders)} traders")

            # Start listening
            asyncio.create_task(self._listen())

            return True

        except Exception as e:
            logger.error(f"Client {self.client_id}: Failed to start: {e}")
            await self._handle_error()
            return False

    async def stop(self) -> None:
        """Stop the WebSocket client."""
        self._running = False

        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()

        logger.info(f"Client {self.client_id}: Stopped")

    async def _listen(self) -> None:
        """Listen for WebSocket messages."""
        while self._running and self._ws:
            try:
                msg = await self._ws.receive()

                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    await self.on_message(data)

                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    logger.warning(f"Client {self.client_id}: Connection lost")
                    await self._handle_error()
                    break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Client {self.client_id}: Listen error: {e}")
                await self._handle_error()
                break

    async def _handle_error(self) -> None:
        """Handle connection errors with reconnection."""
        if not self._running:
            return

        self._reconnect_attempts += 1

        if self._reconnect_attempts > settings.trader_ws_reconnect_attempts:
            logger.error(f"Client {self.client_id}: Max reconnection attempts reached")
            await self.on_disconnect(self.client_id)
            return

        # Exponential backoff
        delay = min(
            settings.trader_ws_reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
            settings.trader_ws_reconnect_max_delay,
        )

        logger.info(
            f"Client {self.client_id}: Reconnecting in {delay:.1f}s (attempt {self._reconnect_attempts})"
        )
        await asyncio.sleep(delay)

        # Cleanup and restart
        if self._ws:
            try:
                await self._ws.close()
            except:
                pass

        await self.start()

    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._ws is not None and not self._ws.closed
