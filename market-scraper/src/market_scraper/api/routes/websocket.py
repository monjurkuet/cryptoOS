# src/market_scraper/api/routes/websocket.py

"""WebSocket route for real-time market data streaming.

This module provides WebSocket endpoints that integrate with the event bus
for real-time streaming of market data, trader updates, and signals.
"""

import asyncio
from contextlib import suppress
from typing import Any

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from market_scraper.core.events import StandardEvent

logger = structlog.get_logger(__name__)

router = APIRouter()


class ConnectionManager:
    """WebSocket connection manager for tracking active connections."""

    def __init__(self) -> None:
        """Initialize the connection manager."""
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        """Connect a WebSocket to a channel.

        Args:
            websocket: The WebSocket connection.
            channel: The channel to subscribe to.
        """
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
        logger.info(
            "websocket_connected",
            channel=channel,
            total=len(self.active_connections.get(channel, [])),
        )

    def disconnect(self, websocket: WebSocket, channel: str) -> None:
        """Disconnect a WebSocket from a channel.

        Args:
            websocket: The WebSocket connection.
            channel: The channel to unsubscribe from.
        """
        if channel in self.active_connections:
            self.active_connections[channel] = [
                conn for conn in self.active_connections[channel] if conn != websocket
            ]
            if not self.active_connections[channel]:
                del self.active_connections[channel]
        logger.info("websocket_disconnected", channel=channel)

    async def send_message(self, message: dict[str, Any], channel: str) -> None:
        """Send a message to all connections in a channel.

        Args:
            message: The message to send.
            channel: The target channel.
        """
        if channel in self.active_connections:
            for connection in self.active_connections[channel]:
                with suppress(Exception):
                    await connection.send_json(message)

    def get_connection_count(self, channel: str | None = None) -> int:
        """Get the number of active connections.

        Args:
            channel: Optional channel to count connections for.

        Returns:
            Number of active connections.
        """
        if channel:
            return len(self.active_connections.get(channel, []))
        return sum(len(conns) for conns in self.active_connections.values())


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    channel: str = Query(
        "traders", description="Channel to subscribe to (traders, signals)"
    ),
) -> None:
    """WebSocket endpoint for real-time market data streaming.

    Connect to receive real-time updates from the event bus.

    Channels:
    - **traders**: Trader position and score updates
    - **signals**: Trading signal alerts

    The connection will receive JSON messages containing event data.

    Example:
        ```javascript
        const ws = new WebSocket('ws://localhost:8000/ws?channel=traders');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Received:', data);
        };
        ```
    """
    await manager.connect(websocket, channel)

    try:
        # Try to get lifecycle from app state (may not be available in all contexts)
        lifecycle = None
        try:
            lifecycle = websocket.app.state.lifecycle
        except AttributeError:
            logger.debug("websocket_no_lifecycle_state", channel=channel)

        if lifecycle and lifecycle.event_bus:
            # Subscribe to event bus
            event_bus = lifecycle.event_bus
            receive_task = asyncio.create_task(websocket.receive_text())

            async def event_handler(event: StandardEvent) -> None:
                """Handle events from the event bus and send to WebSocket."""
                try:
                    await websocket.send_json(event.model_dump())
                except Exception as e:
                    logger.debug("websocket_send_error", error=str(e))

            # Subscribe to the channel
            await event_bus.subscribe(channel, event_handler)

            try:
                # Keep connection alive and handle incoming messages
                while True:
                    try:
                        # Wait for either a message or a timeout (heartbeat)
                        result = await asyncio.wait_for(receive_task, timeout=30.0)

                        # Handle ping/pong or other client messages
                        if result.lower() == "ping":
                            await websocket.send_text("pong")
                        elif result.lower() == "pong":
                            pass  # Ignore pong responses
                        else:
                            # Echo other messages for backward compatibility
                            await websocket.send_text(f"Echo: {result}")

                        # Create new receive task for next message
                        receive_task = asyncio.create_task(websocket.receive_text())

                    except TimeoutError:
                        # Send heartbeat on timeout
                        try:
                            await websocket.send_json({"type": "heartbeat"})
                        except Exception:
                            break  # Connection likely closed

            finally:
                # Unsubscribe from event bus
                await event_bus.unsubscribe(channel, event_handler)

        else:
            # Fallback: Simple echo mode when event bus is not available
            logger.info("websocket_echo_mode", channel=channel)
            while True:
                try:
                    data = await websocket.receive_text()
                    if data.lower() == "ping":
                        await websocket.send_text("pong")
                    else:
                        await websocket.send_text(f"Echo: {data}")
                except WebSocketDisconnect:
                    break

    except WebSocketDisconnect:
        logger.debug("websocket_client_disconnected", channel=channel)
    except Exception as e:
        logger.error("websocket_error", error=str(e), channel=channel, exc_info=True)
    finally:
        manager.disconnect(websocket, channel)


@router.get("/ws/status")
async def websocket_status() -> dict[str, Any]:
    """Get WebSocket connection status.

    Returns:
        Status information about active WebSocket connections.
    """
    return {
        "total_connections": manager.get_connection_count(),
        "channels": {channel: len(conns) for channel, conns in manager.active_connections.items()},
    }
