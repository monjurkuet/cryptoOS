"""Shared event processing logic for standalone and API modes."""

from typing import Any

import structlog

from signal_system.signal_generation.processor import SignalGenerationProcessor
from signal_system.signal_store import SignalStore
from signal_system.whale_alerts.detector import WhaleAlertDetector
from signal_system.config import SignalSystemSettings
from signal_system.utils.safe_convert import safe_float

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
    ) -> None:
        """Initialize the event processor.

        Args:
            signal_processor: Signal generation processor instance
            whale_detector: Whale alert detector instance
            signal_store: Optional signal store for persisting signals
            settings: Application settings
        """
        self._signal_processor = signal_processor
        self._whale_detector = whale_detector
        self._signal_store = signal_store
        self._settings = settings

    async def handle_position_event(self, event: dict) -> None:
        """Process trader position event.

        This method handles:
        1. Updating whale detector with trader info
        2. Detecting whale alerts for BTC positions
        3. Generating trading signals

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
                                    self._signal_store.store_alert({
                                        "priority": alert.priority.value,
                                        "title": alert.title,
                                        "description": alert.description,
                                        "detected_at": alert.detected_at,
                                    })

            # Generate signal
            signal = await self._signal_processor.process_position(event)
            if signal:
                # Store the signal if store available
                if self._signal_store:
                    self._signal_store.store_signal(signal)
                logger.info(
                    "signal_generated",
                    action=signal["action"],
                    confidence=signal["confidence"],
                    net_bias=signal["net_bias"],
                )

        except Exception as e:
            logger.error("position_processing_error", error=str(e), exc_info=True)

    async def handle_scored_traders(self, event: dict) -> None:
        """Process scored traders event.

        Args:
            event: Event containing trader scores
        """
        try:
            await self._signal_processor.process_scored_traders(event)
            logger.debug("scored_traders_processed")
        except Exception as e:
            logger.error("scored_traders_error", error=str(e), exc_info=True)
