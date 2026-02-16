"""
Hyperliquid WebSocket Client.

This module provides a WebSocket client for real-time data streaming
from the Hyperliquid exchange.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import aiohttp
from loguru import logger

from src.config import settings


class HyperliquidWebSocketClient:
    """
    Async WebSocket client for Hyperliquid real-time data.

    Supports:
    - Orderbook (L2 book) updates
    - Trade streams
    - Candle updates
    - All mids (mark prices)
    """

    WS_URL = "wss://api.hyperliquid.xyz/ws"

    def __init__(
        self,
        reconnect: bool = True,
        reconnect_delay: float = 5.0,
        max_reconnect_attempts: int = 10,
    ):
        """
        Initialize the WebSocket client.

        Args:
            reconnect: Whether to automatically reconnect on disconnect
            reconnect_delay: Delay between reconnection attempts (seconds)
            max_reconnect_attempts: Maximum number of reconnection attempts
        """
        self.reconnect = reconnect
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts

        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False
        self._reconnect_count = 0

        # Subscriptions
        self._subscriptions: Dict[str, Dict] = {}
        self._message_handlers: Dict[str, Callable] = {}

    async def __aenter__(self) -> "HyperliquidWebSocketClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def connect(self) -> bool:
        """
        Establish WebSocket connection.

        Returns:
            True if connection successful
        """
        try:
            self._session = aiohttp.ClientSession()
            self._ws = await self._session.ws_connect(
                self.WS_URL,
                heartbeat=30,
            )
            self._running = True
            self._reconnect_count = 0
            logger.info("WebSocket connected to Hyperliquid")

            # Resubscribe to existing subscriptions
            await self._resubscribe()

            return True

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            await self._cleanup()
            return False

    async def disconnect(self) -> None:
        """Disconnect WebSocket and cleanup."""
        self._running = False
        await self._cleanup()
        logger.info("WebSocket disconnected")

    async def _cleanup(self) -> None:
        """Cleanup resources."""
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._session:
            await self._session.close()
            self._session = None

    async def _resubscribe(self) -> None:
        """Resubscribe to all active subscriptions."""
        for sub_id, sub_data in self._subscriptions.items():
            await self._send_subscription(sub_id, sub_data)

    async def subscribe(
        self,
        subscription_type: str,
        coin: str = "BTC",
        handler: Optional[Callable] = None,
        interval: str = None,
    ) -> str:
        """
        Subscribe to a data feed.

        Args:
            subscription_type: Type of subscription (trades, l2Book, candles, allMids)
            coin: Coin to subscribe to
            handler: Async function to handle messages
            interval: Candle interval (required for candle subscription)

        Returns:
            Subscription ID
        """
        # Map friendly names to Hyperliquid WebSocket types
        type_mapping = {
            "orderbook": "l2Book",  # WebSocket uses l2Book, not orderbook
            "trades": "trades",
            "candle": "candle",  # Note: singular, not candles
            "allMids": "allMids",
        }

        ws_type = type_mapping.get(subscription_type, subscription_type)

        sub_id = f"{subscription_type}:{coin}"
        if interval:
            sub_id = f"{subscription_type}:{coin}:{interval}"

        subscription = {
            "type": ws_type,
            "coin": coin,
        }

        # Add interval for candle subscriptions
        if interval and ws_type == "candle":
            subscription["interval"] = interval

        self._subscriptions[sub_id] = subscription

        if handler:
            self._message_handlers[sub_id] = handler

        if self._ws and self._running:
            await self._send_subscription(sub_id, subscription)

        logger.info(f"Subscribed to {sub_id} (ws type: {ws_type})")
        return sub_id

    async def _send_subscription(self, sub_id: str, subscription: Dict) -> None:
        """Send subscription message to WebSocket."""
        if not self._ws:
            return

        message = {
            "method": "subscribe",
            "subscription": subscription,
        }
        await self._ws.send_json(message)

    async def unsubscribe(self, sub_id: str) -> None:
        """
        Unsubscribe from a data feed.

        Args:
            sub_id: Subscription ID to remove
        """
        if sub_id in self._subscriptions:
            del self._subscriptions[sub_id]

        if sub_id in self._message_handlers:
            del self._message_handlers[sub_id]

        logger.info(f"Unsubscribed from {sub_id}")

    async def listen(self) -> None:
        """Main listening loop - processes incoming messages."""
        logger.info("WebSocket listening for messages...")

        while self._running:
            try:
                if not self._ws:
                    if self.reconnect and self._reconnect_count < self.max_reconnect_attempts:
                        await self._handle_reconnect()
                    else:
                        break

                msg = await self._ws.receive()

                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_message(msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {msg.data}")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    logger.warning("WebSocket closed by server")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.warning("WebSocket connection closed")
                    break

            except asyncio.CancelledError:
                logger.info("WebSocket listener cancelled")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket listener: {e}")
                if self.reconnect and self._reconnect_count < self.max_reconnect_attempts:
                    await self._handle_reconnect()
                else:
                    break

        if self._running and self.reconnect:
            await self._handle_reconnect()

    async def _handle_reconnect(self) -> None:
        """Handle reconnection with exponential backoff."""
        self._reconnect_count += 1
        delay = self.reconnect_delay * (2 ** (self._reconnect_count - 1))
        delay = min(delay, 60)  # Cap at 60 seconds

        logger.info(f"Reconnecting in {delay:.1f}s (attempt {self._reconnect_count})...")
        await asyncio.sleep(delay)

        if await self.connect():
            logger.info("WebSocket reconnected successfully")
            # Start listening again
            asyncio.create_task(self.listen())

    async def _handle_message(self, raw_message: str) -> None:
        """Process incoming WebSocket message."""
        try:
            data = json.loads(raw_message)

            # Log all messages for debugging
            if isinstance(data, dict):
                logger.debug(f"WS message: {data.keys()}, channel: {data.get('channel')}")

            # Handle different message types
            if isinstance(data, dict):
                # Check for channel field to determine message type
                channel = data.get("channel", "")

                # Log error messages
                if channel == "error":
                    logger.warning(f"WebSocket error: {data}")

                # Subscription response
                if channel == "subscriptionResponse":
                    logger.debug(f"Subscription confirmed: {data}")
                    return

                # Data message - route to appropriate handler
                # Message format: {"channel": "orderbook", "data": {...}} or {"channel": "trades", "data": [...]}
                data_payload = data.get("data")

                if data_payload is None:
                    logger.debug(f"No data payload in message: {data.keys()}")
                    return

                # Route to handler based on channel type
                # Also handle the mapping from l2Book -> orderbook
                channel_to_handler = {
                    "trades": "trades",
                    "l2Book": "orderbook",  # Map l2Book to orderbook handler
                    "candles": "candles",
                    "allMids": "allMids",
                }

                for sub_id, handler in self._message_handlers.items():
                    sub_type = sub_id.split(":")[0]

                    # Get the actual channel from the message
                    actual_channel = channel_to_handler.get(channel, channel)

                    # Check if this handler matches the channel
                    if sub_type == actual_channel:
                        logger.debug(f"Routing {channel} to handler {sub_id}")
                        try:
                            # Pass the data payload
                            await handler(data_payload)
                        except Exception as e:
                            logger.error(f"Handler error for {sub_id}: {e}")

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON message: {raw_message[:100]}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._ws is not None and not self._ws.closed


class WebSocketManager:
    """
    Manager for multiple WebSocket connections and data streams.

    Provides a higher-level interface for managing real-time data collection.
    """

    def __init__(self):
        """Initialize the WebSocket manager."""
        self.ws_client: Optional[HyperliquidWebSocketClient] = None
        self._tasks: List[asyncio.Task] = []
        self._running = False

    async def start(self) -> bool:
        """
        Start the WebSocket manager.

        Returns:
            True if started successfully
        """
        self.ws_client = HyperliquidWebSocketClient()
        connected = await self.ws_client.connect()

        if connected:
            self._running = True
            # Start listener in background
            listener_task = asyncio.create_task(self.ws_client.listen())
            self._tasks.append(listener_task)
            logger.info("WebSocket manager started")

        return connected

    async def stop(self) -> None:
        """Stop the WebSocket manager and cleanup."""
        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        self._tasks.clear()

        # Disconnect WebSocket
        if self.ws_client:
            await self.ws_client.disconnect()
            self.ws_client = None

        logger.info("WebSocket manager stopped")

    async def subscribe(
        self,
        subscription_type: str,
        coin: str = "BTC",
        handler: Callable[[Dict], Any] = None,
    ) -> str:
        """
        Generic subscribe method.

        Args:
            subscription_type: Type of subscription
            coin: Coin to subscribe to
            handler: Handler function

        Returns:
            Subscription ID
        """
        if not self.ws_client:
            raise RuntimeError("WebSocket manager not started")

        # Build subscription based on type
        subscription = {"type": subscription_type, "coin": coin}

        # Candle requires interval parameter
        if subscription_type == "candle":
            # Default to 1m if not specified - but we need to handle multiple intervals
            # For now, let the caller handle this via specific methods
            pass

        return await self.ws_client.subscribe(
            subscription_type=subscription_type,
            coin=coin,
            handler=handler,
        )

    async def subscribe_candles(
        self,
        coin: str,
        interval: str = "1m",
        handler: Callable[[Dict], Any] = None,
    ) -> str:
        """
        Subscribe to candle updates.

        Args:
            coin: Coin to subscribe to
            interval: Candle interval (1m, 5m, 15m, 1h, 4h, 1d)
            handler: Async function to handle candle data

        Returns:
            Subscription ID
        """
        if not self.ws_client:
            raise RuntimeError("WebSocket manager not started")

        return await self.ws_client.subscribe(
            subscription_type="candle",
            coin=coin,
            handler=handler,
            interval=interval,  # Pass interval
        )

    async def subscribe_orderbook(
        self,
        coin: str,
        handler: Callable[[Dict], Any],
    ) -> str:
        """
        Subscribe to orderbook updates.

        Args:
            coin: Coin to subscribe to (e.g., "BTC", "ETH")
            handler: Async function to handle orderbook data

        Returns:
            Subscription ID
        """
        if not self.ws_client:
            raise RuntimeError("WebSocket manager not started")

        return await self.ws_client.subscribe(
            subscription_type="orderbook",
            coin=coin,
            handler=handler,
        )

    async def subscribe_trades(
        self,
        coin: str,
        handler: Callable[[Dict], Any],
    ) -> str:
        """
        Subscribe to trade updates.

        Args:
            coin: Coin to subscribe to (e.g., "BTC", "ETH")
            handler: Async function to handle trade data

        Returns:
            Subscription ID
        """
        if not self.ws_client:
            raise RuntimeError("WebSocket manager not started")

        return await self.ws_client.subscribe(
            subscription_type="trades",
            coin=coin,
            handler=handler,
        )

    async def subscribe_all_mids(
        self,
        handler: Callable[[Dict], Any],
    ) -> str:
        """
        Subscribe to all mark prices.

        Args:
            handler: Async function to handle mids data

        Returns:
            Subscription ID
        """
        if not self.ws_client:
            raise RuntimeError("WebSocket manager not started")

        return await self.ws_client.subscribe(
            subscription_type="allMids",
            coin="",  # Not needed for allMids
            handler=handler,
        )

    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self.ws_client is not None and self.ws_client.is_connected()
