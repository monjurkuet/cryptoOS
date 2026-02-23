# src/market_scraper/streaming/websocket_server.py

"""WebSocket server for real-time market data streaming."""

import asyncio
import json
from datetime import datetime
from typing import Any

import structlog
import websockets
from websockets.server import ServerConnection

from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.streaming.subscriptions import SubscriptionManager

logger = structlog.get_logger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects."""

    def default(self, obj: Any) -> str:
        """Encode datetime objects as ISO format strings.

        Args:
            obj: Object to encode

        Returns:
            ISO format string for datetime objects, otherwise calls super
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class WebSocketServer:
    """WebSocket server for real-time market data streaming.

    Features:
    - Multiple concurrent connections
    - Symbol-based subscriptions with event type filtering
    - Automatic reconnection handling via heartbeat/ping-pong
    - JSON message protocol

    Message Protocol:
    Client -> Server:
        - Subscribe: {"action": "subscribe", "symbols": ["BTC-USD"], "event_types": ["trade"]}
        - Unsubscribe: {"action": "unsubscribe", "symbols": ["BTC-USD"]}
        - Ping: {"action": "ping"}

    Server -> Client:
        - Ack: {"type": "ack", "action": "subscribed", "data": {...}}
        - Event: {"type": "event", "data": {...}}
        - Error: {"type": "error", "error": "..."}
        - Pong: {"type": "pong"}
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        event_bus: EventBus | None = None,
    ) -> None:
        """Initialize the WebSocket server.

        Args:
            host: Host address to bind to
            port: Port number to listen on
            event_bus: Optional event bus for receiving broadcast events
        """
        self._host = host
        self._port = port
        self._event_bus = event_bus
        self._subscription_manager = SubscriptionManager()
        self._server: websockets.WebSocketServer | None = None
        self._running = False
        self._logger = logger.bind(component="websocket_server")

    async def start(self) -> None:
        """Start the WebSocket server.

        Starts the server with automatic ping/pong heartbeat to detect
        and clean up stale connections.
        """
        self._running = True

        self._server = await websockets.serve(
            self._handle_connection,
            self._host,
            self._port,
            ping_interval=20,
            ping_timeout=10,
        )

        self._logger.info(
            "WebSocket server started",
            host=self._host,
            port=self._port,
        )

        # Subscribe to event bus for broadcasting (wildcard for all events)
        if self._event_bus:
            await self._event_bus.subscribe("*", self._on_event)
            self._logger.debug("Subscribed to event bus for broadcasting")

    async def stop(self) -> None:
        """Stop the WebSocket server gracefully.

        Closes all connections and cleans up resources.
        """
        self._running = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        self._logger.info("WebSocket server stopped")

    async def _handle_connection(
        self,
        websocket: ServerConnection,
        path: str,
    ) -> None:
        """Handle a new WebSocket connection.

        Args:
            websocket: WebSocket protocol instance
            path: Connection path (unused but required by websockets API)
        """
        client_id = str(id(websocket))

        self._logger.info(
            "Client connected",
            client_id=client_id,
            remote_address=str(websocket.remote_address),
            path=path,
        )

        try:
            async for message in websocket:
                try:
                    await self._handle_message(websocket, message)
                except json.JSONDecodeError:
                    await self._send_error(websocket, "Invalid JSON format")
                    self._logger.warning(
                        "invalid_json_received",
                        client_id=client_id,
                        message_preview=str(message)[:100],
                    )
                except Exception as e:
                    self._logger.error(
                        "message_handle_error",
                        client_id=client_id,
                        error=str(e),
                        exc_info=True,
                    )
                    await self._send_error(websocket, f"Internal error: {str(e)}")
        except websockets.exceptions.ConnectionClosed:
            self._logger.debug(
                "connection_closed",
                client_id=client_id,
            )
        except Exception as e:
            self._logger.error(
                "connection_error",
                client_id=client_id,
                error=str(e),
                exc_info=True,
            )
        finally:
            # Clean up subscriptions when client disconnects
            self._subscription_manager.remove_client(client_id)
            self._logger.info("Client disconnected", client_id=client_id)

    async def _handle_message(
        self,
        websocket: ServerConnection,
        message: str,
    ) -> None:
        """Handle incoming WebSocket message.

        Args:
            websocket: WebSocket protocol instance
            message: Raw message string (JSON)
        """
        try:
            data: dict[str, Any] = json.loads(message)
        except json.JSONDecodeError as e:
            await self._send_error(websocket, f"Invalid JSON: {e}")
            return

        action = data.get("action")
        client_id = str(id(websocket))

        self._logger.debug(
            "Received message",
            client_id=client_id,
            action=action,
        )

        if action == "subscribe":
            await self._handle_subscribe(websocket, data)
        elif action == "unsubscribe":
            await self._handle_unsubscribe(websocket, data)
        elif action == "ping":
            await websocket.send(json.dumps({"type": "pong"}))
        else:
            await self._send_error(websocket, f"Unknown action: {action}")
            self._logger.warning(
                "unknown_action",
                client_id=client_id,
                action=action,
            )

    async def _handle_subscribe(
        self,
        websocket: ServerConnection,
        data: dict[str, Any],
    ) -> None:
        """Handle subscribe action.

        Args:
            websocket: WebSocket protocol instance
            data: Message data containing symbols and event_types
        """
        client_id = str(id(websocket))
        symbols = data.get("symbols", [])
        event_types = data.get("event_types", ["*"])

        if not symbols:
            await self._send_error(websocket, "Missing 'symbols' field")
            return

        # Subscribe to each symbol/event_type combination
        for symbol in symbols:
            for event_type in event_types:
                self._subscription_manager.subscribe(
                    client_id,
                    websocket,
                    symbol,
                    event_type,
                )

        await self._send_ack(
            websocket,
            "subscribed",
            {
                "symbols": symbols,
                "event_types": event_types,
            },
        )

        self._logger.info(
            "Client subscribed",
            client_id=client_id,
            symbols=symbols,
            event_types=event_types,
        )

    async def _handle_unsubscribe(
        self,
        websocket: ServerConnection,
        data: dict[str, Any],
    ) -> None:
        """Handle unsubscribe action.

        Args:
            websocket: WebSocket protocol instance
            data: Message data containing symbols to unsubscribe
        """
        client_id = str(id(websocket))
        symbols = data.get("symbols", [])
        event_type = data.get("event_type")  # Optional: specific event type

        if not symbols:
            await self._send_error(websocket, "Missing 'symbols' field")
            return

        # Unsubscribe from each symbol
        total_removed = 0
        for symbol in symbols:
            removed = self._subscription_manager.unsubscribe(client_id, symbol, event_type)
            total_removed += removed

        await self._send_ack(
            websocket,
            "unsubscribed",
            {
                "symbols": symbols,
                "event_type": event_type,
                "removed_count": total_removed,
            },
        )

        self._logger.info(
            "Client unsubscribed",
            client_id=client_id,
            symbols=symbols,
            event_type=event_type,
            removed_count=total_removed,
        )

    async def _on_event(self, event: StandardEvent) -> None:
        """Handle events from event bus for broadcasting.

        Called when an event is published to the event bus.
        Broadcasts the event to all subscribed clients.

        Args:
            event: StandardEvent to broadcast
        """
        if not self._running:
            return

        # Extract symbol from event payload if available
        symbol: str | None = None
        if isinstance(event.payload, dict):
            symbol = event.payload.get("symbol")
        elif hasattr(event.payload, "symbol"):
            symbol = event.payload.symbol

        event_type = str(event.event_type)

        # Get clients subscribed to this symbol and event type
        clients = self._subscription_manager.get_subscribers(symbol, event_type)

        if not clients:
            return

        # Prepare message
        message = json.dumps(
            {
                "type": "event",
                "data": event.model_dump(),
            },
            cls=DateTimeEncoder,
        )

        # Broadcast to all subscribed clients
        results = await asyncio.gather(
            *[client.send(message) for client in clients],
            return_exceptions=True,
        )

        # Log any errors
        error_count = sum(1 for r in results if isinstance(r, Exception))
        if error_count > 0:
            self._logger.warning(
                "broadcast_errors",
                symbol=symbol,
                event_type=event_type,
                subscriber_count=len(clients),
                error_count=error_count,
            )

    async def _send_ack(
        self,
        websocket: ServerConnection,
        action: str,
        data: dict[str, Any],
    ) -> None:
        """Send acknowledgment message.

        Args:
            websocket: WebSocket protocol instance
            action: Action being acknowledged (e.g., "subscribed")
            data: Additional data to include in response
        """
        await websocket.send(
            json.dumps(
                {
                    "type": "ack",
                    "action": action,
                    "data": data,
                }
            )
        )

    async def _send_error(
        self,
        websocket: ServerConnection,
        error: str,
    ) -> None:
        """Send error message.

        Args:
            websocket: WebSocket protocol instance
            error: Error message string
        """
        await websocket.send(
            json.dumps(
                {
                    "type": "error",
                    "error": error,
                }
            )
        )

    def get_stats(self) -> dict[str, Any]:
        """Get server statistics.

        Returns:
            Dictionary containing server and subscription statistics
        """
        return {
            "running": self._running,
            "host": self._host,
            "port": self._port,
            **self._subscription_manager.get_stats(),
        }
