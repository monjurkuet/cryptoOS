"""
Persistent Trader Orders WebSocket Manager.

Manages multiple persistent WebSocket connections for continuous
real-time order monitoring from webData2 data.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
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


class PersistentTraderOrdersWSManager:
    """
    Manages persistent WebSocket connections for trader order monitoring.

    Features:
    - Multiple persistent connections (configurable, default 5)
    - Auto-reconnect with exponential backoff
    - Continuous real-time order updates from webData2
    - Batch DB writes for efficiency
    - Order state tracking to detect changes (new, filled, cancelled)
    - Shares WebSocket connections with position manager via message routing
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
        self._clients: List[TraderOrdersWSClient] = []
        self._num_clients = settings.trader_ws_clients

        # State tracking
        self._running = False
        self._subscribed_traders: Set[str] = set()
        # Track order states per trader: {ethAddress: {oid: OrderState}}
        self._order_states: Dict[str, Dict[int, OrderState]] = {}

        # Message buffer for batch processing
        self._order_buffer: List[Dict] = []
        self._buffer_lock = asyncio.Lock()

        # Statistics
        self._orders_inserted = 0
        self._orders_updated = 0

    async def start(self) -> bool:
        """
        Start the persistent WebSocket order manager.

        Returns:
            True if started successfully
        """
        if self._running:
            logger.warning("Orders manager already running")
            return True

        self._running = True
        logger.info(
            f"Starting Persistent Trader Orders WebSocket Manager with {self._num_clients} clients"
        )

        # Get tracked traders
        traders = await self._get_tracked_traders()
        if not traders:
            logger.warning("No tracked traders found for order monitoring")
            return False

        logger.info(f"Found {len(traders)} tracked traders for order monitoring")

        # Split traders among clients
        batch_size = settings.trader_ws_batch_size
        trader_batches = [traders[i : i + batch_size] for i in range(0, len(traders), batch_size)]

        # Create and start clients
        for i, batch in enumerate(trader_batches[: self._num_clients]):
            client = TraderOrdersWSClient(
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
        logger.info(f"Started {successful}/{len(self._clients)} Orders WebSocket clients")

        # Start background tasks
        asyncio.create_task(self._process_orders_loop())
        asyncio.create_task(self._periodic_health_check())

        return successful > 0

    async def stop(self) -> None:
        """Stop all WebSocket connections gracefully."""
        logger.info("Stopping Persistent Trader Orders WebSocket Manager")
        self._running = False

        # Flush remaining orders
        await self._flush_orders()

        # Stop all clients
        stop_tasks = [client.stop() for client in self._clients]
        await asyncio.gather(*stop_tasks, return_exceptions=True)

        self._clients.clear()
        self._subscribed_traders.clear()
        self._order_states.clear()

        logger.info("Orders manager stopped")

    async def _get_tracked_traders(self) -> List[str]:
        """Get list of tracked trader addresses."""
        collection = self.db[CollectionName.TRACKED_TRADERS]
        cursor = collection.find({"isActive": True}, {"ethAddress": 1}).sort("score", -1)

        docs = await cursor.to_list(length=settings.max_tracked_traders)
        return [doc["ethAddress"] for doc in docs]

    async def _handle_message(self, data: Dict) -> None:
        """Handle incoming WebSocket message."""
        async with self._buffer_lock:
            self._order_buffer.append(data)

            # Flush if buffer is full
            if len(self._order_buffer) >= settings.trader_ws_message_buffer_size:
                await self._flush_orders()

    async def _handle_disconnect(self, client_id: int) -> None:
        """Handle client disconnection by recreating and restarting the client."""
        logger.warning(f"Orders client {client_id} disconnected, recreating...")

        # Find the disconnected client and remove it
        disconnected_client = None
        for i, client in enumerate(self._clients):
            if client.client_id == client_id:
                disconnected_client = client
                # Stop the old client if still running
                try:
                    await client.stop()
                except Exception as e:
                    logger.debug(f"Error stopping old orders client {client_id}: {e}")
                break

        if disconnected_client is None:
            logger.error(f"Orders client {client_id} not found in clients list")
            return

        # Get the traders batch for this client
        batch_size = settings.trader_ws_batch_size
        all_traders = await self._get_tracked_traders()

        if not all_traders:
            logger.warning("No tracked traders found, cannot recreate orders client")
            return

        # Calculate which batch this client was handling
        start_idx = client_id * batch_size
        end_idx = start_idx + batch_size
        trader_batch = all_traders[start_idx:end_idx]

        if not trader_batch:
            logger.warning(f"No traders in batch for orders client {client_id}")
            return

        # Wait a bit before recreating (prevent rapid reconnection loops)
        await asyncio.sleep(5)

        if not self._running:
            logger.info(f"Orders manager stopped, not recreating client {client_id}")
            return

        # Create new client
        logger.info(f"Recreating orders client {client_id} with {len(trader_batch)} traders...")
        new_client = TraderOrdersWSClient(
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
                    logger.info(f"Orders client {client_id} successfully recreated and started")
                    return
                else:
                    logger.warning(
                        f"Orders client {client_id} restart attempt {attempt + 1} failed"
                    )
                    await asyncio.sleep(10 * (attempt + 1))  # Increasing delay
            except Exception as e:
                logger.error(f"Error restarting orders client {client_id}: {e}")
                await asyncio.sleep(10 * (attempt + 1))

        logger.error(
            f"Failed to recreate orders client {client_id} after {max_restart_attempts} attempts"
        )

    async def _process_orders_loop(self) -> None:
        """Periodically process and flush orders."""
        while self._running:
            await asyncio.sleep(settings.trader_orders_ws_flush_interval)
            await self._flush_orders()

    async def _flush_orders(self) -> None:
        """Flush buffered orders to database."""
        async with self._buffer_lock:
            if not self._order_buffer:
                return

            messages = self._order_buffer.copy()
            self._order_buffer.clear()

        if not messages:
            return

        # Process messages and extract order updates
        order_updates: List[Tuple[str, Dict, str]] = []  # (address, order_data, action)

        for msg in messages:
            if msg.get("channel") == "webData2":
                data = msg.get("data", {})
                address = data.get("user", "")
                open_orders = data.get("openOrders", [])

                # Process current open orders
                current_oids = set()
                for order in open_orders:
                    oid = order.get("oid", 0)
                    current_oids.add(oid)

                    action = self._detect_order_change(address, order)
                    if action in ("new", "updated"):
                        order_updates.append((address, order, action))

                # Check for cancelled/filled orders (were open before, not in current list)
                trader_orders = self._order_states.get(address, {})
                for oid, state in list(trader_orders.items()):
                    if oid not in current_oids:
                        # Order was cancelled or filled
                        order_updates.append(
                            (
                                address,
                                {
                                    "oid": oid,
                                    "coin": state.coin,
                                    "side": state.side,
                                    "limitPx": str(state.limit_px),
                                    "sz": "0",  # Zero size indicates closed
                                    "origSz": str(state.sz),
                                    "timestamp": int(datetime.utcnow().timestamp() * 1000),
                                },
                                "closed",
                            )
                        )
                        # Remove from tracking
                        del trader_orders[oid]

        # Batch write to database
        if order_updates:
            await self._write_orders_batch(order_updates)

    def _detect_order_change(self, address: str, order: Dict) -> str:
        """
        Detect if order is new, updated, or unchanged.

        Returns:
            "new", "updated", or "unchanged"
        """
        oid = order.get("oid", 0)
        coin = order.get("coin", "")
        side = order.get("side", "")
        limit_px = float(order.get("limitPx", 0))
        sz = float(order.get("sz", 0))

        # Initialize trader state if needed
        if address not in self._order_states:
            self._order_states[address] = {}

        trader_orders = self._order_states[address]

        if oid not in trader_orders:
            # New order
            trader_orders[oid] = OrderState(
                oid=oid,
                coin=coin,
                side=side,
                limit_px=limit_px,
                sz=sz,
                status="open",
                timestamp=datetime.utcnow(),
            )
            return "new"

        # Check for changes
        existing = trader_orders[oid]
        if (
            existing.coin != coin
            or existing.side != side
            or abs(existing.limit_px - limit_px) > 0.000001
            or abs(existing.sz - sz) > 0.000001
        ):
            # Order updated
            existing.coin = coin
            existing.side = side
            existing.limit_px = limit_px
            existing.sz = sz
            existing.timestamp = datetime.utcnow()
            return "updated"

        return "unchanged"

    async def _write_orders_batch(self, updates: List[Tuple[str, Dict, str]]) -> None:
        """Write order updates to database."""
        collection = self.db[CollectionName.TRADER_ORDERS]

        inserted = 0
        for address, order, action in updates:
            try:
                oid = order.get("oid", 0)
                timestamp_ms = order.get("timestamp", int(datetime.utcnow().timestamp() * 1000))
                timestamp = datetime.utcfromtimestamp(timestamp_ms / 1000)

                doc = {
                    "ethAddress": address,
                    "oid": oid,
                    "coin": order.get("coin"),
                    "side": order.get("side"),
                    "limitPx": float(order.get("limitPx", 0)),
                    "sz": float(order.get("sz", 0)),
                    "origSz": float(order.get("origSz", order.get("sz", 0))),
                    "orderType": "limit",  # webData2 openOrders are typically limit orders
                    "tif": "Gtc",  # Default to Good-till-Cancelled
                    "status": "open" if action != "closed" else "closed",
                    "action": action,  # new, updated, or closed
                    "timestamp": timestamp,
                    "createdAt": datetime.utcnow(),
                }

                # Insert order event
                await collection.insert_one(doc)
                inserted += 1

                # Also update current order state
                state_collection = self.db[CollectionName.TRADER_CURRENT_STATE]
                await state_collection.update_one(
                    {"ethAddress": address},
                    {
                        "$set": {
                            f"orders.{oid}": {
                                "coin": doc["coin"],
                                "side": doc["side"],
                                "limitPx": doc["limitPx"],
                                "sz": doc["sz"],
                                "status": doc["status"],
                                "timestamp": timestamp,
                            }
                        }
                    },
                    upsert=True,
                )

            except Exception as e:
                logger.error(f"Error writing order for {address[:20]}: {e}")

        self._orders_inserted += inserted
        logger.info(
            f"Flushed {inserted} order updates to database (total: {self._orders_inserted})"
        )

    async def _periodic_health_check(self) -> None:
        """Periodically check health of connections."""
        while self._running:
            await asyncio.sleep(60)  # Check every minute

            alive_count = sum(1 for c in self._clients if c.is_connected())
            total_orders = sum(len(orders) for orders in self._order_states.values())
            logger.info(
                f"Orders health check: {alive_count}/{len(self._clients)} clients connected, "
                f"tracking {total_orders} open orders"
            )

    def get_stats(self) -> Dict:
        """Get manager statistics."""
        total_tracked = sum(len(orders) for orders in self._order_states.values())
        return {
            "running": self._running,
            "total_clients": len(self._clients),
            "connected_clients": sum(1 for c in self._clients if c.is_connected()),
            "subscribed_traders": len(self._subscribed_traders),
            "tracked_orders": total_tracked,
            "buffer_size": len(self._order_buffer),
            "orders_inserted": self._orders_inserted,
        }


class TraderOrdersWSClient:
    """Single WebSocket client managing a batch of traders for order monitoring."""

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
                PersistentTraderOrdersWSManager.WS_URL,
                heartbeat=settings.trader_ws_heartbeat,
            )

            self._reconnect_attempts = 0
            logger.info(f"Orders Client {self.client_id}: Connected to WebSocket")

            # Subscribe to all traders
            for address in self.traders:
                await self._ws.send_json(
                    {"method": "subscribe", "subscription": {"type": "webData2", "user": address}}
                )
                await asyncio.sleep(0.01)  # Small delay between subscriptions

            logger.info(
                f"Orders Client {self.client_id}: Subscribed to {len(self.traders)} traders"
            )

            # Start listening
            asyncio.create_task(self._listen())

            return True

        except Exception as e:
            logger.error(f"Orders Client {self.client_id}: Failed to start: {e}")
            await self._handle_error()
            return False

    async def stop(self) -> None:
        """Stop the WebSocket client."""
        self._running = False

        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()

        logger.info(f"Orders Client {self.client_id}: Stopped")

    async def _listen(self) -> None:
        """Listen for WebSocket messages."""
        while self._running and self._ws:
            try:
                msg = await self._ws.receive()

                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    await self.on_message(data)

                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    logger.warning(f"Orders Client {self.client_id}: Connection lost")
                    await self._handle_error()
                    break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Orders Client {self.client_id}: Listen error: {e}")
                await self._handle_error()
                break

    async def _handle_error(self) -> None:
        """Handle connection errors with reconnection."""
        if not self._running:
            return

        self._reconnect_attempts += 1

        if self._reconnect_attempts > settings.trader_ws_reconnect_attempts:
            logger.error(f"Orders Client {self.client_id}: Max reconnection attempts reached")
            await self.on_disconnect(self.client_id)
            return

        # Exponential backoff
        delay = min(
            settings.trader_ws_reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
            settings.trader_ws_reconnect_max_delay,
        )

        logger.info(
            f"Orders Client {self.client_id}: Reconnecting in {delay:.1f}s "
            f"(attempt {self._reconnect_attempts})"
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
