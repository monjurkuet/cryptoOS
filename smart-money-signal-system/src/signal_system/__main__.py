"""Main entry point for Smart Money Signal System."""

import asyncio
from collections import deque
import signal as signal_mod
import sys
from typing import Any

import numpy as np
from pymongo import MongoClient
import structlog
import uvicorn

from signal_system.config import get_settings
from signal_system.event_subscriber import EventSubscriber
from signal_system.ml.regime_detection import MarketRegimeDetector
from signal_system.ml.feature_importance import FeatureImportanceAnalyzer
from signal_system.api.main import app
from signal_system.runtime import RuntimeComponents, build_runtime

logger = structlog.get_logger(__name__)

class SignalSystem:
    """Main signal system orchestrator."""

    def __init__(self) -> None:
        """Initialize the signal system."""
        settings = get_settings()
        self.runtime: RuntimeComponents = build_runtime(
            settings=settings,
            mongo_client_factory=MongoClient,
            event_subscriber_factory=EventSubscriber,
        )
        self.settings = self.runtime.settings
        self.mongo_client = self.runtime.mongo_client

        # Core components
        self.event_subscriber = self.runtime.event_subscriber
        self.signal_processor = self.runtime.signal_processor
        self.signal_store = self.runtime.signal_store
        self.weighting_engine = self.runtime.weighting_engine
        self.whale_detector = self.runtime.whale_detector

        # RL + dashboard components
        self.outcome_tracker = self.runtime.outcome_tracker
        self.outcome_store = self.runtime.outcome_store
        self.trace_store = self.runtime.trace_store
        self.param_event_store = self.runtime.param_event_store
        self.rl_param_server = self.runtime.rl_param_server
        self.event_processor = self.runtime.event_processor

        # ML components (optional, lazy-loaded)
        self._regime_detector: MarketRegimeDetector | None = None
        self._feature_analyzer: FeatureImportanceAnalyzer | None = None
        self._recent_ohlcv: deque[dict[str, float]] = deque(maxlen=240)

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
        if self.mongo_client is not None:
            self.mongo_client.close()
        logger.info("signal_system_stopped")

    def _register_handlers(self) -> None:
        """Register event handlers for different event types."""
        # Handle trader position updates via EventProcessor
        async def handle_trader_positions(event: dict) -> None:
            await self.event_processor.handle_position_event(event)

        # Handle leaderboard/scored traders via EventProcessor
        async def handle_scored_traders(event: dict) -> None:
            await self.event_processor.handle_scored_traders(event)

        # Handle OHLCV events for regime detection and derived mark prices
        async def handle_ohlcv(event: dict) -> None:
            await self._process_ohlcv(event)

        # Handle mark price for outcome tracking
        async def handle_mark_price(event: dict) -> None:
            await self._process_mark_price(event)

        self.event_subscriber.subscribe("trader_positions", handle_trader_positions)
        self.event_subscriber.subscribe("scored_traders", handle_scored_traders)
        self.event_subscriber.subscribe("ohlcv", handle_ohlcv)
        self.event_subscriber.subscribe("mark_price", handle_mark_price)

    async def _process_ohlcv(self, event: dict) -> None:
        """Process OHLCV events for regime detection and RL outcome resolution.

        Args:
            event: OHLCV event from market-scraper
        """
        try:
            payload = event.get("payload", {})
            symbol = payload.get("symbol", self.settings.symbol)

            # Only process OHLCV for our target symbol.
            if symbol != self.settings.symbol:
                return

            close_price = float(payload.get("close", 0) or 0)
            if close_price > 0:
                resolved = await self.event_processor.handle_price_update(close_price)
                if resolved:
                    logger.debug(
                        "outcomes_resolved_from_ohlcv_close",
                        count=len(resolved),
                    )

            candle = {
                "close": float(payload.get("close", 0) or 0),
                "high": float(payload.get("high", 0) or 0),
                "low": float(payload.get("low", 0) or 0),
                "volume": float(payload.get("volume", 0) or 0),
            }
            if candle["close"] <= 0:
                return
            self._recent_ohlcv.append(candle)

            if len(self._recent_ohlcv) < 20:
                return

            # Lazy-load regime detector
            if self._regime_detector is None:
                self._regime_detector = MarketRegimeDetector()
                # Try to load pre-trained model
                if not self._regime_detector.load_model():
                    logger.debug("regime_detector_no_model")
                    return

            # Prepare features from recent candles
            features = self._prepare_regime_features(list(self._recent_ohlcv))
            if features is not None:
                regime = self._regime_detector.detect(features)
                self.weighting_engine.set_regime(regime.name)

                logger.info(
                    "regime_detected",
                    regime=regime.name,
                    signal_multiplier=regime.signal_multiplier,
                )

        except Exception as e:
            logger.error("ohlcv_processing_error", error=str(e), exc_info=True)

    async def _process_mark_price(self, event: dict) -> None:
        """Process mark price event for outcome tracking.

        Args:
            event: Mark price event from market-scraper
        """
        try:
            payload = event.get("payload", {})
            mark_price = payload.get("mark_price", 0)
            if mark_price:
                resolved = await self.event_processor.handle_price_update(
                    float(mark_price)
                )
                if resolved:
                    logger.debug(
                        "outcomes_resolved_from_mark_price",
                        count=len(resolved),
                    )
        except Exception as e:
            logger.error("mark_price_processing_error", error=str(e), exc_info=True)

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
            "rl_param_server": self.rl_param_server.get_status(),
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

        signal_mod.signal(signal_mod.SIGINT, signal_handler)
        signal_mod.signal(signal_mod.SIGTERM, signal_handler)

        async def run():
            await system.start()
            # Keep running until stopped
            while system._running:
                await asyncio.sleep(1)

        asyncio.run(run())


if __name__ == "__main__":
    main()
