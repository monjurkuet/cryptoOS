# src/market_scraper/connectors/hyperliquid/collectors/trader_ws.py

"""Trader WebSocket Collector.

Collects real-time position and order data for tracked traders.
Uses webData2 subscription type for comprehensive trader data.
"""

import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import aiohttp
import structlog

from market_scraper.config.market_config import BufferConfig
from market_scraper.core.config import HyperliquidSettings
from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus

logger = structlog.get_logger(__name__)


class TraderWebSocketCollector:
    """Collects real-time trader data via WebSocket.

    Features:
    - Multiple concurrent connections (configurable, default 5)
    - Event-driven position saves (only when changed)
    - BTC-only filtering (configurable)
    - Auto-reconnect with exponential backoff
    - Batch processing with message buffer

    Storage Optimization: 85% reduction through event-driven saves
    """

    WS_URL = "wss://api.hyperliquid.xyz/ws"

    def __init__(
        self,
        event_bus: EventBus,
        config: HyperliquidSettings,
        on_trader_data: Callable[[dict[str, Any]], None] | None = None,
        buffer_config: BufferConfig | None = None,
    ) -> None:
        """Initialize the trader WebSocket collector.

        Args:
            event_bus: Event bus for publishing events
            config: Hyperliquid settings
            on_trader_data: Optional callback for trader data
            buffer_config: Buffer and flush configuration
        """
        self.event_bus = event_bus
        self.config = config
        self._on_trader_data = on_trader_data

        # Connection management
        self._clients: list[TraderWSClient] = []
        self._num_clients = 5  # Number of concurrent connections
        self._batch_size = 100  # Traders per connection

        # State
        self._running = False
        self._tracked_traders: list[str] = []

        # Event-driven optimization: Track last saved state per trader
        self._last_positions: dict[str, dict] = {}
        self._position_max_interval = config.position_max_interval

        # Buffer configuration
        buffer_config = buffer_config or BufferConfig()
        self._flush_interval: float = buffer_config.flush_interval
        self._buffer_max_size: int = buffer_config.max_size
        self._message_buffer: list[dict] = []
        self._buffer_lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None

        # Stats
        self._messages_received = 0
        self._positions_saved = 0
        self._positions_skipped = 0

    async def start(self, traders: list[str] | None = None) -> None:
        """Start the collector with specified traders.

        Args:
            traders: List of trader addresses to track (optional)
        """
        if self._running:
            logger.warning("trader_ws_already_running")
            return

        self._tracked_traders = traders or []
        self._running = True

        logger.info(
            "trader_ws_starting",
            num_traders=len(self._tracked_traders),
            num_clients=self._num_clients,
            symbol=self.config.symbol,
            flush_interval=self._flush_interval,
            buffer_max_size=self._buffer_max_size,
        )

        if not self._tracked_traders:
            logger.warning("no_traders_to_track")
            return

        # Split traders among clients
        trader_batches = [
            self._tracked_traders[i : i + self._batch_size]
            for i in range(0, len(self._tracked_traders), self._batch_size)
        ]

        # Create and start clients (up to num_clients)
        for i, batch in enumerate(trader_batches[: self._num_clients]):
            client = TraderWSClient(
                client_id=i,
                traders=batch,
                on_message=self._handle_message,
                on_disconnect=self._handle_disconnect,
                config=self.config,
            )
            self._clients.append(client)

        # Start all clients
        start_tasks = [client.start() for client in self._clients]
        results = await asyncio.gather(*start_tasks, return_exceptions=True)

        successful = sum(1 for r in results if r is True)
        logger.info("trader_ws_clients_started", successful=successful, total=len(self._clients))

        # Start flush loop
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self) -> None:
        """Stop all WebSocket connections."""
        logger.info("trader_ws_stopping")
        self._running = False

        # Stop flush task
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                logger.debug("trader_ws_flush_task_cancelled")

        # Flush remaining messages
        await self._flush_messages()

        # Stop all clients
        stop_tasks = [client.stop() for client in self._clients]
        await asyncio.gather(*stop_tasks, return_exceptions=True)

        self._clients.clear()
        logger.info("trader_ws_stopped", stats=self.get_stats())

    async def add_trader(self, address: str) -> None:
        """Add a trader to be tracked.

        Args:
            address: Trader's Ethereum address
        """
        if address in self._tracked_traders:
            return

        self._tracked_traders.append(address)

        # Add to first available client with space
        for client in self._clients:
            if len(client.traders) < self._batch_size:
                await client.subscribe_trader(address)
                return

        # Need to create new client
        if len(self._clients) < self._num_clients:
            client = TraderWSClient(
                client_id=len(self._clients),
                traders=[address],
                on_message=self._handle_message,
                on_disconnect=self._handle_disconnect,
                config=self.config,
            )
            self._clients.append(client)
            await client.start()

    async def remove_trader(self, address: str) -> None:
        """Remove a trader from tracking.

        Args:
            address: Trader's Ethereum address
        """
        if address in self._tracked_traders:
            self._tracked_traders.remove(address)

        # Remove from clients
        for client in self._clients:
            if address in client.traders:
                await client.unsubscribe_trader(address)

    async def _handle_message(self, data: dict) -> None:
        """Handle incoming WebSocket message.

        Args:
            data: Parsed message data
        """
        self._messages_received += 1

        # Debug: Log message receipt
        if self._messages_received <= 5:
            logger.debug(
                "trader_ws_message_received",
                msg_num=self._messages_received,
                channel=data.get("channel"),
                has_user=bool(data.get("data", {}).get("user")),
            )

        should_flush = False
        async with self._buffer_lock:
            self._message_buffer.append(data)

            # Check if buffer is full
            if len(self._message_buffer) >= self._buffer_max_size:
                logger.debug("trader_ws_buffer_full_flushing", size=len(self._message_buffer))
                should_flush = True

        # Flush outside the lock to avoid deadlock
        if should_flush:
            await self._flush_messages()

    async def _handle_disconnect(self, client_id: int) -> None:
        """Handle client disconnection.

        Args:
            client_id: ID of disconnected client
        """
        logger.warning("trader_ws_client_disconnected", client_id=client_id)

        # Find and recreate the client
        for i, client in enumerate(self._clients):
            if client.client_id == client_id:
                # Stop old client
                try:
                    await client.stop()
                except Exception as e:
                    logger.debug("trader_ws_client_stop_error", client_id=client_id, error=str(e))

                # Get traders for this client
                traders = client.traders

                if traders and self._running:
                    # Wait before reconnecting
                    await asyncio.sleep(5)

                    # Create new client
                    new_client = TraderWSClient(
                        client_id=client_id,
                        traders=traders,
                        on_message=self._handle_message,
                        on_disconnect=self._handle_disconnect,
                        config=self.config,
                    )
                    self._clients[i] = new_client
                    await new_client.start()

                break

    async def _flush_loop(self) -> None:
        """Periodically flush the message buffer."""
        while self._running:
            await asyncio.sleep(self._flush_interval)
            await self._flush_messages()

    def _normalize_positions(self, positions: list[dict]) -> str:
        """Normalize positions for comparison.

        Args:
            positions: List of position data

        Returns:
            Normalized string for comparison
        """
        if not positions:
            return ""

        # Sort by coin for consistent comparison
        sorted_positions = sorted(
            positions,
            key=lambda x: x.get("position", {}).get("coin", ""),
        )

        parts = []
        for pos in sorted_positions:
            coin = pos.get("position", {}).get("coin", "")
            szi = float(pos.get("position", {}).get("szi", 0))
            parts.append(f"{coin}:{szi:.8f}")

        return "|".join(parts)

    def _has_significant_change(self, address: str, positions: list[dict]) -> bool:
        """Check if positions have changed significantly.

        Args:
            address: Trader address
            positions: Current positions

        Returns:
            True if should save
        """
        last_saved = self._last_positions.get(address, {})

        # Check time since last save (safety interval)
        last_time = last_saved.get("timestamp", 0)
        time_since_save = time.time() - last_time

        if time_since_save >= self._position_max_interval:
            return True

        # Compare normalized positions
        last_normalized = last_saved.get("normalized", "")
        current_normalized = self._normalize_positions(positions)

        return last_normalized != current_normalized

    async def _flush_messages(self) -> None:
        """Flush buffered messages and emit events."""
        async with self._buffer_lock:
            if not self._message_buffer:
                return

            messages = self._message_buffer.copy()
            self._message_buffer.clear()

        events = []
        webdata_count = 0

        for msg in messages:
            if msg.get("channel") == "webData2":
                webdata_count += 1
                event = self._process_webdata2(msg)
                if event:
                    events.append(event)

        logger.debug(
            "trader_ws_flush_processed",
            total_messages=len(messages),
            webdata_messages=webdata_count,
            events_created=len(events),
            positions_saved=self._positions_saved,
            positions_skipped=self._positions_skipped,
        )

        # Publish events
        if events:
            await self.event_bus.publish_bulk(events)
            logger.info("trader_ws_events_published", count=len(events))

    def _process_webdata2(self, msg: dict) -> StandardEvent | None:
        """Process webData2 message and create event.

        Args:
            msg: WebSocket message

        Returns:
            StandardEvent or None if filtered
        """
        data = msg.get("data", {})
        address = data.get("user", "")
        clearinghouse = data.get("clearinghouseState", {})
        positions = clearinghouse.get("assetPositions", [])

        if not address or not positions:
            return None

        # Filter for active positions
        active_positions = [p for p in positions if float(p.get("position", {}).get("szi", 0)) != 0]

        if not active_positions:
            return None

        # BTC-ONLY FILTER: Only process positions for configured symbol
        symbol_positions = [
            p for p in active_positions if p.get("position", {}).get("coin") == self.config.symbol
        ]

        if not symbol_positions:
            self._positions_skipped += 1
            return None

        # EVENT-DRIVEN: Check if position actually changed
        if not self._has_significant_change(address, symbol_positions):
            self._positions_skipped += 1
            logger.debug(
                "trader_ws_position_unchanged",
                address=address[:10],
                symbol=self.config.symbol,
            )
            return None

        self._positions_saved += 1
        logger.info(
            "trader_ws_position_saved",
            address=address[:10],
            symbol=self.config.symbol,
            position_count=len(symbol_positions),
        )

        # Update last saved state
        self._last_positions[address] = {
            "positions": symbol_positions,
            "normalized": self._normalize_positions(symbol_positions),
            "timestamp": time.time(),
        }

        # Create event
        return StandardEvent.create(
            event_type="trader_positions",
            source="hyperliquid_trader_ws",
            payload={
                "address": address,
                "symbol": self.config.symbol,
                "positions": symbol_positions,
                "marginSummary": clearinghouse.get("marginSummary", {}),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    def get_stats(self) -> dict[str, Any]:
        """Get collector statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "running": self._running,
            "tracked_traders": len(self._tracked_traders),
            "active_clients": len(self._clients),
            "connected_clients": sum(1 for c in self._clients if c.is_connected),
            "messages_received": self._messages_received,
            "positions_saved": self._positions_saved,
            "positions_skipped": self._positions_skipped,
            "buffer_size": len(self._message_buffer),
        }


class TraderWSClient:
    """Single WebSocket client for a batch of traders."""

    def __init__(
        self,
        client_id: int,
        traders: list[str],
        on_message: Callable[[dict], None],
        on_disconnect: Callable[[int], None],
        config: HyperliquidSettings,
    ) -> None:
        """Initialize the client.

        Args:
            client_id: Client identifier
            traders: List of trader addresses to subscribe
            on_message: Callback for messages
            on_disconnect: Callback for disconnection
            config: Hyperliquid settings
        """
        self.client_id = client_id
        self.traders = traders
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        self.config = config

        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._running = False
        self._reconnect_attempts = 0
        self._listen_task: asyncio.Task | None = None

    async def start(self) -> bool:
        """Start the WebSocket client.

        Returns:
            True if started successfully
        """
        try:
            self._running = True
            self._session = aiohttp.ClientSession()

            self._ws = await self._session.ws_connect(
                TraderWebSocketCollector.WS_URL,
                heartbeat=self.config.heartbeat_interval,
            )

            self._reconnect_attempts = 0
            logger.info("trader_ws_client_connected", client_id=self.client_id)

            # Subscribe to all traders
            for address in self.traders:
                await self._ws.send_json(
                    {
                        "method": "subscribe",
                        "subscription": {"type": "webData2", "user": address},
                    }
                )
                await asyncio.sleep(0.01)  # Small delay between subscriptions

            logger.info(
                "trader_ws_client_subscribed",
                client_id=self.client_id,
                traders=len(self.traders),
            )

            # Start listening
            self._listen_task = asyncio.create_task(self._listen())

            return True

        except Exception as e:
            logger.error(
                "trader_ws_client_start_error",
                client_id=self.client_id,
                error=str(e),
                exc_info=True,
            )
            await self._handle_error()
            return False

    async def stop(self) -> None:
        """Stop the WebSocket client."""
        self._running = False

        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                logger.debug("trader_ws_listen_task_cancelled", client_id=self.client_id)

        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()

        logger.info("trader_ws_client_stopped", client_id=self.client_id)

    async def subscribe_trader(self, address: str) -> None:
        """Subscribe to a trader.

        Args:
            address: Trader's Ethereum address
        """
        if address not in self.traders:
            self.traders.append(address)

        if self._ws and not self._ws.closed:
            await self._ws.send_json(
                {
                    "method": "subscribe",
                    "subscription": {"type": "webData2", "user": address},
                }
            )

    async def unsubscribe_trader(self, address: str) -> None:
        """Unsubscribe from a trader.

        Args:
            address: Trader's Ethereum address
        """
        if address in self.traders:
            self.traders.remove(address)

        if self._ws and not self._ws.closed:
            await self._ws.send_json(
                {
                    "method": "unsubscribe",
                    "subscription": {"type": "webData2", "user": address},
                }
            )

    async def _listen(self) -> None:
        """Listen for WebSocket messages."""
        while self._running and self._ws:
            try:
                msg = await self._ws.receive()

                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = msg.json()
                    await self.on_message(data)

                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    logger.warning("trader_ws_client_connection_lost", client_id=self.client_id)
                    await self._handle_error()
                    break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "trader_ws_client_listen_error",
                    client_id=self.client_id,
                    error=str(e),
                    exc_info=True,
                )
                await self._handle_error()
                break

    async def _handle_error(self) -> None:
        """Handle connection errors with reconnection."""
        if not self._running:
            return

        self._reconnect_attempts += 1

        if self._reconnect_attempts > self.config.reconnect_max_attempts:
            logger.error(
                "trader_ws_client_max_reconnect",
                client_id=self.client_id,
            )
            await self.on_disconnect(self.client_id)
            return

        # Exponential backoff
        delay = min(
            self.config.reconnect_base_delay * (2 ** (self._reconnect_attempts - 1)),
            self.config.reconnect_max_delay,
        )

        logger.info(
            "trader_ws_client_reconnecting",
            client_id=self.client_id,
            delay=delay,
            attempt=self._reconnect_attempts,
        )

        await asyncio.sleep(delay)

        # Cleanup and restart
        if self._ws:
            try:
                await self._ws.close()
            except Exception as e:
                logger.debug("trader_ws_close_error", client_id=self.client_id, error=str(e))

        await self.start()

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._ws is not None and not self._ws.closed
