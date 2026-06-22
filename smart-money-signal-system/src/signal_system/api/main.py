"""Signal System API."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
import structlog

from signal_system.api.dependencies import set_components
from signal_system.api.routes import router as signals_router
from signal_system.config import get_settings
from signal_system.event_subscriber import EventSubscriber
from signal_system.runtime import RuntimeComponents, build_runtime

logger = structlog.get_logger(__name__)

_runtime_components: RuntimeComponents | None = None
_subscriber_task: asyncio.Task | None = None

# Compatibility globals used by health endpoint and legacy tests.
_event_subscriber: EventSubscriber | None = None
_signal_processor = None
_whale_detector = None
_signal_store = None
_outcome_tracker = None
_outcome_store = None
_rl_param_server = None
_trace_store = None
_param_event_store = None
_event_processor = None
_mongo_client: MongoClient | None = None


def _bind_component_refs(components: RuntimeComponents) -> None:
    """Populate module globals from assembled runtime components."""
    global _event_subscriber, _signal_processor, _whale_detector, _signal_store
    global _outcome_tracker, _outcome_store, _rl_param_server, _trace_store
    global _param_event_store, _event_processor, _mongo_client

    _event_subscriber = components.event_subscriber
    _signal_processor = components.signal_processor
    _whale_detector = components.whale_detector
    _signal_store = components.signal_store
    _outcome_tracker = components.outcome_tracker
    _outcome_store = components.outcome_store
    _rl_param_server = components.rl_param_server
    _trace_store = components.trace_store
    _param_event_store = components.param_event_store
    _event_processor = components.event_processor
    _mongo_client = components.mongo_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global _runtime_components, _subscriber_task

    settings = get_settings()
    _runtime_components = build_runtime(
        settings=settings,
        mongo_client_factory=MongoClient,
        event_subscriber_factory=EventSubscriber,
    )
    _bind_component_refs(_runtime_components)

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
        settings=_runtime_components.settings,
        runtime_components=_runtime_components,
        signal_config_store=_runtime_components.config_store,
    )

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
    _runtime_components = None
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