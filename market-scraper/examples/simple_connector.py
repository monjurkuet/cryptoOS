"""
Simple Connector Example

This example demonstrates the minimal structure required to create
a custom connector for the Market Scraper Framework.

Usage:
    python examples/simple_connector.py
"""

import asyncio
from datetime import UTC, datetime
from typing import Any, AsyncIterator

from market_scraper.connectors.base import DataConnector, ConnectorConfig
from market_scraper.core.events import StandardEvent, EventType
from market_scraper.core.types import Symbol, Timeframe


class SimpleConnector(DataConnector):
    """A minimal example connector demonstrating the required interface.

    This connector generates sample data for demonstration purposes.
    In a real implementation, you would replace the sample data generation
    with actual API calls to your data source.
    """

    def __init__(self, config: ConnectorConfig) -> None:
        super().__init__(config)
        self._client = None

    async def connect(self) -> None:
        """Establish connection to the data source.

        In a real implementation, this would initialize an HTTP client,
        WebSocket connection, or other connection mechanism.
        """
        print(f"Connecting to {self.name}...")
        # Simulate connection delay
        await asyncio.sleep(0.1)
        self._connected = True
        print(f"Connected to {self.name}")

    async def disconnect(self) -> None:
        """Gracefully close the connection.

        Clean up any resources, close connections, etc.
        """
        print(f"Disconnecting from {self.name}...")
        self._client = None
        self._connected = False
        print(f"Disconnected from {self.name}")

    async def get_historical_data(
        self,
        symbol: Symbol,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[StandardEvent]:
        """Fetch historical market data.

        Args:
            symbol: Trading pair/symbol (e.g., "BTC-USD")
            timeframe: Data granularity (e.g., "1m", "1h", "1d")
            start: Start timestamp (inclusive)
            end: End timestamp (inclusive)

        Returns:
            List of standardized market data events

        Raises:
            DataFetchError: If fetch fails
            ValidationError: If response parsing fails
        """
        print(f"Fetching {timeframe} historical data for {symbol}")
        print(f"  From: {start}")
        print(f"  To:   {end}")

        # In a real implementation, you would:
        # 1. Make API request to your data source
        # 2. Parse the response
        # 3. Convert to StandardEvent format

        # Generate sample data for demonstration
        events = []
        current = start
        price = 50000.0  # Starting price

        while current <= end:
            # Simulate price movement
            import random

            price += random.uniform(-100, 100)

            event = StandardEvent.create(
                event_type=EventType.OHLCV,
                source=self.name,
                payload={
                    "symbol": symbol,
                    "open": price - 50,
                    "high": price + 100,
                    "low": price - 150,
                    "close": price,
                    "volume": random.uniform(100, 1000),
                    "timestamp": current,
                },
            )
            events.append(event)

            # Advance time based on timeframe
            if timeframe == "1m":
                current = datetime(
                    current.year, current.month, current.day, current.hour, current.minute + 1
                )
            elif timeframe == "1h":
                current = datetime(current.year, current.month, current.day, current.hour + 1)
            else:
                current = datetime(current.year, current.month, current.day + 1)

        print(f"  Retrieved {len(events)} events")
        return events

    async def stream_realtime(
        self,
        symbols: list[Symbol],
    ) -> AsyncIterator[StandardEvent]:
        """Stream real-time market data.

        Args:
            symbols: List of symbols to subscribe to

        Yields:
            Standardized market data events as they arrive

        Raises:
            ConnectionError: If stream connection fails
        """
        print(f"Starting real-time stream for {symbols}")

        # In a real implementation, you would:
        # 1. Establish WebSocket connection
        # 2. Subscribe to symbols
        # 3. Listen for messages and yield events

        counter = 0
        while self._connected and counter < 10:  # Limit for demo
            import random

            for symbol in symbols:
                yield StandardEvent.create(
                    event_type=EventType.TRADE,
                    source=self.name,
                    payload={
                        "symbol": symbol,
                        "price": 50000 + random.uniform(-100, 100),
                        "volume": random.uniform(0.1, 10),
                        "timestamp": datetime.now(UTC),
                    },
                )

            await asyncio.sleep(1)
            counter += 1

    async def health_check(self) -> dict[str, Any]:
        """Check connector health.

        Returns:
            Health status dict with:
            - status: "healthy", "degraded", or "unhealthy"
            - latency_ms: Response time in milliseconds
            - message: Human-readable status message
        """
        import time

        start = time.perf_counter()

        try:
            # Simulate health check operation
            await asyncio.sleep(0.05)

            latency_ms = (time.perf_counter() - start) * 1000

            return {
                "status": "healthy" if latency_ms < 500 else "degraded",
                "latency_ms": round(latency_ms, 2),
                "message": "OK",
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "latency_ms": None,
                "message": str(e),
            }


async def main() -> None:
    """Demonstrate using the simple connector."""
    from market_scraper.connectors.registry import ConnectorRegistry

    # Create configuration
    config = ConnectorConfig(
        name="simple_connector",
        enabled=True,
        rate_limit_per_second=10.0,
        timeout_seconds=30.0,
    )

    # Create connector instance
    connector = SimpleConnector(config)

    # Use as async context manager
    async with connector:
        # Check health
        health = await connector.health_check()
        print(f"\nHealth check: {health}\n")

        # Fetch historical data
        from datetime import timedelta

        events = await connector.get_historical_data(
            symbol="BTC-USD",
            timeframe="1h",
            start=datetime.now(UTC) - timedelta(days=1),
            end=datetime.now(UTC),
        )

        # Display sample events
        print(f"\nFirst 3 events:")
        for event in events[:3]:
            print(f"  {event.event_type}: ${event.payload.get('close', 'N/A')}")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
