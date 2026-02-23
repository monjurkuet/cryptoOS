# src/market_scraper/core/events.py

"""Event models for the Market Scraper Framework."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class EventType(StrEnum):
    """Standard event types."""

    # Market data events
    TRADE = "trade"
    TICKER = "ticker"
    ORDER_BOOK = "order_book"
    OHLCV = "ohlcv"

    # System events
    CONNECTOR_STATUS = "connector_status"
    HEARTBEAT = "heartbeat"
    ERROR = "error"

    # Custom events
    CUSTOM = "custom"


class MarketDataPayload(BaseModel):
    """Standard market data payload."""

    model_config = ConfigDict(extra="allow")

    symbol: str = Field(..., description="Trading pair/symbol")
    price: float | None = Field(None, description="Current price")
    volume: float | None = Field(None, description="Traded volume")
    timestamp: datetime = Field(..., description="Event timestamp")

    # Optional fields for different data types
    bid: float | None = Field(None, description="Best bid price")
    ask: float | None = Field(None, description="Best ask price")
    bid_volume: float | None = Field(None, description="Bid volume")
    ask_volume: float | None = Field(None, description="Ask volume")

    # OHLCV fields
    open: float | None = Field(None, description="Open price")
    high: float | None = Field(None, description="High price")
    low: float | None = Field(None, description="Low price")
    close: float | None = Field(None, description="Close price")


class StandardEvent(BaseModel):
    """Standardized event structure for all system events.

    All events flowing through the system must conform to this structure.
    This enables loose coupling between components.
    """

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )

    # Required fields
    event_id: str = Field(
        ...,
        description="Unique event identifier (UUID)",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    event_type: EventType | str = Field(
        ...,
        description="Event type classification",
    )
    timestamp: datetime = Field(
        ...,
        description="Event occurrence timestamp (UTC)",
    )
    source: str = Field(
        ...,
        description="Event source (connector name)",
        examples=["hyperliquid", "cbbi"],
    )

    # Payload
    payload: MarketDataPayload | dict[str, Any] = Field(
        ...,
        description="Event payload data",
    )

    # Metadata
    correlation_id: str | None = Field(
        None,
        description="Correlation ID for tracing",
    )
    parent_event_id: str | None = Field(
        None,
        description="Parent event ID for event chains",
    )
    priority: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Event priority (1-10, lower is higher priority)",
    )

    # System fields (auto-populated)
    processed_at: datetime | None = Field(
        None,
        description="Timestamp when event was processed",
    )
    processing_time_ms: float | None = Field(
        None,
        description="Processing time in milliseconds",
    )

    def mark_processed(self) -> None:
        """Mark event as processed and calculate processing time."""
        self.processed_at = datetime.now(UTC)
        if self.processed_at and self.timestamp:
            delta = self.processed_at - self.timestamp
            self.processing_time_ms = delta.total_seconds() * 1000

    @classmethod
    def create(
        cls,
        event_type: EventType | str,
        source: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
        priority: int = 5,
        timestamp: datetime | None = None,
    ) -> "StandardEvent":
        """Factory method to create a new event.

        Args:
            event_type: Type of event
            source: Event source name
            payload: Event data
            correlation_id: Optional correlation ID
            priority: Event priority (1-10)
            timestamp: Optional timestamp (defaults to current UTC time)

        Returns:
            New StandardEvent instance
        """
        return cls(
            event_id=str(uuid4()),
            event_type=event_type,
            timestamp=timestamp or datetime.now(UTC),
            source=source,
            payload=payload,
            correlation_id=correlation_id or str(uuid4()),
            priority=priority,
            parent_event_id=None,
            processed_at=None,
            processing_time_ms=None,
        )
