# src/market_scraper/processors/candle_processor.py

"""Candle processor for aggregating trades into OHLCV candles."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import structlog

from market_scraper.core.events import EventType, MarketDataPayload, StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.processors.base import Processor

logger = structlog.get_logger(__name__)


class CandleProcessor(Processor):
    """Aggregates trade events into OHLCV candles.

    Supports multiple timeframes and uses a sliding window approach for
    real-time aggregation. Partial candles are stored in memory and
    flushed when complete.

    Attributes:
        _timeframes: List of timeframe intervals in minutes
        _candles: Storage for partial candles per symbol/timeframe
        _trades: Buffer of recent trades for aggregation
    """

    def __init__(
        self,
        event_bus: EventBus,
        timeframes: list[int] | None = None,
    ) -> None:
        """Initialize the candle processor.

        Args:
            event_bus: Event bus instance for publishing candle events
            timeframes: List of timeframe intervals in minutes (default: [1, 5, 15])
        """
        super().__init__(event_bus)
        self._timeframes = timeframes or [1, 5, 15]
        # Structure: {symbol: {timeframe: {timestamp: candle_data}}}
        self._candles: dict[str, dict[int, dict[datetime, dict[str, Any]]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        # Buffer of trades per symbol
        self._trades: dict[str, list[dict[str, Any]]] = defaultdict(list)

    async def process(self, event: StandardEvent) -> StandardEvent | None:
        """Accumulate trade events for candle aggregation.

        Args:
            event: Trade event to process

        Returns:
            The original event, or None if processing failed
        """
        try:
            # Only process trade events
            if event.event_type != EventType.TRADE:
                return event

            # Extract payload
            payload = event.payload
            if isinstance(payload, dict):
                payload = MarketDataPayload(**payload)
            elif not isinstance(payload, MarketDataPayload):
                return None

            symbol = payload.symbol
            if not symbol or payload.price is None:
                return None

            # Store trade for aggregation
            trade = {
                "timestamp": payload.timestamp,
                "price": payload.price,
                "volume": payload.volume or 0.0,
            }
            self._trades[symbol].append(trade)

            # Update candles for all timeframes
            for timeframe in self._timeframes:
                self._update_candle(symbol, timeframe, trade)

            return event

        except Exception as e:
            logger.error(
                "Failed to process trade for candle aggregation",
                event_id=event.event_id,
                error=str(e),
            )
            return None

    def _update_candle(self, symbol: str, timeframe: int, trade: dict[str, Any]) -> None:
        """Update candle data with a new trade.

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe in minutes
            trade: Trade data with price, volume, and timestamp
        """
        # Calculate candle timestamp (floor to timeframe boundary)
        trade_ts = trade["timestamp"]
        if isinstance(trade_ts, str):
            trade_ts = datetime.fromisoformat(trade_ts.replace("Z", "+00:00"))

        minutes = trade_ts.minute
        candle_minute = (minutes // timeframe) * timeframe
        candle_ts = trade_ts.replace(minute=candle_minute, second=0, microsecond=0)

        candles_for_tf = self._candles[symbol][timeframe]

        if candle_ts not in candles_for_tf:
            # Start new candle
            candles_for_tf[candle_ts] = {
                "open": trade["price"],
                "high": trade["price"],
                "low": trade["price"],
                "close": trade["price"],
                "volume": trade["volume"],
                "timestamp": candle_ts,
                "symbol": symbol,
                "timeframe": timeframe,
            }
        else:
            # Update existing candle
            candle = candles_for_tf[candle_ts]
            candle["high"] = max(candle["high"], trade["price"])
            candle["low"] = min(candle["low"], trade["price"])
            candle["close"] = trade["price"]
            candle["volume"] += trade["volume"]

    def _aggregate_candles(
        self,
        trades: list[dict[str, Any]],
        timeframe: int,
    ) -> list[dict[str, Any]]:
        """Group trades into OHLCV candles.

        Args:
            trades: List of trade dictionaries
            timeframe: Timeframe in minutes

        Returns:
            List of candle dictionaries
        """
        if not trades:
            return []

        candles: dict[datetime, dict[str, Any]] = {}

        for trade in trades:
            ts = trade["timestamp"]
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))

            # Calculate candle timestamp
            minutes = ts.minute
            candle_minute = (minutes // timeframe) * timeframe
            candle_ts = ts.replace(minute=candle_minute, second=0, microsecond=0)

            if candle_ts not in candles:
                candles[candle_ts] = {
                    "open": trade["price"],
                    "high": trade["price"],
                    "low": trade["price"],
                    "close": trade["price"],
                    "volume": trade["volume"],
                    "timestamp": candle_ts,
                    "timeframe": timeframe,
                }
            else:
                candle = candles[candle_ts]
                candle["high"] = max(candle["high"], trade["price"])
                candle["low"] = min(candle["low"], trade["price"])
                candle["close"] = trade["price"]
                candle["volume"] += trade["volume"]

        return list(candles.values())

    async def flush(self) -> list[StandardEvent]:
        """Emit completed candles as events.

        Candles that have passed their timeframe window are emitted
        and removed from memory.

        Returns:
            List of candle events that were published
        """
        completed_events = []
        now = datetime.utcnow()

        for symbol in list(self._candles.keys()):
            for timeframe in list(self._candles[symbol].keys()):
                candles_for_tf = self._candles[symbol][timeframe]

                for candle_ts in list(candles_for_tf.keys()):
                    candle = candles_for_tf[candle_ts]

                    # Check if candle is complete (current time > candle end)
                    candle_end = candle_ts + timedelta(minutes=timeframe)
                    if now >= candle_end:
                        # Create OHLCV event
                        payload = MarketDataPayload(
                            symbol=symbol,
                            open=candle["open"],
                            high=candle["high"],
                            low=candle["low"],
                            close=candle["close"],
                            volume=candle["volume"],
                            timestamp=candle_ts,
                        )

                        event = StandardEvent.create(
                            event_type=EventType.OHLCV,
                            source="candle_processor",
                            payload=payload.model_dump(),
                        )

                        await self._event_bus.publish(event)
                        completed_events.append(event)

                        # Remove completed candle
                        del candles_for_tf[candle_ts]

                # Clean up empty timeframes
                if not candles_for_tf:
                    del self._candles[symbol][timeframe]

            # Clean up empty symbols
            if not self._candles[symbol]:
                del self._candles[symbol]

        # Clear old trades (keep last 1000 per symbol)
        for symbol in self._trades:
            if len(self._trades[symbol]) > 1000:
                self._trades[symbol] = self._trades[symbol][-1000:]

        return completed_events

    def get_candles(
        self,
        symbol: str,
        timeframe: int,
    ) -> list[dict[str, Any]]:
        """Get current candles for a symbol and timeframe.

        Args:
            symbol: Trading pair symbol
            timeframe: Timeframe in minutes

        Returns:
            List of candle dictionaries
        """
        if symbol in self._candles and timeframe in self._candles[symbol]:
            return list(self._candles[symbol][timeframe].values())
        return []

    async def stop(self) -> None:
        """Stop the processor and flush remaining candles."""
        await self.flush()
        self._running = False
