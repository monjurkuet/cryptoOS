"""Signal System API."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
import structlog

from signal_system.config import get_settings
from signal_system.api.routes import router as signals_router
from signal_system.api.dependencies import set_components
from signal_system.event_subscriber import EventSubscriber
from signal_system.signal_generation.processor import SignalGenerationProcessor
from signal_system.signal_store import SignalStore
from signal_system.whale_alerts.detector import WhaleAlertDetector
from signal_system.services.event_processor import EventProcessor
from signal_system.rl.outcome_tracker import SignalOutcomeTracker
from signal_system.rl.outcome_store import OutcomeStore
from signal_system.rl.parameter_server import RLParameterServer
from signal_system.dashboard.store import DecisionTraceStore, ParamEventStore

logger = structlog.get_logger(__name__)

_CHECKPOINT_DIR = Path(__file__).parent.parent.parent.parent / "checkpoints"

# Component instances for this module
_event_subscriber: EventSubscriber | None = None
_signal_processor: SignalGenerationProcessor | None = None
_whale_detector: WhaleAlertDetector | None = None
_signal_store: SignalStore | None = None
_outcome_tracker: SignalOutcomeTracker | None = None
_outcome_store: OutcomeStore | None = None
_rl_param_server: RLParameterServer | None = None
_trace_store: DecisionTraceStore | None = None
_param_event_store: ParamEventStore | None = None
_event_processor: EventProcessor | None = None
_subscriber_task: asyncio.Task | None = None
_mongo_client: MongoClient | None = None


def _create_mongo_client(settings) -> MongoClient | None:
    """Create shared MongoDB client for signal-system persistence."""
    try:
        client = MongoClient(settings.mongo.url, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        logger.info("api_mongo_connected")
        return client
    except Exception as error:
        logger.warning("api_mongo_connection_failed", error=str(error))
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global _event_subscriber, _signal_processor, _whale_detector, _signal_store, _outcome_tracker, _outcome_store, _rl_param_server, _trace_store, _param_event_store, _event_processor, _subscriber_task, _mongo_client

    settings = get_settings()

    _mongo_client = _create_mongo_client(settings)

    # Initialize components
    _signal_processor = SignalGenerationProcessor(symbol=settings.symbol)
    _whale_detector = WhaleAlertDetector()
    _signal_store = SignalStore(
        mongo_client=_mongo_client,
        database_name=settings.mongo.database,
        retention_days=settings.dashboard_retention_days,
    )

    # RL components
    _outcome_tracker = SignalOutcomeTracker()
    _outcome_store = OutcomeStore(
        mongo_client=_mongo_client,
        database_name=settings.mongo.database,
    )
    _trace_store = DecisionTraceStore(
        mongo_client=_mongo_client,
        database_name=settings.mongo.database,
        retention_days=settings.dashboard_retention_days,
    )
    _param_event_store = ParamEventStore(
        mongo_client=_mongo_client,
        database_name=settings.mongo.database,
        retention_days=settings.dashboard_retention_days,
    )
    _rl_param_server = RLParameterServer(checkpoint_dir=_CHECKPOINT_DIR)

    # Keep production API lightweight on constrained hosts unless explicitly enabled.
    if settings.load_rl_checkpoint_on_startup:
        _rl_param_server.load_from_checkpoint()
    rl_params = _rl_param_server.get_params()
    _signal_processor.set_rl_params(**rl_params)
    _param_event_store.store_event(rl_params, source="startup")
    logger.info("rl_params_loaded", **rl_params)

    # Setup event subscriber
    _event_subscriber = EventSubscriber(settings.redis)

    # Create shared event processor
    _event_processor = EventProcessor(
        signal_processor=_signal_processor,
        whale_detector=_whale_detector,
        signal_store=_signal_store,
        settings=settings,
        outcome_tracker=_outcome_tracker,
        outcome_store=_outcome_store,
        trace_store=_trace_store,
    )

    # Set components for dependency injection
    set_components(
        signal_processor=_signal_processor,
        whale_detector=_whale_detector,
        event_subscriber=_event_subscriber,
        signal_store=_signal_store,
        outcome_store=_outcome_store,
        rl_param_server=_rl_param_server,
        trace_store=_trace_store,
        param_event_store=_param_event_store,
        mongo_client=_mongo_client,
        settings=settings,
    )

    # Register handlers using EventProcessor
    async def handle_position(event: dict) -> None:
        await _event_processor.handle_position_event(event)

    async def handle_scored_traders(event: dict) -> None:
        await _event_processor.handle_scored_traders(event)

    async def handle_mark_price(event: dict) -> None:
        payload = event.get("payload", {})
        mark_price = payload.get("mark_price", 0)
        if mark_price and _event_processor:
            await _event_processor.handle_price_update(float(mark_price))

    async def handle_ohlcv(event: dict) -> None:
        payload = event.get("payload", {})
        close_price = payload.get("close", 0)
        if close_price and _event_processor:
            await _event_processor.handle_price_update(float(close_price))

    _event_subscriber.subscribe("trader_positions", handle_position)
    _event_subscriber.subscribe("scored_traders", handle_scored_traders)
    _event_subscriber.subscribe("mark_price", handle_mark_price)
    _event_subscriber.subscribe("ohlcv", handle_ohlcv)

    # Connect and start subscriber in background
    try:
        await _event_subscriber.connect()
        # Start listening for events in a background task
        _subscriber_task = asyncio.create_task(_event_subscriber.start())
        logger.info("api_startup_complete")
    except Exception as e:
        logger.warning("redis_connection_failed", error=str(e))

    yield

    # Cleanup
    if _subscriber_task:
        _subscriber_task.cancel()
        try:
            await _subscriber_task
        except asyncio.CancelledError:
            pass
    if _event_subscriber:
        await _event_subscriber.disconnect()
    if _mongo_client is not None:
        _mongo_client.close()
    logger.info("api_shutdown_complete")


settings = get_settings()

app = FastAPI(
    title="Smart Money Signal System",
    description="Real-time trading signals from whale position tracking",
    version="0.1.0",
    root_path=settings.api_root_path,
    lifespan=lifespan,
)

# CORS - Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "components": {
            "event_subscriber": _event_subscriber.get_stats() if _event_subscriber else None,
            "signal_processor": _signal_processor.get_stats() if _signal_processor else None,
            "whale_detector": _whale_detector.get_stats() if _whale_detector else None,
            "signal_store": _signal_store.get_signal_stats() if _signal_store else None,
            "rl_param_server": _rl_param_server.get_status() if _rl_param_server else None,
            "trace_store": _trace_store.get_stats() if _trace_store else None,
            "param_event_store": _param_event_store.get_stats() if _param_event_store else None,
        },
    }
