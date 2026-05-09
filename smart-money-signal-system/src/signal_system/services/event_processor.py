"""Shared event processing logic for standalone and API modes."""

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING, Any

import structlog

from signal_system.signal_generation.processor import SignalGenerationProcessor
from signal_system.signal_store import SignalStore
from signal_system.whale_alerts.detector import WhaleAlertDetector
from signal_system.config import SignalSystemSettings
from signal_system.utils.safe_convert import safe_float

if TYPE_CHECKING:
    from signal_system.rl.outcome_tracker import SignalOutcomeTracker
    from signal_system.rl.outcome_store import OutcomeStore
    from signal_system.dashboard.store import DecisionTraceStore

logger = structlog.get_logger(__name__)


class EventProcessor:
    """Shared event processing logic for standalone and API modes.

    Centralizes the handling of trader position events and scored traders
    events to ensure consistent behavior between the standalone processor
    and the API server modes.
    """

    def __init__(
        self,
        signal_processor: SignalGenerationProcessor,
        whale_detector: WhaleAlertDetector,
        signal_store: SignalStore | None,
        settings: SignalSystemSettings,
        outcome_tracker: SignalOutcomeTracker | None = None,
        outcome_store: OutcomeStore | None = None,
        trace_store: DecisionTraceStore | None = None,
    ) -> None:
        """Initialize the event processor.

        Args:
            signal_processor: Signal generation processor instance
            whale_detector: Whale alert detector instance
            signal_store: Optional signal store for persisting signals
            settings: Application settings
            outcome_tracker: Optional outcome tracker for RL reward computation
            outcome_store: Optional outcome store for MongoDB persistence
        """
        self._signal_processor = signal_processor
        self._whale_detector = whale_detector
        self._signal_store = signal_store
        self._settings = settings
        self._outcome_tracker = outcome_tracker
        self._outcome_store = outcome_store
        self._trace_store = trace_store

    async def handle_position_event(self, event: dict) -> None:
        """Process trader position event.

        This method handles:
        1. Updating whale detector with trader info
        2. Detecting whale alerts for BTC positions
        3. Generating trading signals
        4. Registering signals with outcome tracker (if configured)

        Args:
            event: Raw event from market-scraper
        """
        try:
            payload = event.get("payload", {})
            address = payload.get("address")

            if address:
                # Extract account value from position
                account_value = safe_float(payload.get("accountValue"), 0)
                positions = payload.get("positions", [])

                # Update whale detector with trader info
                self._whale_detector.update_trader_info(
                    address=address,
                    account_value=account_value,
                )

                # Check for whale alerts on target symbol positions
                for pos in positions:
                    pos_data = pos.get("position", pos)
                    if pos_data.get("coin") == self._settings.symbol:
                        szi = safe_float(pos_data.get("szi"), 0)
                        change = self._whale_detector.detect_position_change(
                            address=address,
                            coin=self._settings.symbol,
                            current_szi=szi,
                        )
                        if change:
                            alert = self._whale_detector.generate_alert(change)
                            if alert:
                                logger.info(
                                    "whale_alert_generated",
                                    priority=alert.priority.value,
                                    title=alert.title,
                                )
                                # Store alert if store available
                                if self._signal_store:
                                    await asyncio.to_thread(
                                        self._signal_store.store_alert,
                                        {
                                            "priority": alert.priority.value,
                                            "title": alert.title,
                                            "description": alert.description,
                                            "detected_at": alert.detected_at,
                                        },
                                    )

                # Generate signal
                signal = await self._signal_processor.process_position(event)
                latest_trace = self._signal_processor.get_latest_decision_trace()
                if inspect.isawaitable(latest_trace):
                    latest_trace = await latest_trace
                if latest_trace and self._trace_store is not None:
                    await asyncio.to_thread(self._trace_store.store_trace, latest_trace)
                if signal:
                    # Store the signal if store available
                    if self._signal_store:
                        await asyncio.to_thread(self._signal_store.store_signal, signal)
                    logger.info(
                        "signal_generated",
                        action=signal["action"],
                        confidence=signal["confidence"],
                        net_bias=signal["net_bias"],
                    )

                    # Register signal with outcome tracker for RL reward computation
                    if self._outcome_tracker is not None:
                        # Extract mark price from payload if available
                        mark_price = safe_float(payload.get("mark_price", 0), 0)
                        if mark_price == 0:
                            # Try from position data
                            for pos in positions:
                                pos_data = pos.get("position", pos)
                                if pos_data.get("coin") == self._settings.symbol:
                                    mark_price = safe_float(
                                        pos_data.get("markPx", 0), 0
                                    )
                                    break
                        self._outcome_tracker.register_signal(
                            signal_id=None,
                            action=signal["action"],
                            confidence=signal["confidence"],
                            price=mark_price,
                        )

        except Exception as e:
            logger.error("position_processing_error", error=str(e), exc_info=True)

    async def handle_price_update(self, price: float) -> list:
        """Feed a price update to the outcome tracker.

        Called when a mark_price event arrives. Resolves any pending
        signals whose evaluation horizons have expired.

        Args:
            price: Current mark price

        Returns:
            List of resolved SignalOutcome objects (empty if no tracker)
        """
        if self._outcome_tracker is None:
            return []

        resolved = self._outcome_tracker.update_price(price)

        # Persist resolved outcomes to MongoDB
        if resolved and self._outcome_store is not None:
            await asyncio.to_thread(self._outcome_store.store_batch, resolved)

        return resolved

    def get_outcome_stats(self) -> dict[str, Any]:
        """Get outcome tracker statistics.

        Returns:
            Tracker stats dict, or empty dict if no tracker configured
        """
        if self._outcome_tracker is None:
            return {}
        return self._outcome_tracker.get_stats()

    async def handle_scored_traders(self, event: dict) -> None:
        """Process scored traders event.

        Args:
            event: Event containing trader scores
        """
        try:
            payload = event.get("payload", {})
            traders = payload.get("traders", [])
            for trader in traders:
                address = str(trader.get("address", "")).lower()
                if not address:
                    continue
                account_value = safe_float(
                    trader.get("accountValue", trader.get("account_value", 0)),
                    0,
                )
                tags = [str(tag).lower() for tag in trader.get("tags", [])]
                if account_value >= 20_000_000 or "alpha_whale" in tags:
                    tier = "alpha_whale"
                elif account_value >= 10_000_000 or "whale" in tags:
                    tier = "whale"
                elif account_value >= 5_000_000 or "large" in tags:
                    tier = "large"
                elif account_value >= 1_000_000:
                    tier = "medium"
                else:
                    tier = "standard"
                self._whale_detector.update_trader_info(
                    address=address,
                    name=trader.get("displayName"),
                    tier=tier,
                    account_value=account_value,
                )
            await self._signal_processor.process_scored_traders(event)
            logger.debug("scored_traders_processed")
        except Exception as e:
            logger.error("scored_traders_error", error=str(e), exc_info=True)
