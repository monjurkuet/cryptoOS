"""
Custom Processor Example

This example demonstrates how to create a custom processor for
transforming, validating, or filtering events in the Market Scraper Framework.

Usage:
    python examples/custom_processor.py
"""

import asyncio
from typing import Any

from market_scraper.core.events import StandardEvent, EventType
from market_scraper.event_bus import MemoryEventBus
from market_scraper.processors.base import Processor


class PriceAlertProcessor(Processor):
    """A processor that detects significant price movements.

    This processor:
    1. Subscribes to trade events
    2. Tracks price history
    3. Emits alerts when price changes exceed a threshold
    """

    def __init__(
        self,
        event_bus: MemoryEventBus,
        price_change_threshold: float = 0.05,  # 5% change
    ) -> None:
        super().__init__(event_bus)
        self._price_change_threshold = price_change_threshold
        self._last_prices: dict[str, float] = {}
        self._alerts: list[dict[str, Any]] = []

    async def process(self, event: StandardEvent) -> StandardEvent | None:
        """Process a trade event and check for price alerts.

        Args:
            event: The incoming trade event

        Returns:
            The original event, or None if filtered out
        """
        # Only process trade events
        if event.event_type != EventType.TRADE:
            return event

        symbol = event.payload.get("symbol")
        price = event.payload.get("price")

        if not symbol or price is None:
            return event

        # Check for price alert
        if symbol in self._last_prices:
            last_price = self._last_prices[symbol]
            change = abs(price - last_price) / last_price

            if change >= self._price_change_threshold:
                alert = {
                    "symbol": symbol,
                    "last_price": last_price,
                    "current_price": price,
                    "change_percent": change * 100,
                    "direction": "up" if price > last_price else "down",
                    "timestamp": event.timestamp,
                }
                self._alerts.append(alert)
                print(
                    f"  ALERT: {symbol} moved {alert['change_percent']:.2f}% "
                    f"(${last_price:.2f} -> ${price:.2f})"
                )

        # Update last price
        self._last_prices[symbol] = price

        # Return event unchanged
        return event

    def get_alerts(self) -> list[dict[str, Any]]:
        """Get all triggered alerts."""
        return self._alerts.copy()


class DataEnrichmentProcessor(Processor):
    """A processor that enriches events with additional data.

    This processor adds computed fields to events:
    - Trade value (price * volume)
    - Market cap (for certain assets)
    """

    async def process(self, event: StandardEvent) -> StandardEvent | None:
        """Enrich the event with additional data.

        Args:
            event: The incoming event

        Returns:
            The enriched event
        """
        payload = event.payload

        # Add trade value
        if event.event_type == EventType.TRADE:
            price = payload.get("price", 0)
            volume = payload.get("volume", 0)
            payload["trade_value"] = price * volume

        # Add processed timestamp to all events
        from datetime import UTC, datetime

        payload["enriched_at"] = datetime.now(UTC).isoformat()

        return event


class ValidationProcessor(Processor):
    """A processor that validates incoming data.

    This processor:
    1. Checks for required fields
    2. Validates data types
    3. Filters out invalid events
    """

    REQUIRED_FIELDS = {
        EventType.TRADE: ["symbol", "price", "timestamp"],
        EventType.TICKER: ["symbol", "price", "timestamp"],
        EventType.OHLCV: ["symbol", "open", "high", "low", "close", "timestamp"],
    }

    async def process(self, event: StandardEvent) -> StandardEvent | None:
        """Validate the event.

        Args:
            event: The incoming event

        Returns:
            The event if valid, None if filtered out
        """
        required = self.REQUIRED_FIELDS.get(event.event_type, [])

        for field in required:
            if field not in event.payload or event.payload[field] is None:
                print(f"  Validation failed: missing {field} in {event.event_type}")
                return None

        # Validate price is positive
        price = event.payload.get("price")
        if price is not None and price <= 0:
            print(f"  Validation failed: invalid price {price}")
            return None

        # Validate OHLCV relationships
        if event.event_type == EventType.OHLCV:
            if not (
                event.payload["low"] <= event.payload["open"] <= event.payload["high"]
                and event.payload["low"] <= event.payload["close"] <= event.payload["high"]
            ):
                print(f"  Validation failed: invalid OHLCV relationship")
                return None

        return event


async def main() -> None:
    """Demonstrate custom processors."""

    # Create event bus
    bus = MemoryEventBus()

    # Create processors
    alert_processor = PriceAlertProcessor(
        bus,
        price_change_threshold=0.02,  # 2% threshold for demo
    )
    enrichment_processor = DataEnrichmentProcessor(bus)
    validation_processor = ValidationProcessor(bus)

    # Start processors
    await alert_processor.start()
    await enrichment_processor.start()
    await validation_processor.start()

    # Subscribe to events
    async def process_pipeline(event: StandardEvent):
        # Run through validation first
        event = await validation_processor.process(event)
        if event is None:
            return

        # Then enrichment
        event = await enrichment_processor.process(event)

        # Finally alerts
        await alert_processor.process(event)

    await bus.subscribe(EventType.TRADE, process_pipeline)

    # Generate sample events
    print("Generating sample trade events...")
    print("-" * 50)

    prices = [50000, 50100, 49900, 51000, 50500]

    for i, price in enumerate(prices):
        event = StandardEvent.create(
            event_type=EventType.TRADE,
            source="demo",
            payload={
                "symbol": "BTC-USD",
                "price": price,
                "volume": 1.5,
                "timestamp": f"2024-01-15T10:{i:02d}:00Z",
            },
        )

        await bus.publish(event)
        await asyncio.sleep(0.1)  # Small delay between events

    print("-" * 50)

    # Display alerts
    alerts = alert_processor.get_alerts()
    print(f"\nTotal alerts triggered: {len(alerts)}")

    # Show final event
    print(
        "\nNote: Run the framework to see enriched events with trade_value and enriched_at fields."
    )


if __name__ == "__main__":
    asyncio.run(main())
