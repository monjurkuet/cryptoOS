# src/market_scraper/connectors/hyperliquid/connector.py

"""Hyperliquid exchange connector implementation."""

import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

from market_scraper.connectors.base import DataConnector
from market_scraper.connectors.hyperliquid.client import HyperliquidClient
from market_scraper.connectors.hyperliquid.config import HyperliquidConfig
from market_scraper.connectors.hyperliquid.parsers import (
    parse_candle,
    parse_orderbook,
    parse_ticker,
    parse_trade,
)
from market_scraper.core.events import StandardEvent
from market_scraper.core.types import Symbol, Timeframe


class HyperliquidConnector(DataConnector):
    """Hyperliquid exchange connector.

    Provides:
    - Historical candle data
    - Real-time ticker streaming
    - Order book snapshots
    - Trade streaming
    """

    def __init__(self, config: HyperliquidConfig) -> None:
        """Initialize the connector.

        Args:
            config: Hyperliquid-specific configuration
        """
        super().__init__(config)
        self._config = config
        self._client: HyperliquidClient | None = None
        self._ws_connection: Any = None

    @property
    def name(self) -> str:
        """Return connector name."""
        return "hyperliquid"

    async def connect(self) -> None:
        """Initialize HTTP client."""
        self._client = HyperliquidClient(
            base_url=self._config.base_url,
            timeout=self._config.timeout_seconds,
            max_retries=self._config.max_retries,
            retry_delay=self._config.retry_delay_seconds,
        )
        await self._client.connect()
        self._connected = True

    async def disconnect(self) -> None:
        """Close connections."""
        if self._client:
            await self._client.close()
            self._client = None
        if self._ws_connection:
            await self._ws_connection.close()
            self._ws_connection = None
        self._connected = False

    async def get_historical_data(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[StandardEvent]:
        """Fetch historical candle data.

        Args:
            symbol: Trading pair/symbol
            timeframe: Data granularity
            start: Start timestamp
            end: End timestamp

        Returns:
            List of standardized OHLCV events
        """
        if not self._client:
            raise RuntimeError("Not connected")
        assert self._client is not None

        # Convert timeframe to Hyperliquid format
        hl_timeframe = self._convert_timeframe(timeframe)

        # Convert symbol format (BTC-USD -> BTC)
        coin = symbol.replace("-", "").replace("/", "")

        # Fetch candles
        candles = await self._client.get_candles(
            coin=coin,
            timeframe=hl_timeframe,
            start_time=int(start.timestamp() * 1000),
            end_time=int(end.timestamp() * 1000),
        )

        # Convert to StandardEvents
        events = []
        for candle in candles:
            event = parse_candle(candle, self.name, symbol)
            if event:
                events.append(event)

        return events

    async def stream_realtime(
        self,
        symbols: list[Symbol],
    ) -> AsyncIterator[StandardEvent]:
        """Stream real-time market data via WebSocket.

        Args:
            symbols: List of symbols to subscribe to

        Yields:
            Standardized market data events
        """
        if not self._connected:
            raise RuntimeError("Not connected")

        # Connect WebSocket
        self._ws_connection = await websockets.connect(self._config.ws_url)

        try:
            # Subscribe to channels for each symbol
            for symbol in symbols:
                coin = symbol.replace("-", "").replace("/", "")

                # Subscribe to trades
                await self._ws_connection.send(
                    json.dumps(
                        {
                            "method": "subscribe",
                            "subscription": {"type": "trades", "coin": coin},
                        }
                    )
                )

                # Subscribe to order book
                await self._ws_connection.send(
                    json.dumps(
                        {
                            "method": "subscribe",
                            "subscription": {"type": "l2Book", "coin": coin},
                        }
                    )
                )

                # Subscribe to ticker
                await self._ws_connection.send(
                    json.dumps(
                        {
                            "method": "subscribe",
                            "subscription": {"type": "ticker", "coin": coin},
                        }
                    )
                )

            # Process incoming messages
            async for message in self._ws_connection:
                try:
                    data = json.loads(message)
                    event = self._parse_websocket_message(data)
                    if event:
                        yield event
                except json.JSONDecodeError:
                    continue
                except Exception:
                    continue

        except ConnectionClosed:
            self._connected = False
            raise

    async def health_check(self) -> dict[str, Any]:
        """Check Hyperliquid API health.

        Returns:
            Health status dictionary
        """
        if not self._client:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "message": "Client not connected",
            }

        try:
            start = datetime.utcnow()

            # Try to fetch metadata
            meta = await self._client.get_meta()

            latency = (datetime.utcnow() - start).total_seconds() * 1000

            universe = meta.get("universe", [])
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "message": f"Connected, {len(universe)} markets available",
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "latency_ms": 0,
                "message": str(e),
            }

    def _convert_timeframe(self, timeframe: Timeframe) -> str:
        """Convert standard timeframe to Hyperliquid format.

        Args:
            timeframe: Standard timeframe string

        Returns:
            Hyperliquid timeframe string

        Raises:
            ValueError: If timeframe is not supported
        """
        mapping = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d",
        }
        if timeframe not in mapping:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return mapping[timeframe]

    def _parse_websocket_message(self, data: dict) -> StandardEvent | None:
        """Parse WebSocket message into StandardEvent.

        Args:
            data: WebSocket message data

        Returns:
            StandardEvent if message can be parsed, None otherwise
        """
        msg_type = data.get("channel")

        if msg_type == "trades":
            return parse_trade(data, self.name)
        elif msg_type == "l2Book":
            return parse_orderbook(data, self.name)
        elif msg_type == "ticker":
            return parse_ticker(data, self.name)

        return None
