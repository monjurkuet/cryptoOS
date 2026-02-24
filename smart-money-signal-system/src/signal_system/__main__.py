"""Main entry point for Smart Money Signal System."""

import asyncio
import signal
import sys
from typing import Any

import numpy as np
import structlog
import uvicorn

from signal_system.config import get_settings
from signal_system.event_subscriber import EventSubscriber
from signal_system.signal_generation.processor import SignalGenerationProcessor
from signal_system.weighting_engine.engine import TraderWeightingEngine
from signal_system.whale_alerts.detector import WhaleAlertDetector
from signal_system.ml.regime_detection import MarketRegimeDetector
from signal_system.ml.feature_importance import FeatureImportanceAnalyzer
from signal_system.api.main import app

logger = structlog.get_logger(__name__)


class SignalSystem:
    """Main signal system orchestrator."""

    def __init__(self) -> None:
        """Initialize the signal system."""
        self.settings = get_settings()

        # Core components
        self.event_subscriber = EventSubscriber(self.settings.redis)
        self.signal_processor = SignalGenerationProcessor(symbol=self.settings.symbol)
        self.weighting_engine = TraderWeightingEngine()
        self.whale_detector = WhaleAlertDetector()

        # ML components (optional, lazy-loaded)
        self._regime_detector: MarketRegimeDetector | None = None
        self._feature_analyzer: FeatureImportanceAnalyzer | None = None

        self._running = False

    async def start(self) -> None:
        """Start the signal system."""
        logger.info(
            "signal_system_starting",
            symbol=self.settings.symbol,
            api_port=self.settings.api_port,
        )

        # Connect to Redis
        try:
            await self.event_subscriber.connect()
            logger.info("redis_connected")
        except Exception as e:
            logger.error("redis_connection_failed", error=str(e))
            raise

        # Register event handlers
        self._register_handlers()

        # Start event processing
        self._running = True
        logger.info("signal_system_started")

    async def stop(self) -> None:
        """Stop the signal system."""
        logger.info("signal_system_stopping")
        self._running = False
        await self.event_subscriber.disconnect()
        logger.info("signal_system_stopped")

    def _register_handlers(self) -> None:
        """Register event handlers for different event types."""
        # Handle trader position updates
        async def handle_trader_positions(event: dict) -> None:
            await self._process_position_event(event)

        # Handle leaderboard/scored traders
        async def handle_scored_traders(event: dict) -> None:
            await self._process_scored_traders(event)

        # Handle candles for regime detection
        async def handle_candles(event: dict) -> None:
            await self._process_candles(event)

        self.event_subscriber.subscribe("trader_positions", handle_trader_positions)
        self.event_subscriber.subscribe("scored_traders", handle_scored_traders)
        self.event_subscriber.subscribe("candles", handle_candles)

    async def _process_position_event(self, event: dict) -> None:
        """Process trader position event.

        Args:
            event: Raw event from market-scraper
        """
        try:
            # Update trader info for whale detection
            payload = event.get("payload", {})
            address = payload.get("address")

            if address:
                # Extract account value from position
                account_value = float(payload.get("accountValue", 0))
                positions = payload.get("positions", [])

                # Update whale detector with trader info
                self.whale_detector.update_trader_info(
                    address=address,
                    account_value=account_value,
                )

                # Check for whale alerts on BTC positions
                for pos in positions:
                    pos_data = pos.get("position", pos)
                    if pos_data.get("coin") == self.settings.symbol:
                        szi = float(pos_data.get("szi", 0))
                        change = self.whale_detector.detect_position_change(
                            address=address,
                            coin=self.settings.symbol,
                            current_szi=szi,
                        )
                        if change:
                            alert = self.whale_detector.generate_alert(change)
                            if alert:
                                logger.info(
                                    "whale_alert_generated",
                                    priority=alert.priority.value,
                                    title=alert.title,
                                )

            # Generate signal
            signal = await self.signal_processor.process_position(event)
            if signal:
                logger.info(
                    "signal_generated",
                    action=signal["action"],
                    confidence=signal["confidence"],
                    net_bias=signal["net_bias"],
                )

        except Exception as e:
            logger.error("position_processing_error", error=str(e), exc_info=True)

    async def _process_scored_traders(self, event: dict) -> None:
        """Process scored traders event.

        Args:
            event: Event containing trader scores
        """
        try:
            await self.signal_processor.process_scored_traders(event)
            logger.debug("scored_traders_processed")
        except Exception as e:
            logger.error("scored_traders_error", error=str(e), exc_info=True)

    async def _process_candles(self, event: dict) -> None:
        """Process candle data for regime detection.

        Args:
            event: Candle event from market-scraper
        """
        try:
            payload = event.get("payload", {})
            candles = payload.get("candles", [])
            symbol = payload.get("symbol", self.settings.symbol)

            # Only process candles for our target symbol
            if symbol != self.settings.symbol:
                return

            if not candles:
                return

            # Lazy-load regime detector
            if self._regime_detector is None:
                self._regime_detector = MarketRegimeDetector()
                # Try to load pre-trained model
                if not self._regime_detector.load_model():
                    logger.debug("regime_detector_no_model")
                    return

            # Prepare features from recent candles
            features = self._prepare_regime_features(candles)
            if features is not None:
                regime = self._regime_detector.detect(features)
                self.weighting_engine.set_regime(regime.name)

                logger.info(
                    "regime_detected",
                    regime=regime.name,
                    signal_multiplier=regime.signal_multiplier,
                )

        except Exception as e:
            logger.error("candles_processing_error", error=str(e), exc_info=True)

    def _prepare_regime_features(self, candles: list[dict]) -> np.ndarray | None:
        """Prepare feature vector for regime detection from candles.

        Args:
            candles: List of OHLCV candle data

        Returns:
            Feature array or None if insufficient data
        """
        if len(candles) < 20:
            return None

        # Take last 20 candles for feature calculation
        recent = candles[-20:]

        # Extract OHLCV data
        closes = np.array([c.get("close", 0) for c in recent])
        highs = np.array([c.get("high", 0) for c in recent])
        lows = np.array([c.get("low", 0) for c in recent])
        volumes = np.array([c.get("volume", 0) for c in recent])

        if closes.size == 0 or closes[0] == 0:
            return None

        # Calculate features
        returns = np.diff(closes) / closes[:-1]

        # Feature order must match training data order
        features = np.array([
            # Volatility features
            float(np.std(returns) * np.sqrt(365)) if len(returns) > 0 else 0,
            float(np.mean((highs - lows) / closes)),
            # Trend features
            float((closes[-1] - closes[0]) / closes[0]) if closes[0] != 0 else 0,
            float((closes[-1] - np.min(lows)) / (np.max(highs) - np.min(lows)))
            if (np.max(highs) - np.min(lows)) != 0 else 0.5,
            # Volume features
            float(volumes[-5:].mean() / volumes[:5].mean())
            if volumes[:5].mean() != 0 else 1.0,
            float(np.std(volumes) / np.mean(volumes))
            if np.mean(volumes) != 0 else 0,
            # Price action
            float(np.mean((highs - np.maximum(closes, np.roll(closes, 1))) / (highs - lows + 1e-10))),
            float(np.mean((np.minimum(closes, np.roll(closes, 1)) - lows) / (highs - lows + 1e-10))),
        ])

        return features

    def get_stats(self) -> dict[str, Any]:
        """Get system statistics.

        Returns:
            Dict with all component stats
        """
        return {
            "running": self._running,
            "event_subscriber": self.event_subscriber.get_stats(),
            "signal_processor": self.signal_processor.get_stats(),
            "weighting_engine": self.weighting_engine.get_stats(),
            "whale_detector": self.whale_detector.get_stats(),
        }


def run_server() -> None:
    """Run the API server."""
    settings = get_settings()
    uvicorn.run(
        "signal_system.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        # Run API server mode
        run_server()
    else:
        # Run standalone mode (event processor only)
        system = SignalSystem()

        def signal_handler(sig, frame):
            logger.info("shutdown_signal_received")
            asyncio.create_task(system.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        async def run():
            await system.start()
            # Keep running until stopped
            while system._running:
                await asyncio.sleep(1)

        asyncio.run(run())


if __name__ == "__main__":
    main()
