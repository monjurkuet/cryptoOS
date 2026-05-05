# src/market_scraper/connectors/hyperliquid/collectors/manager.py

"""Collector manager for orchestrating all Hyperliquid collectors."""

import asyncio
import json
import random
from typing import Any

import structlog
import websockets
from websockets.exceptions import ConnectionClosed

from market_scraper.config.market_config import BufferConfig
from market_scraper.connectors.hyperliquid.collectors.base import BaseCollector
from market_scraper.connectors.hyperliquid.collectors.candles import CandlesCollector
from market_scraper.core.config import HyperliquidSettings
from market_scraper.event_bus.base import EventBus

logger = structlog.get_logger(__name__)


class CollectorManager:
    """Manages all Hyperliquid collectors over a single WebSocket connection.

    Features:
    - Single WebSocket connection for all data types
    - Auto-reconnect with exponential backoff
    - Configurable subscriptions
    - Health monitoring
    - Graceful unsubscribe before close to prevent server-side subscription leaks
    """

    def __init__(
        self,
        event_bus: EventBus,
        config: HyperliquidSettings,
        collectors: list[str] | None = None,
        buffer_config: BufferConfig | None = None,
    ) -> None:
        """Initialize the collector manager.

        Args:
            event_bus: Event bus for publishing events
            config: Hyperliquid settings
            collectors: List of collector names to enable (default: all)
            buffer_config: Buffer configuration for collectors
        """
        self.event_bus = event_bus
        self.config = config
        self._buffer_config = buffer_config or BufferConfig()
        self._ws: Any = None
        self._running = False
        self._reconnect_attempts = 0
        self._collectors: dict[str, BaseCollector] = {}
        self._message_task: asyncio.Task | None = None

        # Initialize collectors
        self._init_collectors(collectors or ["candles"])

    def _init_collectors(self, collector_names: list[str]) -> None:
        """Initialize collector instances.

        Args:
            collector_names: List of collector names to initialize
        """
        collector_classes = {
            "candles": CandlesCollector,
        }

        for name in collector_names:
            if name in collector_classes:
                self._collectors[name] = collector_classes[name](
                    event_bus=self.event_bus,
                    config=self.config,
                    buffer_config=self._buffer_config,
                )
                logger.info("collector_initialized", collector=name)
            else:
                logger.warning("unknown_collector", name=name)

    @property
    def is_running(self) -> bool:
        """Check if manager is running."""
        return self._running

    async def start(self) -> None:
        """Start the collector manager.

        Non-blocking: Starts WebSocket connection in background task.
        """
        if self._running:
            return

        self._running = True
        self._message_task = asyncio.create_task(self._connect())

    async def stop(self) -> None:
        """Stop the collector manager."""
        self._running = False

        # Stop all collectors (flushes buffers)
        for collector in self._collectors.values():
            try:
                await collector.stop()
            except Exception as e:
                logger.warning("collector_stop_error", collector=collector.name, error=str(e))

        # Unsubscribe then close WebSocket
        await self._close_ws()

        # Cancel message task
        if self._message_task:
            self._message_task.cancel()
            try:
                await self._message_task
            except asyncio.CancelledError:
                logger.debug("message_task_cancelled")
            self._message_task = None

        logger.info("collector_manager_stopped")

    async def _close_ws(self) -> None:
        """Unsubscribe from channels, then close the WebSocket cleanly.

        Sending unsubscribe messages before closing lets the Hyperliquid server
        release subscription slots immediately, preventing 'Cannot track more
        than 10' errors on subsequent reconnections.
        """
        if not self._ws:
            return

    # Attempt to send unsubscribe messages if the connection is still alive
    try:
        from websockets.protocol import State
        if self._ws.state == State.OPEN:
            await self._unsubscribe()
    except Exception:
        pass  # If we can't check state, just proceed to close
    try:
        await self._ws.close()
    except Exception as e:
        logger.debug("websocket_close_error", error=str(e))

    self._ws = None

    async def _connect(self) -> None:
        """Connect to WebSocket and subscribe to channels."""
        while self._running:
            try:
                logger.info(
                    "websocket_connecting",
                    url=self.config.ws_url,
                    attempt=self._reconnect_attempts + 1,
                )

                # Connect to WebSocket
                self._ws = await websockets.connect(
                    self.config.ws_url,
                    ping_interval=self.config.heartbeat_interval,
                    ping_timeout=10,
                )

                self._reconnect_attempts = 0
                logger.info("websocket_connected")

                # Subscribe to channels
                await self._subscribe()

                # Start collectors
                for collector in self._collectors.values():
                    try:
                        await collector.start()
                    except Exception as e:
                        logger.error(
                            "collector_start_error",
                            collector=collector.name,
                            error=str(e),
                            exc_info=True,
                        )

                # Start message loop (blocks until disconnect/error)
                await self._message_loop()

            except ConnectionClosed:
                logger.warning("websocket_disconnected")
                await self._handle_disconnect()

            except Exception as e:
                logger.error("websocket_error", error=str(e), exc_info=True)
                await self._handle_disconnect()

    async def _subscribe(self) -> None:
        """Subscribe to WebSocket channels."""
        if not self._ws:
            return

        coin = self.config.symbol

        # Subscribe to candles for each interval
        if "candles" in self._collectors:
            for interval in CandlesCollector.INTERVALS:
                await self._ws.send(
                    json.dumps(
                        {
                            "method": "subscribe",
                            "subscription": {"type": "candle", "coin": coin, "interval": interval},
                        }
                    )
                )

        logger.info("subscriptions_sent", collectors=list(self._collectors.keys()))

    async def _unsubscribe(self) -> None:
        """Send unsubscribe messages for all active subscriptions.

        This lets Hyperliquid's server release subscription slots immediately
        instead of waiting for a timeout, preventing 'Cannot track more than 10'
        type errors on reconnect.
        """
        if not self._ws or self._ws.closed:
            return

        coin = self.config.symbol

        # Unsubscribe from candles for each interval
        if "candles" in self._collectors:
            for interval in CandlesCollector.INTERVALS:
                try:
                    await self._ws.send(
                        json.dumps(
                            {
                                "method": "unsubscribe",
                                "subscription": {"type": "candle", "coin": coin, "interval": interval},
                            }
                        )
                    )
                except Exception:
                    # Connection is broken — no point continuing
                    break

    async def _message_loop(self) -> None:
        """Process incoming WebSocket messages."""
        if not self._ws:
            return

        async for message in self._ws:
            if not self._running:
                break

            try:
                data = json.loads(message)
                await self._process_message(data)
            except json.JSONDecodeError:
                logger.warning("invalid_json", message_preview=message[:100])
            except Exception as e:
                logger.error("message_error", error=str(e), exc_info=True)

    async def _process_message(self, data: dict[str, Any]) -> None:
        """Route message to appropriate collector.

        Args:
            data: Parsed WebSocket message
        """
        channel = data.get("channel", "")

        # Map channels to collectors
        channel_map = {
            "candle": "candles",
        }

        collector_name = channel_map.get(channel)
        if collector_name and collector_name in self._collectors:
            await self._collectors[collector_name].process_message(data)

    async def _handle_disconnect(self) -> None:
        """Handle WebSocket disconnection.

        Unsubscribes, closes the stale connection, stops collectors, then
        sleeps with exponential backoff before the _connect loop retries.
        """
        if not self._running:
            return

        # Unsubscribe on the old WS before closing (mirrors the pattern
        # in TraderWebSocketCollector._handle_error that prevents
        # "Cannot track more than 10" errors on reconnect).
        await self._close_ws()

        # Stop collectors (flushes remaining buffered events)
        for collector in self._collectors.values():
            try:
                await collector.stop()
            except Exception as e:
                logger.warning("collector_stop_error_on_disconnect", collector=collector.name, error=str(e))

        self._reconnect_attempts += 1

        if self._reconnect_attempts > self.config.reconnect_max_attempts:
            logger.error("max_reconnect_attempts_exceeded")
            self._running = False
            return

        # Calculate delay with exponential backoff + jitter
        # Use (reconnect_attempts - 1) as the exponent so the first retry
        # uses the base delay, not 2× the base delay.
        raw_delay = self.config.reconnect_base_delay * (2 ** (self._reconnect_attempts - 1))
        delay = min(raw_delay, self.config.reconnect_max_delay)
        # Add random jitter (0-25% of delay) to desynchronize reconnect attempts
        jitter = delay * random.uniform(0, 0.25)
        delay = delay + jitter

        logger.info(
            "reconnecting",
            attempt=self._reconnect_attempts,
            delay_seconds=round(delay, 2),
        )

        await asyncio.sleep(delay)

    def get_status(self) -> dict[str, Any]:
        """Get status of all collectors.

        Returns:
            Status dictionary
        """
        return {
            "running": self._running,
            "websocket_connected": self._ws is not None and not getattr(self._ws, "closed", True),
            "reconnect_attempts": self._reconnect_attempts,
            "collectors": {
                name: {
                    "running": collector.is_running,
                    "metrics": collector.get_metrics(),
                }
                for name, collector in self._collectors.items()
            },
        }
