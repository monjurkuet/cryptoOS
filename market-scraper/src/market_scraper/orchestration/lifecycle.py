# src/market_scraper/orchestration/lifecycle.py

"""Lifecycle manager for orchestrating all system components."""

import asyncio
from datetime import datetime
from typing import Any

import structlog

from market_scraper.config.traders_config import load_traders_config
from market_scraper.connectors.hyperliquid.collectors.manager import CollectorManager
from market_scraper.connectors.hyperliquid.collectors.leaderboard import LeaderboardCollector
from market_scraper.core.config import Settings, get_settings
from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.event_bus.memory_bus import MemoryEventBus
from market_scraper.event_bus.redis_bus import RedisEventBus
from market_scraper.processors.position_inference import PositionInferenceProcessor
from market_scraper.processors.trader_scoring import TraderScoringProcessor
from market_scraper.processors.signal_generation import SignalGenerationProcessor
from market_scraper.storage.base import DataRepository
from market_scraper.storage.memory_repository import MemoryRepository
from market_scraper.storage.mongo_repository import MongoRepository

logger = structlog.get_logger(__name__)


class LifecycleManager:
    """Manages application lifecycle and component coordination.

    Components managed:
    1. Event Bus (Memory or Redis)
    2. Repository (Memory or MongoDB)
    3. Collector Manager (Hyperliquid WebSocket for market data)
    4. Leaderboard Collector (periodic leaderboard fetching)
    5. Processors (position inference, trader scoring, signal generation)
    6. Storage Processor (saves events to repository)

    Lifecycle:
    1. startup() - Initialize and connect all components
    2. shutdown() - Gracefully disconnect all components
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the lifecycle manager.

        Args:
            settings: Application settings (defaults to get_settings())
        """
        self._settings = settings or get_settings()
        self._started = False
        self._startup_complete = False
        self._startup_error: Exception | None = None

        # Core components
        self._event_bus: EventBus | None = None
        self._repository: DataRepository | None = None
        self._collector_manager: CollectorManager | None = None
        self._leaderboard_collector: LeaderboardCollector | None = None

        # Processors
        self._processors: list[Any] = []

    @property
    def is_ready(self) -> bool:
        """Check if startup is complete and system is ready."""
        return self._startup_complete and self._started

    @property
    def startup_error(self) -> Exception | None:
        """Get any error that occurred during startup."""
        return self._startup_error

    async def startup(self) -> None:
        """Initialize all components on startup.

        Order:
        1. Event Bus
        2. Repository
        3. Subscribe storage handler to event bus
        4. Initialize processors (subscribe to event bus)
        5. Collector Manager (market data)
        6. Leaderboard Collector
        """
        if self._started:
            logger.warning("lifecycle_already_started")
            return

        logger.info(
            "lifecycle_startup_begin",
            symbol=self._settings.hyperliquid.symbol,
        )

        try:
            # 1. Initialize Event Bus
            await self._init_event_bus()
            logger.info("event_bus_initialized", type=type(self._event_bus).__name__)

            # 2. Initialize Repository
            await self._init_repository()
            logger.info("repository_initialized", type=type(self._repository).__name__)

            # 3. Subscribe storage handler
            await self._subscribe_storage_handler()
            logger.info("storage_handler_subscribed")

            # 3.5 Subscribe candle storage handler
            await self._subscribe_candle_handler()
            logger.info("candle_handler_subscribed")

            # 4. Initialize processors
            await self._init_processors()
            logger.info("processors_initialized", count=len(self._processors))

            # 5. Initialize Collector Manager (market data)
            await self._init_collector_manager()
            logger.info("collector_manager_initialized")

            # 6. Initialize Leaderboard Collector
            await self._init_leaderboard_collector()
            logger.info("leaderboard_collector_initialized")

            self._started = True
            self._startup_complete = True
            logger.info("lifecycle_startup_complete")

        except Exception as e:
            logger.error("lifecycle_startup_failed", error=str(e))
            self._startup_error = e
            await self.shutdown()
            raise

    async def startup_background(self) -> None:
        """Run startup in background without blocking.

        This allows the HTTP server to start immediately while
        components initialize in the background.

        Should be called via asyncio.create_task() to run concurrently.
        """
        try:
            await self.startup()
        except Exception as e:
            # Error is already logged and stored in _startup_error
            logger.error("background_startup_failed", error=str(e))

    async def wait_ready(self, timeout: float = 30.0) -> bool:
        """Wait for startup to complete.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            True if ready, False if timeout or error.
        """
        import asyncio

        start_time = asyncio.get_event_loop().time()
        while not self._startup_complete:
            if self._startup_error:
                return False
            if asyncio.get_event_loop().time() - start_time > timeout:
                return False
            await asyncio.sleep(0.1)
        return True

    async def shutdown(self) -> None:
        """Graceful shutdown of all components.

        Order (reverse of startup):
        1. Leaderboard Collector
        2. Collector Manager
        3. Processors
        4. Repository
        5. Event Bus
        """
        logger.info("lifecycle_shutdown_begin")

        # Stop leaderboard collector
        if self._leaderboard_collector:
            try:
                await self._leaderboard_collector.stop()
            except Exception as e:
                logger.error("leaderboard_stop_error", error=str(e))
            self._leaderboard_collector = None

        # Stop collector manager
        if self._collector_manager:
            try:
                await self._collector_manager.stop()
            except Exception as e:
                logger.error("collector_stop_error", error=str(e))
            self._collector_manager = None

        # Stop processors
        for processor in self._processors:
            try:
                await processor.stop()
            except Exception as e:
                logger.error("processor_stop_error", error=str(e))
        self._processors.clear()

        # Disconnect repository
        if self._repository:
            try:
                await self._repository.disconnect()
            except Exception as e:
                logger.error("repository_disconnect_error", error=str(e))
            self._repository = None

        # Disconnect event bus
        if self._event_bus:
            try:
                await self._event_bus.disconnect()
            except Exception as e:
                logger.error("event_bus_disconnect_error", error=str(e))
            self._event_bus = None

        self._started = False
        logger.info("lifecycle_shutdown_complete")

    async def _init_event_bus(self) -> None:
        """Initialize event bus based on configuration."""
        redis_url = self._settings.redis.url

        if redis_url and redis_url != "redis://localhost:6379":
            # Use Redis event bus if URL is configured
            try:
                self._event_bus = RedisEventBus(redis_url=redis_url)
                await self._event_bus.connect()
                return
            except Exception as e:
                logger.warning(
                    "redis_connection_failed_using_memory",
                    error=str(e),
                )

        # Default to memory event bus
        self._event_bus = MemoryEventBus()
        await self._event_bus.connect()

    async def _init_repository(self) -> None:
        """Initialize repository based on configuration."""
        mongo_url = self._settings.mongo.url

        if mongo_url and mongo_url != "mongodb://localhost:27017":
            # Use MongoDB repository if URL is configured
            try:
                self._repository = MongoRepository(
                    connection_string=mongo_url,
                    database_name=self._settings.mongo.database,
                )
                await self._repository.connect()
                return
            except Exception as e:
                logger.warning(
                    "mongo_connection_failed_using_memory",
                    error=str(e),
                )

        # Default to memory repository
        self._repository = MemoryRepository()
        await self._repository.connect()

    async def _subscribe_storage_handler(self) -> None:
        """Subscribe storage handler to all events."""
        if not self._event_bus:
            raise RuntimeError("Event bus not initialized")

        # Events that are too large to store (skip storage)
        SKIP_STORAGE_EVENTS = {"leaderboard"}  # Leaderboard is ~30MB, exceeds MongoDB 16MB limit

        async def storage_handler(event: StandardEvent) -> None:
            """Handle events by storing them in the repository."""
            # Skip events that are too large
            if event.event_type in SKIP_STORAGE_EVENTS:
                return

            if self._repository:
                try:
                    await self._repository.store(event)
                except Exception as e:
                    logger.error(
                        "storage_handler_error",
                        event_id=event.event_id,
                        error=str(e),
                    )

        # Subscribe to all events
        await self._event_bus.subscribe("*", storage_handler)

    async def _subscribe_candle_handler(self) -> None:
        """Subscribe candle storage handler to OHLCV events."""
        if not self._event_bus:
            raise RuntimeError("Event bus not initialized")

        async def candle_handler(event: StandardEvent) -> None:
            """Handle OHLCV events by storing them in candle collections."""
            if event.event_type != "ohlcv":
                return

            if not self._repository:
                return

            try:
                payload = event.payload
                if not isinstance(payload, dict):
                    return

                symbol = payload.get("symbol", "").upper()
                interval = payload.get("interval", "")
                if not symbol or not interval:
                    return

                # Create candle document
                from market_scraper.storage.models import Candle
                from datetime import datetime

                timestamp = payload.get("timestamp")
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                elif not isinstance(timestamp, datetime):
                    return

                candle = Candle(
                    t=timestamp,
                    o=float(payload.get("open", 0)),
                    h=float(payload.get("high", 0)),
                    l=float(payload.get("low", 0)),
                    c=float(payload.get("close", 0)),
                    v=float(payload.get("volume", 0)),
                )

                # Store to the specific candle collection
                if hasattr(self._repository, "store_candle"):
                    await self._repository.store_candle(candle, symbol, interval)

            except Exception as e:
                logger.error(
                    "candle_handler_error",
                    event_id=event.event_id,
                    error=str(e),
                )

        await self._event_bus.subscribe("ohlcv", candle_handler)

    async def _init_processors(self) -> None:
        """Initialize event processors."""
        if not self._event_bus:
            raise RuntimeError("Event bus not initialized")

        config = self._settings.hyperliquid

        # Position Inference Processor
        position_inference = PositionInferenceProcessor(
            event_bus=self._event_bus,
            config=config,
        )
        await position_inference.start()
        self._processors.append(position_inference)

        # Subscribe processor to leaderboard events
        async def position_inference_handler(event: StandardEvent) -> None:
            if event.event_type == "leaderboard":
                result = await position_inference.process(event)
                if result and self._event_bus:
                    await self._event_bus.publish(result)

        await self._event_bus.subscribe("leaderboard", position_inference_handler)

        # Trader Scoring Processor
        trader_scoring = TraderScoringProcessor(
            event_bus=self._event_bus,
            config=config,
            min_score=50.0,
            max_count=500,
        )
        await trader_scoring.start()
        self._processors.append(trader_scoring)

        # Subscribe processor to leaderboard events
        async def trader_scoring_handler(event: StandardEvent) -> None:
            if event.event_type == "leaderboard":
                result = await trader_scoring.process(event)
                if result and self._event_bus:
                    await self._event_bus.publish(result)

        await self._event_bus.subscribe("leaderboard", trader_scoring_handler)

        # Signal Generation Processor
        signal_generation = SignalGenerationProcessor(
            event_bus=self._event_bus,
            config=config,
        )
        await signal_generation.start()
        self._processors.append(signal_generation)

        # Subscribe processor to position and score events
        async def signal_handler(event: StandardEvent) -> None:
            if event.event_type in ["trader_positions", "scored_traders", "mark_price"]:
                result = await signal_generation.process(event)
                if result and self._event_bus:
                    await self._event_bus.publish(result)

        await self._event_bus.subscribe("trader_positions", signal_handler)
        await self._event_bus.subscribe("scored_traders", signal_handler)
        await self._event_bus.subscribe("mark_price", signal_handler)

    async def _init_collector_manager(self) -> None:
        """Initialize the Hyperliquid collector manager."""
        if not self._event_bus:
            raise RuntimeError("Event bus not initialized")

        if not self._settings.hyperliquid.enabled:
            logger.info("hyperliquid_collector_disabled")
            return

        self._collector_manager = CollectorManager(
            event_bus=self._event_bus,
            config=self._settings.hyperliquid,
            collectors=["trades", "orderbook", "candles", "all_mids"],
        )

        await self._collector_manager.start()

    async def _init_leaderboard_collector(self) -> None:
        """Initialize the leaderboard collector."""
        if not self._event_bus:
            raise RuntimeError("Event bus not initialized")

        if not self._settings.hyperliquid.enabled:
            logger.info("leaderboard_collector_disabled")
            return

        # Load trader configuration from YAML
        traders_config = load_traders_config()

        # Get database reference for direct storage
        db = None
        if hasattr(self._repository, "_db"):
            db = self._repository._db

        self._leaderboard_collector = LeaderboardCollector(
            event_bus=self._event_bus,
            config=self._settings.hyperliquid,
            db=db,
            traders_config=traders_config,
        )

        await self._leaderboard_collector.start()

    # --- Public API Methods ---

    async def health_check(self) -> dict[str, bool]:
        """Perform basic health check.

        Returns:
            Dictionary of component health status
        """
        return {
            "api": True,
            "event_bus": self._event_bus is not None,
            "repository": self._repository is not None,
            "collectors": self._collector_manager is not None and self._collector_manager.is_running,
            "leaderboard": self._leaderboard_collector is not None and self._leaderboard_collector._running,
            "processors": len(self._processors) > 0,
        }

    async def get_detailed_health(self) -> dict[str, dict[str, Any]]:
        """Get detailed health status of all components.

        Returns:
            Dictionary with detailed health info per component
        """
        result: dict[str, dict[str, Any]] = {
            "api": {"status": "healthy"},
            "event_bus": {
                "status": "healthy" if self._event_bus else "not_initialized",
                "metrics": self._event_bus.get_metrics() if self._event_bus else {},
            },
            "repository": {
                "status": "healthy" if self._repository else "not_initialized",
            },
            "collectors": {
                "status": "healthy" if self._collector_manager else "not_initialized",
            },
            "leaderboard": {
                "status": "healthy" if self._leaderboard_collector else "not_initialized",
            },
            "processors": {
                "status": "healthy" if self._processors else "not_initialized",
                "count": len(self._processors),
            },
        }

        if self._repository:
            try:
                repo_health = await self._repository.health_check()
                result["repository"].update(repo_health)
            except Exception as e:
                result["repository"]["error"] = str(e)

        if self._collector_manager:
            result["collectors"].update(self._collector_manager.get_status())

        if self._leaderboard_collector:
            result["leaderboard"].update(self._leaderboard_collector.get_stats())

        return result

    async def get_markets(self) -> list[dict[str, Any]]:
        """Get list of available markets.

        Returns:
            List with the configured symbol
        """
        symbol = self._settings.hyperliquid.symbol
        return [{"symbol": symbol, "status": "active"}]

    async def get_market_data(self, symbol: str) -> dict[str, Any] | None:
        """Get latest market data for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            Latest data or None if not available
        """
        if not self._repository:
            return None

        try:
            # Get latest candle (use 1h as default for "current price")
            latest_candle = await self._repository.get_latest_candle(
                symbol=symbol,
                interval="1h",
            )

            return {
                "symbol": symbol,
                "latest_candle": latest_candle,
            }
        except Exception as e:
            logger.error("get_market_data_error", error=str(e))
            return None

    async def get_market_history(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get historical market data.

        Args:
            symbol: Trading symbol
            timeframe: Data timeframe (e.g., "1m", "5m", "15m", "1h", "4h", "1d")
            start_time: Start timestamp
            end_time: End timestamp
            limit: Maximum results

        Returns:
            List of historical candles
        """
        if not self._repository:
            return []

        try:
            candles = await self._repository.get_candles(
                symbol=symbol,
                interval=timeframe,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
            )
            return candles
        except Exception as e:
            logger.error("get_market_history_error", error=str(e))
            return []

    async def list_connectors(self) -> list[dict[str, str]]:
        """List all registered connectors.

        Returns:
            List of connector info
        """
        connectors = []

        if self._collector_manager:
            status = self._collector_manager.get_status()
            connectors.append({
                "name": "hyperliquid",
                "status": "running" if status.get("running") else "stopped",
                "symbol": self._settings.hyperliquid.symbol,
            })

        if self._leaderboard_collector:
            connectors.append({
                "name": "leaderboard",
                "status": "running" if self._leaderboard_collector._running else "stopped",
                "symbol": self._settings.hyperliquid.symbol,
            })

        return connectors

    async def get_connector_status(self, name: str) -> dict[str, Any] | None:
        """Get status of a specific connector.

        Args:
            name: Connector name

        Returns:
            Connector status or None
        """
        if name == "hyperliquid" and self._collector_manager:
            return self._collector_manager.get_status()
        if name == "leaderboard" and self._leaderboard_collector:
            return self._leaderboard_collector.get_stats()
        return None

    async def start_connector(self, name: str) -> None:
        """Start a specific connector.

        Args:
            name: Connector name

        Raises:
            ValueError: If connector not found
        """
        if name == "hyperliquid":
            if self._collector_manager and not self._collector_manager.is_running:
                await self._collector_manager.start()
                return
            if not self._collector_manager and self._event_bus:
                self._collector_manager = CollectorManager(
                    event_bus=self._event_bus,
                    config=self._settings.hyperliquid,
                )
                await self._collector_manager.start()
                return

        if name == "leaderboard":
            if self._leaderboard_collector and not self._leaderboard_collector._running:
                await self._leaderboard_collector.start()
                return
            if not self._leaderboard_collector and self._event_bus:
                self._leaderboard_collector = LeaderboardCollector(
                    event_bus=self._event_bus,
                    config=self._settings.hyperliquid,
                )
                await self._leaderboard_collector.start()
                return

        raise ValueError(f"Connector {name} not found or cannot be started")

    async def stop_connector(self, name: str) -> None:
        """Stop a specific connector.

        Args:
            name: Connector name

        Raises:
            ValueError: If connector not found
        """
        if name == "hyperliquid" and self._collector_manager:
            await self._collector_manager.stop()
            return

        if name == "leaderboard" and self._leaderboard_collector:
            await self._leaderboard_collector.stop()
            return

        raise ValueError(f"Connector {name} not found")

    async def get_connector_health(self, name: str) -> dict[str, Any] | None:
        """Get health of a specific connector.

        Args:
            name: Connector name

        Returns:
            Health status or None
        """
        return await self.get_connector_status(name)

    @property
    def event_bus(self) -> EventBus | None:
        """Get the event bus instance."""
        return self._event_bus

    @property
    def repository(self) -> DataRepository | None:
        """Get the repository instance."""
        return self._repository

    @property
    def collector_manager(self) -> CollectorManager | None:
        """Get the collector manager instance."""
        return self._collector_manager

    @property
    def leaderboard_collector(self) -> LeaderboardCollector | None:
        """Get the leaderboard collector instance."""
        return self._leaderboard_collector
