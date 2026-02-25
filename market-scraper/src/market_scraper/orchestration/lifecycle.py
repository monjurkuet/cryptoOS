# src/market_scraper/orchestration/lifecycle.py

"""Lifecycle manager for orchestrating all system components."""

import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from market_scraper.config.market_config import load_market_config
from market_scraper.connectors.hyperliquid.collectors.leaderboard import LeaderboardCollector
from market_scraper.connectors.hyperliquid.collectors.manager import CollectorManager
from market_scraper.connectors.hyperliquid.collectors.trader_ws import TraderWebSocketCollector
from market_scraper.core.config import Settings, get_settings
from market_scraper.core.events import StandardEvent
from market_scraper.event_bus.base import EventBus
from market_scraper.event_bus.memory_bus import MemoryEventBus
from market_scraper.event_bus.redis_bus import RedisEventBus
from market_scraper.orchestration.health import ComponentType, HealthMonitor
from market_scraper.orchestration.scheduler import Scheduler
from market_scraper.processors.position_inference import PositionInferenceProcessor
from market_scraper.processors.signal_generation import SignalGenerationProcessor
from market_scraper.processors.trader_scoring import TraderScoringProcessor
from market_scraper.storage.base import DataRepository
from market_scraper.storage.memory_repository import MemoryRepository
from market_scraper.storage.models import TradingSignal
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
        self._trader_ws_collector: TraderWebSocketCollector | None = None

        # Processors
        self._processors: list[Any] = []

        # Scheduler and Health Monitor
        self._scheduler: Scheduler | None = None
        self._health_monitor: HealthMonitor | None = None

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

        start_time = datetime.now(UTC)
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

            # 3.1 Run candle backfill
            await self._run_candle_backfill()
            logger.info("candle_backfill_complete")

            # 4. Initialize processors
            await self._init_processors()
            logger.info("processors_initialized", count=len(self._processors))

            # 5. Initialize Collector Manager (market data)
            await self._init_collector_manager()
            logger.info("collector_manager_initialized")

            # 6. Initialize Leaderboard Collector
            await self._init_leaderboard_collector()
            logger.info("leaderboard_collector_initialized")

            # 6.1 Initialize Trader WebSocket Collector
            await self._init_trader_ws_collector()
            logger.info("trader_ws_collector_initialized")

            # 7. Initialize Scheduler
            await self._init_scheduler()
            logger.info("scheduler_initialized")

            # 8. Initialize Health Monitor
            await self._init_health_monitor()
            logger.info("health_monitor_initialized")

            self._started = True
            self._startup_complete = True

            duration_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
            logger.info("lifecycle_startup_complete", duration_ms=round(duration_ms, 2))

        except Exception as e:
            logger.error("lifecycle_startup_failed", error=str(e), exc_info=True)
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
            logger.error("background_startup_failed", error=str(e), exc_info=True)

    async def wait_ready(self, timeout: float = 30.0) -> bool:
        """Wait for startup to complete.

        Args:
            timeout: Maximum seconds to wait.

        Returns:
            True if ready, False if timeout or error.
        """
        start_time = time.time()
        while not self._startup_complete:
            if self._startup_error:
                return False
            if time.time() - start_time > timeout:
                return False
            await asyncio.sleep(0.1)
        return True

    async def shutdown(self) -> None:
        """Graceful shutdown of all components.

        Order (reverse of startup):
        1. Health Monitor
        2. Scheduler
        3. Leaderboard Collector
        4. Collector Manager
        5. Processors
        6. Repository
        7. Event Bus
        """
        start_time = datetime.now(UTC)
        logger.info("lifecycle_shutdown_begin")

        # Stop health monitor
        if self._health_monitor:
            self._health_monitor = None
            logger.info("health_monitor_stopped")

        # Stop scheduler
        if self._scheduler:
            try:
                await self._scheduler.stop()
            except Exception as e:
                logger.error("scheduler_stop_error", error=str(e), exc_info=True)
            self._scheduler = None

        # Stop leaderboard collector
        if self._leaderboard_collector:
            try:
                await self._leaderboard_collector.stop()
            except Exception as e:
                logger.error("leaderboard_stop_error", error=str(e), exc_info=True)
            self._leaderboard_collector = None

        # Stop trader websocket collector
        if self._trader_ws_collector:
            try:
                await self._trader_ws_collector.stop()
            except Exception as e:
                logger.error("trader_ws_stop_error", error=str(e), exc_info=True)
            self._trader_ws_collector = None

        # Stop collector manager
        if self._collector_manager:
            try:
                await self._collector_manager.stop()
            except Exception as e:
                logger.error("collector_stop_error", error=str(e), exc_info=True)
            self._collector_manager = None

        # Stop processors
        for processor in self._processors:
            try:
                await processor.stop()
            except Exception as e:
                logger.error("processor_stop_error", error=str(e), exc_info=True)
        self._processors.clear()

        # Disconnect repository
        if self._repository:
            try:
                await self._repository.disconnect()
            except Exception as e:
                logger.error("repository_disconnect_error", error=str(e), exc_info=True)
            self._repository = None

        # Disconnect event bus
        if self._event_bus:
            try:
                await self._event_bus.disconnect()
            except Exception as e:
                logger.error("event_bus_disconnect_error", error=str(e), exc_info=True)
            self._event_bus = None

        self._started = False
        duration_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000
        logger.info("lifecycle_shutdown_complete", duration_ms=round(duration_ms, 2))

    async def _init_event_bus(self) -> None:
        """Initialize event bus based on configuration."""
        redis_url = self._settings.redis.url
        logger.debug("init_event_bus_checking", redis_url=redis_url)

        if redis_url:
            # Try to use Redis event bus if URL is configured (including default)
            try:
                self._event_bus = RedisEventBus(redis_url=redis_url)
                await self._event_bus.connect()
                logger.info("redis_event_bus_initialized", url=redis_url)
                return
            except Exception as e:
                logger.warning(
                    "redis_connection_failed_using_memory",
                    error=str(e),
                )

        # Default to memory event bus if Redis not configured or failed
        self._event_bus = MemoryEventBus()
        await self._event_bus.connect()
        logger.info("memory_event_bus_initialized")

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
        skip_storage_events = {"leaderboard"}  # Leaderboard is ~30MB, exceeds MongoDB 16MB limit

        async def storage_handler(event: StandardEvent) -> None:
            """Handle events by storing them in the repository."""
            # Skip events that are too large
            if event.event_type in skip_storage_events:
                return

            if self._repository:
                try:
                    # Store in events collection
                    await self._repository.store(event)

                    # Also store trading signals in signals collection
                    if event.event_type == "trading_signal":
                        await self._store_trading_signal(event)

                except Exception as e:
                    logger.error(
                        "storage_handler_error",
                        event_id=event.event_id,
                        error=str(e),
                    )

        # Subscribe to all events
        await self._event_bus.subscribe("*", storage_handler)

    async def _store_trading_signal(self, event: StandardEvent) -> None:
        """Store a trading signal in the signals collection.

        Args:
            event: Trading signal event to store.
        """
        if not self._repository or not isinstance(self._repository, MongoRepository):
            return

        payload = event.payload
        if not isinstance(payload, dict):
            return

        try:
            signal = TradingSignal(
                t=event.timestamp,
                symbol=payload.get("symbol", "BTC"),
                rec=payload.get("recommendation", "NEUTRAL"),
                conf=payload.get("confidence", 0),
                long_bias=payload.get("longBias", 0),
                short_bias=payload.get("shortBias", 0),
                net_exp=payload.get("netExposure", 0),
                t_long=payload.get("tradersLong", 0),
                t_short=payload.get("tradersShort", 0),
                t_flat=payload.get("tradersFlat", 0),
                price=payload.get("price", 0),
            )
            await self._repository.store_signal(signal)
            logger.debug("trading_signal_stored", symbol=signal.symbol, rec=signal.rec)
        except Exception as e:
            logger.error("trading_signal_store_error", error=str(e))

    async def _run_candle_backfill(self) -> None:
        """Run historical candle backfill on startup."""
        from market_scraper.connectors.hyperliquid.client import HyperliquidClient
        from market_scraper.services.candle_backfill import CandleBackfillService

        market_config = load_market_config()
        backfill_config = market_config.candle_backfill

        if not backfill_config.enabled or not backfill_config.run_on_startup:
            logger.info("backfill_skipped", enabled=backfill_config.enabled)
            return

        try:
            client = HyperliquidClient(
                base_url=self._settings.hyperliquid.api_url,
                timeout=self._settings.hyperliquid.timeout_seconds,
            )
            await client.connect()

            service = CandleBackfillService(
                client=client,
                repository=self._repository,
                config=backfill_config,
                symbol=self._settings.hyperliquid.symbol,
            )
            results = await service.run_backfill()

            await client.close()
            logger.info("backfill_completed", results=results)

        except Exception as e:
            logger.error("backfill_failed", error=str(e), exc_info=True)

    async def _init_processors(self) -> None:
        """Initialize event processors."""
        if not self._event_bus:
            raise RuntimeError("Event bus not initialized")

        config = self._settings.hyperliquid

        # Load market configuration
        market_config = load_market_config()

        # Position Inference Processor
        position_inference = PositionInferenceProcessor(
            event_bus=self._event_bus,
            config=config,
            position_inference_config=market_config.position_inference,
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

        # Trader Scoring Processor (using config for filters and tags)
        trader_scoring = TraderScoringProcessor(
            event_bus=self._event_bus,
            config=config,
            min_score=market_config.filters.min_score,
            max_count=market_config.filters.max_count,
            tags_config=market_config.tags,
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

        # Load market configuration from YAML
        market_config = load_market_config()

        self._collector_manager = CollectorManager(
            event_bus=self._event_bus,
            config=self._settings.hyperliquid,
            collectors=["candles"],  # Only candles collector implemented currently
            buffer_config=market_config.buffer,
        )

        await self._collector_manager.start()

    async def _init_leaderboard_collector(self) -> None:
        """Initialize the leaderboard collector."""
        if not self._event_bus:
            raise RuntimeError("Event bus not initialized")

        if not self._settings.hyperliquid.enabled:
            logger.info("leaderboard_collector_disabled")
            return

        # Load market configuration from YAML
        market_config = load_market_config()

        # Get database reference for direct storage
        db = None
        if hasattr(self._repository, "_db"):
            db = self._repository._db

        self._leaderboard_collector = LeaderboardCollector(
            event_bus=self._event_bus,
            config=self._settings.hyperliquid,
            db=db,
            market_config=market_config,
        )

        await self._leaderboard_collector.start()

    async def _init_trader_ws_collector(self) -> None:
        """Initialize the trader WebSocket collector for position tracking.

        This collector subscribes to tracked traders and publishes their
        real-time position data to the event bus.
        """
        if not self._event_bus:
            raise RuntimeError("Event bus not initialized")

        if not self._settings.hyperliquid.enabled:
            logger.info("trader_ws_collector_disabled")
            return

        # Load market configuration from YAML
        market_config = load_market_config()

        # Create the collector
        self._trader_ws_collector = TraderWebSocketCollector(
            event_bus=self._event_bus,
            config=self._settings.hyperliquid,
            buffer_config=market_config.buffer,
        )

        # Wait a moment for leaderboard to process and store tracked traders
        # Then get tracked addresses from leaderboard collector
        await asyncio.sleep(2.0)

        if self._leaderboard_collector:
            tracked_addresses = await self._leaderboard_collector.get_tracked_addresses()

            if tracked_addresses:
                logger.info("starting_trader_ws_with_tracked", count=len(tracked_addresses))
                await self._trader_ws_collector.start(tracked_addresses)
            else:
                logger.warning("no_tracked_addresses_trader_ws_not_started")
                # Start without traders - will add them later when leaderboard refreshes
        else:
            logger.warning("leaderboard_not_available_trader_ws_delayed")

    async def _init_scheduler(self) -> None:
        """Initialize the scheduler with configured tasks."""
        market_config = load_market_config()
        scheduler_config = market_config.scheduler

        if not scheduler_config.enabled:
            logger.info("scheduler_disabled")
            return

        self._scheduler = Scheduler()

        # Register tasks from config
        tasks = scheduler_config.tasks

        # Leaderboard refresh task
        if "leaderboard_refresh" in tasks and tasks["leaderboard_refresh"].enabled:
            leaderboard_config = tasks["leaderboard_refresh"]
            interval = timedelta(seconds=leaderboard_config.interval_seconds)

            async def refresh_leaderboard():
                if self._leaderboard_collector and self._leaderboard_collector._running:
                    try:
                        await self._leaderboard_collector.fetch_now()
                    except Exception as e:
                        logger.error("leaderboard_refresh_error", error=str(e))

            self._scheduler.schedule("leaderboard_refresh", interval, refresh_leaderboard)
            logger.info(
                "scheduler_task_registered",
                task="leaderboard_refresh",
                interval=leaderboard_config.interval_seconds,
            )

        # Health check task
        if "health_check" in tasks and tasks["health_check"].enabled:
            health_config = tasks["health_check"]
            interval = timedelta(seconds=health_config.interval_seconds)

            async def check_health():
                try:
                    await self.health_check()
                except Exception as e:
                    logger.error("health_check_error", error=str(e))

            self._scheduler.schedule("health_check", interval, check_health)
            logger.info(
                "scheduler_task_registered",
                task="health_check",
                interval=health_config.interval_seconds,
            )

        # Data cleanup task
        if "data_cleanup" in tasks and tasks["data_cleanup"].enabled:
            cleanup_config = tasks["data_cleanup"]
            interval = timedelta(seconds=cleanup_config.interval_seconds)

            async def cleanup_data():
                logger.info("data_cleanup_task_executed")

            self._scheduler.schedule("data_cleanup", interval, cleanup_data)
            logger.info(
                "scheduler_task_registered",
                task="data_cleanup",
                interval=cleanup_config.interval_seconds,
            )

        # Connector health task
        if "connector_health" in tasks and tasks["connector_health"].enabled:
            connector_health_config = tasks["connector_health"]
            interval = timedelta(seconds=connector_health_config.interval_seconds)

            async def check_connector_health():
                try:
                    # Get health for each on-chain connector
                    from market_scraper.api.dependencies import get_connector_factory

                    factory = get_connector_factory()
                    connectors = await factory.get_all_connectors()

                    for connector in connectors:
                        try:
                            health = await connector.health_check()
                            status = health.get("status", "unknown")
                            logger.debug(
                                "connector_health_check",
                                connector=connector.name,
                                status=status,
                            )
                        except Exception as e:
                            logger.warning(
                                "connector_health_check_failed",
                                connector=getattr(connector, "name", "unknown"),
                                error=str(e),
                            )
                except Exception as e:
                    logger.error("connector_health_task_error", error=str(e))

            self._scheduler.schedule("connector_health", interval, check_connector_health)
            logger.info(
                "scheduler_task_registered",
                task="connector_health",
                interval=connector_health_config.interval_seconds,
            )

        # Start the scheduler
        await self._scheduler.start()

    async def _init_health_monitor(self) -> None:
        """Initialize the health monitor."""
        if not self._scheduler:
            logger.warning("health_monitor_no_scheduler")
            return

        market_config = load_market_config()
        scheduler_config = market_config.scheduler

        if not scheduler_config.enabled:
            logger.info("health_monitor_disabled")
            return

        self._health_monitor = HealthMonitor(self._scheduler)

        # Register components for health monitoring
        if self._event_bus:
            self._health_monitor.register_component("event_bus", ComponentType.EVENT_BUS)
        if self._repository:
            self._health_monitor.register_component("repository", ComponentType.STORAGE)
        if self._collector_manager:
            self._health_monitor.register_component("collector_manager", ComponentType.CONNECTOR)
        if self._leaderboard_collector:
            self._health_monitor.register_component("leaderboard", ComponentType.CONNECTOR)
        if self._trader_ws_collector:
            self._health_monitor.register_component("trader_ws", ComponentType.CONNECTOR)

        for i, _processor in enumerate(self._processors):
            self._health_monitor.register_component(f"processor_{i}", ComponentType.PROCESSOR)

        logger.info(
            "health_monitor_components_registered", count=len(self._health_monitor._components)
        )

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
            "collectors": self._collector_manager is not None
            and self._collector_manager.is_running,
            "leaderboard": self._leaderboard_collector is not None
            and self._leaderboard_collector._running,
            "trader_ws": self._trader_ws_collector is not None
            and self._trader_ws_collector._running,
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
            "trader_ws": {
                "status": "healthy" if self._trader_ws_collector else "not_initialized",
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

        if self._trader_ws_collector:
            result["trader_ws"].update(self._trader_ws_collector.get_stats())

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
            connectors.append(
                {
                    "name": "hyperliquid",
                    "status": "running" if status.get("running") else "stopped",
                    "symbol": self._settings.hyperliquid.symbol,
                }
            )

        if self._leaderboard_collector:
            connectors.append(
                {
                    "name": "leaderboard",
                    "status": "running" if self._leaderboard_collector._running else "stopped",
                    "symbol": self._settings.hyperliquid.symbol,
                }
            )

        if self._trader_ws_collector:
            connectors.append(
                {
                    "name": "trader_ws",
                    "status": "running" if self._trader_ws_collector._running else "stopped",
                    "symbol": self._settings.hyperliquid.symbol,
                }
            )

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
        if name == "trader_ws" and self._trader_ws_collector:
            return self._trader_ws_collector.get_stats()
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

        if name == "trader_ws":
            if self._trader_ws_collector and not self._trader_ws_collector._running:
                # Get tracked addresses and start
                if self._leaderboard_collector:
                    addresses = await self._leaderboard_collector.get_tracked_addresses()
                    if addresses:
                        await self._trader_ws_collector.start(addresses)
                        return
                raise ValueError("No tracked addresses available for trader_ws")
            if not self._trader_ws_collector and self._event_bus:
                market_config = load_market_config()
                self._trader_ws_collector = TraderWebSocketCollector(
                    event_bus=self._event_bus,
                    config=self._settings.hyperliquid,
                    buffer_config=market_config.buffer,
                )
                if self._leaderboard_collector:
                    addresses = await self._leaderboard_collector.get_tracked_addresses()
                    if addresses:
                        await self._trader_ws_collector.start(addresses)
                        return
                raise ValueError("No tracked addresses available for trader_ws")

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

        if name == "trader_ws" and self._trader_ws_collector:
            await self._trader_ws_collector.stop()
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

    @property
    def trader_ws_collector(self) -> TraderWebSocketCollector | None:
        """Get the trader WebSocket collector instance."""
        return self._trader_ws_collector
