# src/market_scraper/api/routes/health.py

from fastapi import APIRouter, Depends, HTTPException

from market_scraper import __version__
from market_scraper.api.dependencies import get_lifecycle
from market_scraper.api.models import (
    HealthResponse,
    HealthStatus,
    ReadinessResponse,
)
from market_scraper.orchestration.lifecycle import LifecycleManager

router = APIRouter()


@router.get("/live", response_model=dict)
async def liveness_probe():
    """Liveness probe for Kubernetes.

    Returns 200 if the application is running.
    """
    return {"status": "alive"}


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_probe(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
):
    """Readiness probe for Kubernetes.

    Checks if all dependencies are available.
    Returns 503 if startup is not complete yet.
    """
    # Check if startup is complete
    if not lifecycle.is_ready:
        startup_error = lifecycle.startup_error
        if startup_error:
            raise HTTPException(
                status_code=503,
                detail={
                    "ready": False,
                    "error": str(startup_error),
                    "checks": {"startup": False},
                },
            )
        raise HTTPException(
            status_code=503,
            detail={
                "ready": False,
                "message": "Startup in progress",
                "checks": {"startup": False},
            },
        )

    checks = await lifecycle.health_check()

    ready = all(checks.values()) if checks else False

    if not ready:
        raise HTTPException(
            status_code=503,
            detail=ReadinessResponse(ready=False, checks=checks).model_dump(),
        )

    return ReadinessResponse(ready=True, checks=checks)


@router.get("/startup", response_model=dict)
async def startup_status(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
):
    """Check startup status.

    Returns the current startup state:
    - ready: True if startup is complete
    - error: Error message if startup failed
    """
    return {
        "ready": lifecycle.is_ready,
        "error": str(lifecycle.startup_error) if lifecycle.startup_error else None,
    }


@router.get("/status", response_model=HealthResponse)
async def health_status(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
):
    """Detailed health status.

    Returns health information for all components.
    Caches result for 5 seconds to prevent event-loop-blocking health checks
    from causing cascading timeouts in the dashboard.
    """
    import asyncio
    import time

    _HEALTH_STATUS_CACHE_TTL = 5.0
    _HEALTH_CHECK_TIMEOUT = 3.0
    cache_key = "_health_status_cache"
    cached_entry = getattr(health_status, cache_key, None)
    if cached_entry and (time.monotonic() - cached_entry[0]) <= _HEALTH_STATUS_CACHE_TTL:
        return cached_entry[1]

    # If startup not complete, return startup status
    if not lifecycle.is_ready:
        startup_error = lifecycle.startup_error
        result = HealthResponse(
            status=HealthStatus.DEGRADED if not startup_error else HealthStatus.UNHEALTHY,
            version=__version__,
            components={
                "startup": {
                    "status": "in_progress" if not startup_error else "failed",
                    "error": str(startup_error) if startup_error else None,
                }
            },
        )
        setattr(health_status, cache_key, (time.monotonic(), result))
        return result

    try:
        components = await asyncio.wait_for(
            lifecycle.get_detailed_health(),
            timeout=_HEALTH_CHECK_TIMEOUT,
        )
    except TimeoutError:
        # Health check timed out — return cached stale data or degraded
        if cached_entry:
            return cached_entry[1]
        components = {
            "api": {"status": "healthy"},
            "repository": {"status": "degraded", "error": "health_check_timed_out"},
        }

    overall_status = HealthStatus.HEALTHY
    if any(c.get("status") == "unhealthy" for c in components.values()):
        overall_status = HealthStatus.UNHEALTHY
    elif any(c.get("status") == "degraded" for c in components.values()):
        overall_status = HealthStatus.DEGRADED

    result = HealthResponse(
        status=overall_status,
        version=__version__,
        components=components,
    )
    setattr(health_status, cache_key, (time.monotonic(), result))
    return result
