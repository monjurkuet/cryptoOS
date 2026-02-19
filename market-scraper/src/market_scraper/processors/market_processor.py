# src/market_scraper/processors/market_processor.py

"""Market data processor for normalizing and validating market events."""

from collections.abc import Callable

import structlog

from market_scraper.core.events import EventType, MarketDataPayload, StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.processors.base import Processor

logger = structlog.get_logger(__name__)


class MarketDataProcessor(Processor):
    """Processes and normalizes incoming market data events.

    Responsibilities:
    - Normalize symbol formats across sources
    - Validate price/volume data
    - Enrich events with metadata
    - Filter invalid data

    Supports different symbol formats from various sources like
    Hyperliquid (BTC@USD -> BTC-USD) and CBBI.
    """

    def __init__(self, event_bus: EventBus) -> None:
        """Initialize the market data processor.

        Args:
            event_bus: Event bus instance for publishing normalized events
        """
        super().__init__(event_bus)
        self._symbol_normalizers: dict[str, Callable[[str], str]] = {
            "hyperliquid": self._normalize_hyperliquid_symbol,
            "cbbi": self._normalize_cbbi_symbol,
        }

    async def process(self, event: StandardEvent) -> StandardEvent | None:
        """Process and normalize a market data event.

        Args:
            event: Raw event from connector

        Returns:
            Normalized event or None if invalid
        """
        try:
            # Skip non-market events
            if event.event_type not in (
                EventType.TRADE,
                EventType.TICKER,
                EventType.OHLCV,
            ):
                return event

            # Get normalizer for source
            normalizer = self._symbol_normalizers.get(
                event.source,
                self._default_normalizer,
            )

            # Normalize payload
            payload = event.payload
            if isinstance(payload, dict):
                payload = MarketDataPayload(**payload)
            elif not isinstance(payload, MarketDataPayload):
                logger.warning(
                    "Invalid payload type",
                    event_id=event.event_id,
                    payload_type=type(payload).__name__,
                )
                return None

            # Normalize symbol
            normalized_symbol = normalizer(payload.symbol)

            # Validate data
            if not self._validate_payload(payload):
                logger.warning(
                    "Invalid market data",
                    event_id=event.event_id,
                    symbol=payload.symbol,
                    source=event.source,
                )
                return None

            # Create normalized payload
            normalized_payload = MarketDataPayload(
                symbol=normalized_symbol,
                price=payload.price,
                volume=payload.volume,
                timestamp=payload.timestamp,
                bid=payload.bid,
                ask=payload.ask,
                bid_volume=payload.bid_volume,
                ask_volume=payload.ask_volume,
                open=payload.open,
                high=payload.high,
                low=payload.low,
                close=payload.close,
            )

            # Create normalized event
            normalized_event = StandardEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                timestamp=event.timestamp,
                source=event.source,
                payload=normalized_payload,
                correlation_id=event.correlation_id,
                parent_event_id=event.event_id,
                priority=event.priority,
            )

            # Publish normalized event
            await self._event_bus.publish(normalized_event)

            return normalized_event

        except Exception as e:
            logger.error(
                "Failed to process market data",
                event_id=event.event_id,
                error=str(e),
            )
            return None

    def _normalize_hyperliquid_symbol(self, symbol: str) -> str:
        """Normalize Hyperliquid symbol format.

        Hyperliquid uses @ notation (e.g., BTC@USD) which needs to be
        converted to standard format (BTC-USD).

        Args:
            symbol: Raw symbol from Hyperliquid

        Returns:
            Normalized symbol in BTC-USD format
        """
        symbol = symbol.replace("@", "-")
        if "-" not in symbol:
            symbol = f"{symbol}-USD"
        return symbol.upper()

    def _normalize_cbbi_symbol(self, symbol: str) -> str:
        """Normalize CBBI symbol format.

        CBBI already uses standard format, so we just uppercase it.

        Args:
            symbol: Raw symbol from CBBI

        Returns:
            Normalized symbol
        """
        return symbol.upper()

    def _default_normalizer(self, symbol: str) -> str:
        """Default symbol normalizer for unknown sources.

        Args:
            symbol: Raw symbol

        Returns:
            Uppercase symbol
        """
        return symbol.upper()

    def _validate_payload(self, payload: MarketDataPayload) -> bool:
        """Validate market data payload.

        Checks for:
        - Required fields (symbol must be present)
        - Valid price (> 0 and < 1e12)
        - Valid volume (>= 0)
        - OHLCV consistency (high >= low)

        Args:
            payload: Market data payload to validate

        Returns:
            True if payload is valid, False otherwise
        """
        # Check required fields
        if not payload.symbol:
            return False

        # Validate price (if present)
        if payload.price is not None and (payload.price <= 0 or payload.price > 1e12):
            return False

        # Validate volume (if present)
        if payload.volume is not None and payload.volume < 0:
            return False

        # Validate OHLCV consistency
        return not (
            payload.high is not None and payload.low is not None and payload.high < payload.low
        )
