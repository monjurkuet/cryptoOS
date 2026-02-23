"""
Persistent Trader Orders WebSocket Manager.

Manages multiple persistent WebSocket connections for continuous
real-time order monitoring from webData2 data.

Refactored: Fixed zombie client accumulation, added proper connection verification,
and implemented indefinite retry with smart backoff.
"""

import asyncio
import random
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
import aiohttp
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.config import settings
from src.models.base import CollectionName


class ConnectionState(Enum):
    """Connection lifecycle states."""

    INIT = "init"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SUBSCRIBING = "subscribing"
    SUBSCRIBED = "subscribed"
    RUNNING = "running"
    ERROR = "error"
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"


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


@dataclass
class ConnectionMetrics:
    """Track connection metrics per client."""

    connection_attempts_total: int = 0
    connection_failures_total: int = 0
    connection_success_total: int = 0
    reconnections_total: int = 0
    messages_received_total: int = 0
    orders_detected_total: int = 0
    last_error: Optional[str] = None
    last_error_type: Optional[str] = None
    last_successful_connection: Optional[datetime] = None


class TraderOrdersWSClient:
    """
    Single WebSocket client managing a batch of traders for order monitoring.

    Features:
    - Proper connection state machine
    - Connection verification with subscription acknowledgment
    - Indefinite retry with exponential backoff and jitter
    - Comprehensive error logging
    - Metrics tracking
    """

    def __init__(
        self,
        client_id: int,
        db: AsyncIOMotorDatabase,
        traders: List[str],
        on_message,
        on_disconnect,
        ws_url: str = "wss://api.hyperliquid.xyz/ws",
    ):
        self.client_id = client_id
        self.db = db
        self.traders = traders
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        self.ws_url = ws_url

        # Connection objects
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None

        # State management
        self._state = ConnectionState.INIT
        self._state_lock = asyncio.Lock()
        self._connected_event = asyncio.Event()
        self._subscribed_event = asyncio.Event()
        self._shutdown_event = asyncio.Event()

        # Retry state
        self._reconnect_attempts = 0
        self._reconnect_task: Optional[asyncio.Task] = None
        self._listen_task: Optional[asyncio.Task] = None

        # Metrics
        self._metrics = ConnectionMetrics()

        # Subscription tracking
        self._subscription_confirmed = set()
        self._subscription_timeout = 10.0  # seconds to wait for subscription ack

        logger.debug(f"Orders Client {self.client_id}: Initialized with {len(traders)} traders")

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    def _set_state(self, new_state: ConnectionState) -> None:
        """Update connection state with logging."""
        old_state = self._state
        self._state = new_state
        if old_state != new_state:
            logger.debug(
                f"Orders Client {self.client_id}: State change {old_state.value} -> {new_state.value}"
            )

    async def start(self) -> bool:
        """
        Start the WebSocket client with full connection verification.

        Returns:
            True if connection established and subscriptions acknowledged
        """
        async with self._state_lock:
            if self._state in (ConnectionState.RUNNING, ConnectionState.SUBSCRIBED):
                logger.warning(f"Orders Client {self.client_id}: Already running")
                return True

            if self._state == ConnectionState.CONNECTING:
                logger.warning(f"Orders Client {self.client_id}: Connection in progress")
                # Wait for existing connection attempt
                try:
                    await asyncio.wait_for(self._connected_event.wait(), timeout=30.0)
                    return await self._verify_connection()
                except asyncio.TimeoutError:
                    logger.error(
                        f"Orders Client {self.client_id}: Timeout waiting for existing connection"
                    )
                    return False

            self._set_state(ConnectionState.CONNECTING)
            self._connected_event.clear()
            self._subscribed_event.clear()

        self._metrics.connection_attempts_total += 1

        try:
            # Create session
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60.0))

            # Connect to WebSocket
            logger.info(f"Orders Client {self.client_id}: Connecting to {self.ws_url}")
            self._ws = await self._session.ws_connect(
                self.ws_url,
                heartbeat=settings.trader_ws_heartbeat,
                autoclose=False,
                autoping=True,
            )

            async with self._state_lock:
                self._set_state(ConnectionState.CONNECTED)
                self._connected_event.set()

            logger.info(f"Orders Client {self.client_id}: WebSocket connected")

            # Subscribe to all traders
            await self._subscribe_all()

            # Verify subscriptions
            if not await self._verify_connection():
                logger.error(f"Orders Client {self.client_id}: Subscription verification failed")
                self._metrics.last_error = "Subscription verification failed"
                self._metrics.last_error_type = "subscription"
                self._metrics.connection_failures_total += 1
                await self._cleanup_connection()
                self._schedule_reconnect()
                return False

            # Start listening
            async with self._state_lock:
                self._set_state(ConnectionState.RUNNING)

            self._listen_task = asyncio.create_task(
                self._listen(), name=f"orders_client_{self.client_id}_listen"
            )

            # Reset retry counter on success
            self._reconnect_attempts = 0
            self._metrics.connection_success_total += 1
            self._metrics.last_successful_connection = datetime.utcnow()

            logger.info(
                f"Orders Client {self.client_id}: Fully operational - "
                f"{len(self.traders)} traders subscribed"
            )

            return True

        except aiohttp.ClientConnectorError as e:
            self._log_connection_error("network", f"Cannot connect to server: {e}")
            await self._cleanup_connection()
            self._schedule_reconnect()
            return False

        except aiohttp.WSServerHandshakeError as e:
            self._log_connection_error("handshake", f"WebSocket handshake failed: {e}")
            await self._cleanup_connection()
            self._schedule_reconnect()
            return False

        except asyncio.TimeoutError:
            self._log_connection_error("timeout", "Connection timed out")
            await self._cleanup_connection()
            self._schedule_reconnect()
            return False

        except Exception as e:
            error_type = type(e).__name__
            self._log_connection_error("unknown", f"Unexpected error: {e}")
            await self._cleanup_connection()
            self._schedule_reconnect()
            return False

    async def _subscribe_all(self) -> None:
        """Subscribe to all traders in the batch."""
        async with self._state_lock:
            self._set_state(ConnectionState.SUBSCRIBING)

        self._subscription_confirmed.clear()

        for address in self.traders:
            try:
                await self._ws.send_json(
                    {"method": "subscribe", "subscription": {"type": "webData2", "user": address}}
                )
                # Small delay between subscriptions to avoid rate limiting
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.warning(
                    f"Orders Client {self.client_id}: Failed to subscribe to {address}: {e}"
                )

        logger.info(
            f"Orders Client {self.client_id}: Sent {len(self.traders)} subscription requests"
        )

    async def _verify_connection(self) -> bool:
        """
        Verify that subscriptions were acknowledged.

        Returns:
            True if at least one subscription was acknowledged
        """
        async with self._state_lock:
            if self._state not in (ConnectionState.CONNECTED, ConnectionState.SUBSCRIBING):
                return False

        # Wait for subscription acknowledgment
        # We'll wait for a short period to receive subscription confirmations
        try:
            # Wait for any subscription confirmation or timeout
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < self._subscription_timeout:
                if self._ws and self._ws.closed:
                    return False

                # Check if we received any messages (indicates subscription success)
                if self._metrics.messages_received_total > 0:
                    async with self._state_lock:
                        self._set_state(ConnectionState.SUBSCRIBED)
                    self._subscribed_event.set()
                    return True

                # Check for immediate errors
                if self._state == ConnectionState.ERROR:
                    return False

                await asyncio.sleep(0.1)

            # If no messages received but connection is open, consider it OK
            # The server may not send immediate data for all traders
            if self._ws and not self._ws.closed:
                async with self._state_lock:
                    self._set_state(ConnectionState.SUBSCRIBED)
                self._subscribed_event.set()
                logger.info(
                    f"Orders Client {self.client_id}: No immediate data, but connection verified"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Orders Client {self.client_id}: Error verifying connection: {e}")
            return False

    def _log_connection_error(self, error_type: str, message: str) -> None:
        """Log connection error with context."""
        self._metrics.last_error = message
        self._metrics.last_error_type = error_type
        self._metrics.connection_failures_total += 1

        logger.error(
            f"Orders Client {self.client_id}: Connection failed [{error_type}]: {message} "
            f"(attempt {self._metrics.connection_attempts_total}, "
            f"failures: {self._metrics.connection_failures_total})"
        )

    async def stop(self) -> None:
        """Stop the WebSocket client gracefully."""
        logger.info(f"Orders Client {self.client_id}: Stopping...")

        async with self._state_lock:
            self._set_state(ConnectionState.STOPPED)
            self._shutdown_event.set()

        # Cancel any pending reconnect
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        # Cancel listen task
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        await self._cleanup_connection()

        logger.info(f"Orders Client {self.client_id}: Stopped")

    async def _cleanup_connection(self) -> None:
        """Clean up connection resources."""
        if self._ws:
            try:
                if not self._ws.closed:
                    await self._ws.close()
            except Exception as e:
                logger.debug(f"Orders Client {self.client_id}: Error closing WebSocket: {e}")
            finally:
                self._ws = None

        if self._session:
            try:
                await self._session.close()
            except Exception as e:
                logger.debug(f"Orders Client {self.client_id}: Error closing session: {e}")
            finally:
                self._session = None

    async def _listen(self) -> None:
        """Listen for WebSocket messages."""
        logger.debug(f"Orders Client {self.client_id}: Listen loop started")

        while True:
            try:
                if not self._ws or self._ws.closed:
                    logger.warning(f"Orders Client {self.client_id}: WebSocket closed unexpectedly")
                    await self._handle_disconnect("websocket_closed")
                    break

                msg = await self._ws.receive()

                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = msg.json()
                        self._metrics.messages_received_total += 1
                        await self.on_message(data)

                        # Check for order data
                        if data.get("channel") == "webData2":
                            self._metrics.orders_detected_total += 1

                    except Exception as e:
                        logger.error(
                            f"Orders Client {self.client_id}: Error processing message: {e}"
                        )

                elif msg.type == aiohttp.WSMsgType.BINARY:
                    # Handle binary messages if any
                    logger.debug(f"Orders Client {self.client_id}: Received binary message")

                elif msg.type == aiohttp.WSMsgType.PING:
                    # Auto-pong is handled by aiohttp
                    logger.debug(f"Orders Client {self.client_id}: Received ping")

                elif msg.type == aiohttp.WSMsgType.PONG:
                    logger.debug(f"Orders Client {self.client_id}: Received pong")

                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    close_code = msg.data if hasattr(msg, "data") else "unknown"
                    logger.warning(
                        f"Orders Client {self.client_id}: Connection closed by server "
                        f"(code: {close_code})"
                    )
                    await self._handle_disconnect(f"server_close_{close_code}")
                    break

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    error_msg = str(msg.data) if msg.data else "Unknown error"
                    logger.error(f"Orders Client {self.client_id}: WebSocket error: {error_msg}")
                    await self._handle_disconnect(f"ws_error_{error_msg}")
                    break

            except asyncio.CancelledError:
                logger.debug(f"Orders Client {self.client_id}: Listen loop cancelled")
                break

            except Exception as e:
                error_type = type(e).__name__
                logger.error(
                    f"Orders Client {self.client_id}: Unexpected error in listen loop: {e} "
                    f"(type: {error_type})"
                )
                await self._handle_disconnect(f"exception_{error_type}")
                break

        logger.debug(f"Orders Client {self.client_id}: Listen loop ended")

    async def _handle_disconnect(self, reason: str) -> None:
        """Handle connection loss with indefinite retry."""
        async with self._state_lock:
            if self._state == ConnectionState.STOPPED:
                return
            self._set_state(ConnectionState.ERROR)

        logger.warning(
            f"Orders Client {self.client_id}: Disconnected (reason: {reason}), "
            f"scheduling reconnection..."
        )

        # Cleanup current connection
        await self._cleanup_connection()

        # Notify manager for client replacement
        # We do this BEFORE scheduling reconnect to ensure proper cleanup
        asyncio.create_task(
            self._notify_disconnect(), name=f"orders_client_{self.client_id}_disconnect_notify"
        )

    async def _notify_disconnect(self) -> None:
        """Notify parent manager of disconnection."""
        try:
            await self.on_disconnect(self.client_id)
        except Exception as e:
            logger.error(f"Orders Client {self.client_id}: Error notifying disconnect: {e}")

    def _schedule_reconnect(self) -> None:
        """Schedule reconnection with smart backoff (indefinite retry)."""
        if self._shutdown_event.is_set():
            return

        self._reconnect_attempts += 1
        self._metrics.reconnections_total += 1

        # Exponential backoff with jitter: min(5 * 2^attempts, 300) + random jitter
        base_delay = min(5 * (2 ** (self._reconnect_attempts - 1)), 300)
        jitter = random.uniform(0, 2)  # 0-2 seconds jitter
        delay = base_delay + jitter

        logger.info(
            f"Orders Client {self.client_id}: Scheduling reconnection in {delay:.1f}s "
            f"(attempt #{self._reconnect_attempts}, backoff: {base_delay:.1f}s + {jitter:.2f}s jitter)"
        )

        self._reconnect_task = asyncio.create_task(
            self._reconnect_after_delay(delay), name=f"orders_client_{self.client_id}_reconnect"
        )

    async def _reconnect_after_delay(self, delay: float) -> None:
        """Reconnect after specified delay."""
        try:
            await asyncio.sleep(delay)

            if self._shutdown_event.is_set():
                logger.debug(
                    f"Orders Client {self.client_id}: Shutdown detected, aborting reconnect"
                )
                return

            async with self._state_lock:
                if self._state == ConnectionState.RUNNING:
                    logger.debug(f"Orders Client {self.client_id}: Already running, skip reconnect")
                    return
                self._set_state(ConnectionState.RECONNECTING)

            logger.info(f"Orders Client {self.client_id}: Attempting reconnection...")
            success = await self.start()

            if success:
                logger.info(
                    f"Orders Client {self.client_id}: Successfully reconnected after "
                    f"{self._reconnect_attempts} attempts"
                )
                # Reset attempt counter on success
                self._reconnect_attempts = 0
            else:
                # Reconnection failed, _schedule_reconnect will be called again by start()
                pass

        except asyncio.CancelledError:
            logger.debug(f"Orders Client {self.client_id}: Reconnect task cancelled")
        except Exception as e:
            logger.error(f"Orders Client {self.client_id}: Error during reconnect: {e}")
            self._schedule_reconnect()

    def is_connected(self) -> bool:
        """
        Check if client is fully connected and subscribed.

        Returns:
            True only if in RUNNING state with active WebSocket
        """
        return (
            self._state == ConnectionState.RUNNING and self._ws is not None and not self._ws.closed
        )

    def is_verified(self) -> bool:
        """Check if connection is verified (subscribed)."""
        return self._state in (ConnectionState.SUBSCRIBED, ConnectionState.RUNNING)

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            "client_id": self.client_id,
            "state": self._state.value,
            "is_connected": self.is_connected(),
            "is_verified": self.is_verified(),
            "trader_count": len(self.traders),
            "reconnect_attempts": self._reconnect_attempts,
            "metrics": {
                "connection_attempts_total": self._metrics.connection_attempts_total,
                "connection_failures_total": self._metrics.connection_failures_total,
                "connection_success_total": self._metrics.connection_success_total,
                "reconnections_total": self._metrics.reconnections_total,
                "messages_received_total": self._metrics.messages_received_total,
                "orders_detected_total": self._metrics.orders_detected_total,
                "last_error": self._metrics.last_error,
                "last_error_type": self._metrics.last_error_type,
                "last_successful_connection": self._metrics.last_successful_connection.isoformat()
                if self._metrics.last_successful_connection
                else None,
            },
        }


class PersistentTraderOrdersWSManager:
    """
    Manages persistent WebSocket connections for trader order monitoring.

    Features:
    - Multiple persistent connections (configurable, default 5)
    - Auto-reconnect with exponential backoff (indefinite retry)
    - Continuous real-time order updates from webData2
    - Batch DB writes for efficiency
    - Order state tracking to detect changes (new, filled, cancelled)
    - Proper client lifecycle management (no zombie clients)
    """

    WS_URL = "wss://api.hyperliquid.xyz/ws"

    def __init__(self, db: AsyncIOMotorDatabase):
        """
        Initialize the manager.

        Args:
            db: MongoDB database instance
        """
        self.db = db

        # Connection pool - use dict for O(1) lookup by client_id
        self._clients: Dict[int, TraderOrdersWSClient] = {}
        self._clients_lock = asyncio.Lock()
        self._num_clients = settings.trader_ws_clients

        # State tracking
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._subscribed_traders: Set[str] = set()
        # Track order states per trader: {ethAddress: {oid: OrderState}}
        self._order_states: Dict[str, Dict[int, OrderState]] = {}

        # Message buffer for batch processing
        self._order_buffer: List[Dict] = []
        self._buffer_lock = asyncio.Lock()

        # Background tasks
        self._process_task: Optional[asyncio.Task] = None
        self._health_check_task: Optional[asyncio.Task] = None

        # Statistics
        self._orders_inserted = 0
        self._orders_updated = 0
        self._start_time: Optional[datetime] = None

    async def start(self) -> bool:
        """
        Start the persistent WebSocket order manager.

        Returns:
            True if at least one client started successfully
        """
        if self._running:
            logger.warning("Orders manager already running")
            return True

        self._running = True
        self._start_time = datetime.utcnow()
        self._shutdown_event.clear()

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

        # Create and start clients (up to _num_clients)
        start_tasks = []
        for i, batch in enumerate(trader_batches[: self._num_clients]):
            client = TraderOrdersWSClient(
                client_id=i,
                db=self.db,
                traders=batch,
                on_message=self._handle_message,
                on_disconnect=self._handle_disconnect,
                ws_url=self.WS_URL,
            )
            async with self._clients_lock:
                self._clients[i] = client
            start_tasks.append(self._start_client_with_error_handling(client))

        # Wait for all clients to start
        if start_tasks:
            results = await asyncio.gather(*start_tasks, return_exceptions=True)
            successful = sum(1 for r in results if r is True)
            failed = len(results) - successful

            logger.info(
                f"Orders WebSocket clients: {successful} started, {failed} failed/initializing"
            )
        else:
            successful = 0
            logger.warning("No client start tasks created")

        # Start background tasks
        self._process_task = asyncio.create_task(
            self._process_orders_loop(), name="orders_manager_process"
        )
        self._health_check_task = asyncio.create_task(
            self._periodic_health_check(), name="orders_manager_health"
        )

        return successful > 0

    async def _start_client_with_error_handling(self, client: TraderOrdersWSClient) -> bool:
        """Start a client with proper error handling."""
        try:
            return await client.start()
        except Exception as e:
            logger.error(f"Orders Client {client.client_id}: Exception during start: {e}")
            return False

    async def stop(self) -> None:
        """Stop all WebSocket connections gracefully."""
        logger.info("Stopping Persistent Trader Orders WebSocket Manager")
        self._running = False
        self._shutdown_event.set()

        # Cancel background tasks
        if self._process_task and not self._process_task.done():
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass

        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Flush remaining orders
        await self._flush_orders()

        # Stop all clients
        async with self._clients_lock:
            stop_tasks = [client.stop() for client in self._clients.values()]
            self._clients.clear()

        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

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
        """
        Handle client disconnection by recreating and restarting the client.

        This method ensures:
        1. No zombie clients (old client is fully removed)
        2. No duplicate clients (proper replacement)
        3. Clean resource cleanup
        4. Indefinite retry with smart backoff
        """
        logger.warning(f"Orders client {client_id} disconnect handler triggered")

        if not self._running or self._shutdown_event.is_set():
            logger.info(f"Orders manager stopped, not recreating client {client_id}")
            return

        async with self._clients_lock:
            # Find and remove the disconnected client
            old_client = self._clients.pop(client_id, None)

            if old_client is None:
                # Client already removed (possibly by another disconnect handler)
                logger.warning(f"Orders client {client_id} already removed from pool")
                return

            # Stop the old client if still running
            try:
                await old_client.stop()
                logger.debug(f"Orders client {client_id}: Old client stopped successfully")
            except Exception as e:
                logger.debug(f"Orders client {client_id}: Error stopping old client: {e}")

        # Check if we should recreate
        if not self._running or self._shutdown_event.is_set():
            logger.info(f"Orders manager stopped, not recreating client {client_id}")
            return

        # Get fresh trader data
        try:
            all_traders = await self._get_tracked_traders()
        except Exception as e:
            logger.error(f"Failed to get tracked traders for client {client_id}: {e}")
            all_traders = []

        if not all_traders:
            logger.warning(f"No tracked traders found, cannot recreate orders client {client_id}")
            # Schedule retry later
            asyncio.create_task(
                self._schedule_client_recreation(client_id),
                name=f"orders_client_{client_id}_delayed_recreate",
            )
            return

        # Calculate which batch this client was handling
        batch_size = settings.trader_ws_batch_size
        start_idx = client_id * batch_size
        end_idx = start_idx + batch_size
        trader_batch = all_traders[start_idx:end_idx]

        if not trader_batch:
            logger.warning(f"No traders in batch for orders client {client_id}")
            return

        # Create new client
        logger.info(f"Recreating orders client {client_id} with {len(trader_batch)} traders...")
        new_client = TraderOrdersWSClient(
            client_id=client_id,
            db=self.db,
            traders=trader_batch,
            on_message=self._handle_message,
            on_disconnect=self._handle_disconnect,
            ws_url=self.WS_URL,
        )

        # Add new client to pool
        async with self._clients_lock:
            # Check if another client was added with same ID (race condition)
            if client_id in self._clients:
                logger.warning(f"Orders client {client_id}: Zombie client detected, removing it")
                try:
                    await self._clients[client_id].stop()
                except:
                    pass

            self._clients[client_id] = new_client

        # Start the new client (it will handle its own retry logic)
        try:
            success = await new_client.start()
            if success:
                logger.info(f"Orders client {client_id} successfully recreated and started")
            else:
                logger.warning(
                    f"Orders client {client_id} recreation returned False, "
                    f"reconnect logic will handle retry"
                )
        except Exception as e:
            logger.error(f"Error starting recreated orders client {client_id}: {e}")
            # The client's own retry logic will handle this

    async def _schedule_client_recreation(self, client_id: int, delay: float = 30.0) -> None:
        """Schedule client recreation after a delay."""
        try:
            await asyncio.sleep(delay)
            if self._running and not self._shutdown_event.is_set():
                await self._handle_disconnect(client_id)
        except asyncio.CancelledError:
            pass

    async def _process_orders_loop(self) -> None:
        """Periodically process and flush orders."""
        while self._running:
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(), timeout=settings.trader_orders_ws_flush_interval
                )
                break  # Shutdown requested
            except asyncio.TimeoutError:
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
        check_count = 0
        while self._running:
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=60.0,  # Check every minute
                )
                break  # Shutdown requested
            except asyncio.TimeoutError:
                pass

            check_count += 1

            async with self._clients_lock:
                connected_count = sum(1 for c in self._clients.values() if c.is_connected())
                verified_count = sum(1 for c in self._clients.values() if c.is_verified())
                total_clients = len(self._clients)

            total_orders = sum(len(orders) for orders in self._order_states.values())
            buffer_size = len(self._order_buffer)

            # Log health status
            if connected_count < total_clients:
                logger.warning(
                    f"Orders health check #{check_count}: "
                    f"{connected_count}/{total_clients} clients connected, "
                    f"{verified_count} verified, "
                    f"tracking {total_orders} open orders, buffer: {buffer_size}"
                )
            else:
                logger.info(
                    f"Orders health check #{check_count}: "
                    f"All {total_clients} clients connected, "
                    f"tracking {total_orders} open orders, buffer: {buffer_size}"
                )

            # Check for zombie clients (should never happen after fix)
            if total_clients > self._num_clients:
                logger.error(
                    f"ZOMBIE CLIENTS DETECTED: {total_clients} clients in pool, "
                    f"expected {self._num_clients}. Cleaning up..."
                )
                async with self._clients_lock:
                    # Keep only the expected number of clients
                    sorted_ids = sorted(self._clients.keys())[: self._num_clients]
                    clients_to_remove = [cid for cid in self._clients if cid not in sorted_ids]
                    for cid in clients_to_remove:
                        try:
                            await self._clients[cid].stop()
                        except:
                            pass
                        del self._clients[cid]

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics."""
        # Note: get_stats() is synchronous, use the lock's locked state check if needed
        client_stats = [client.get_stats() for client in self._clients.values()]

        total_tracked = sum(len(orders) for orders in self._order_states.values())

        return {
            "running": self._running,
            "total_clients": len(self._clients),
            "expected_clients": self._num_clients,
            "connected_clients": sum(1 for c in self._clients.values() if c.is_connected()),
            "verified_clients": sum(1 for c in self._clients.values() if c.is_verified()),
            "subscribed_traders": len(self._subscribed_traders),
            "tracked_orders": total_tracked,
            "buffer_size": len(self._order_buffer),
            "orders_inserted": self._orders_inserted,
            "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds()
            if self._start_time
            else 0,
            "clients": client_stats,
        }
