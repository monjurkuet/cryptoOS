"""Signal System API."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from signal_system.config import get_settings
from signal_system.api.routes import router as signals_router
from signal_system.api.dependencies import set_components
from signal_system.event_subscriber import EventSubscriber
from signal_system.signal_generation.processor import SignalGenerationProcessor
from signal_system.signal_store import SignalStore
from signal_system.whale_alerts.detector import WhaleAlertDetector

logger = structlog.get_logger(__name__)

# Component instances for this module
_event_subscriber: EventSubscriber | None = None
_signal_processor: SignalGenerationProcessor | None = None
_whale_detector: WhaleAlertDetector | None = None
_signal_store: SignalStore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global _event_subscriber, _signal_processor, _whale_detector, _signal_store

    settings = get_settings()

    # Initialize components
    _signal_processor = SignalGenerationProcessor(symbol=settings.symbol)
    _whale_detector = WhaleAlertDetector()
    _signal_store = SignalStore()

    # Setup event subscriber
    _event_subscriber = EventSubscriber(settings.redis)

    # Set components for dependency injection
    set_components(
        signal_processor=_signal_processor,
        whale_detector=_whale_detector,
        event_subscriber=_event_subscriber,
        signal_store=_signal_store,
    )

    # Register handlers
    async def handle_position(event: dict) -> None:
        if _signal_processor:
            signal = await _signal_processor.process_position(event)
            if signal:
                # Store the signal
                if _signal_store:
                    _signal_store.store_signal(signal)
                logger.info("signal_generated", signal=signal)

    async def handle_scored_traders(event: dict) -> None:
        if _signal_processor:
            await _signal_processor.process_scored_traders(event)

    _event_subscriber.subscribe("trader_positions", handle_position)
    _event_subscriber.subscribe("scored_traders", handle_scored_traders)

    # Connect and start subscriber
    try:
        await _event_subscriber.connect()
        logger.info("api_startup_complete")
    except Exception as e:
        logger.warning("redis_connection_failed", error=str(e))

    yield

    # Cleanup
    if _event_subscriber:
        await _event_subscriber.disconnect()
    logger.info("api_shutdown_complete")


settings = get_settings()

app = FastAPI(
    title="Smart Money Signal System",
    description="Real-time trading signals from whale position tracking",
    version="0.1.0",
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
        },
    }
