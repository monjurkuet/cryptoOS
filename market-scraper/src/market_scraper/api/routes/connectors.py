# src/market_scraper/api/routes/connectors.py

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from market_scraper.api.dependencies import get_lifecycle
from market_scraper.api.models import HealthStatus
from market_scraper.orchestration.lifecycle import LifecycleManager

router = APIRouter()


class ConnectorListItem(BaseModel):
    """Connector list item."""

    name: str
    status: str
    symbol: str | None = None


class ConnectorStatusResponse(BaseModel):
    """Connector status response."""

    name: str
    status: str
    connected: bool
    running: bool
    websocket_connected: bool = False
    reconnect_attempts: int = 0
    collectors: dict[str, Any] | None = None


class ConnectorHealthResponse(BaseModel):
    """Connector health response."""

    name: str
    status: HealthStatus
    latency_ms: float | None = None
    message: str = ""


@router.get("", response_model=list[ConnectorListItem])
async def list_connectors(
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> list[dict[str, str]]:
    """List all registered connectors.

    Returns status information for all available connectors.
    """
    connectors = await lifecycle.list_connectors()
    return connectors


@router.get("/{name}", response_model=ConnectorStatusResponse)
async def get_connector(
    name: str,
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, Any]:
    """Get connector status.

    Returns detailed status information for a specific connector.
    """
    status = await lifecycle.get_connector_status(name)
    if not status:
        raise HTTPException(status_code=404, detail=f"Connector {name} not found")

    # Transform status to match response model
    return {
        "name": name,
        "status": "running" if status.get("running") else "stopped",
        "connected": status.get("websocket_connected", False),
        "running": status.get("running", False),
        "websocket_connected": status.get("websocket_connected", False),
        "reconnect_attempts": status.get("reconnect_attempts", 0),
        "collectors": status.get("collectors"),
    }


@router.post("/{name}/start")
async def start_connector(
    name: str,
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, str]:
    """Start a connector.

    Starts the specified connector if it exists.
    """
    try:
        await lifecycle.start_connector(name)
        return {"status": "started", "connector": name}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.post("/{name}/stop")
async def stop_connector(
    name: str,
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, str]:
    """Stop a connector.

    Stops the specified connector if it exists.
    """
    try:
        await lifecycle.stop_connector(name)
        return {"status": "stopped", "connector": name}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/{name}/health", response_model=ConnectorHealthResponse)
async def connector_health(
    name: str,
    lifecycle: LifecycleManager = Depends(get_lifecycle),
) -> dict[str, Any]:
    """Get connector health.

    Returns health information for a specific connector.
    """
    status = await lifecycle.get_connector_status(name)
    if not status:
        raise HTTPException(status_code=404, detail=f"Connector {name} not found")

    # Determine health status
    is_running = status.get("running", False)
    is_connected = status.get("websocket_connected", False)

    if is_running and is_connected:
        health_status = HealthStatus.HEALTHY
    elif is_running:
        health_status = HealthStatus.DEGRADED
    else:
        health_status = HealthStatus.UNHEALTHY

    return {
        "name": name,
        "status": health_status,
        "latency_ms": None,
        "message": "Connected" if is_connected else "Disconnected",
    }
