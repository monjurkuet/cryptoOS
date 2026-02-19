# src/market_scraper/api/routes/cbbi.py

"""CBBI (Bitcoin Bull Run Index) API endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class CBBIDataResponse(BaseModel):
    """CBBI data response."""

    confidence: float = Field(..., description="CBBI confidence score (0-100)")
    price: float | None = Field(None, description="Current BTC price")
    timestamp: str = Field(..., description="Data timestamp")
    components: dict[str, float] = Field(
        default_factory=dict,
        description="Component metric values",
    )


class CBBIComponentResponse(BaseModel):
    """CBBI component response."""

    component_name: str
    description: str
    current_value: float | None
    historical: list[dict[str, Any]]


# Cached CBBI client (initialized lazily)
_cbbi_connector = None


async def get_cbbi_connector():
    """Get or create CBBI connector."""
    global _cbbi_connector

    if _cbbi_connector is None:
        from market_scraper.connectors.cbbi import CBBIConnector, CBBIConfig

        _cbbi_connector = CBBIConnector(CBBIConfig(name="cbbi"))
        await _cbbi_connector.connect()

    return _cbbi_connector


@router.get("", response_model=CBBIDataResponse)
async def get_cbbi_data() -> dict[str, Any]:
    """Get current CBBI (Bitcoin Bull Run Index) data.

    Returns the current CBBI confidence score and component metrics.

    The CBBI aggregates multiple Bitcoin metrics to provide a comprehensive
    market sentiment indicator:
    - Confidence score ranges from 0-100
    - Higher values indicate more bullish sentiment
    - Components include: Pi Cycle Top, MVRV, Puell Multiple, etc.

    Data is updated daily from colintalkscrypto.com.
    """
    try:
        connector = await get_cbbi_connector()
        event = await connector.get_current_index()

        return {
            "confidence": event.payload.get("confidence", 0),
            "price": event.payload.get("price"),
            "timestamp": event.payload.get("timestamp", ""),
            "components": event.payload.get("components", {}),
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch CBBI data: {str(e)}",
        )


@router.get("/components", response_model=list[CBBIComponentResponse])
async def get_cbbi_components() -> list[dict[str, Any]]:
    """Get breakdown of all CBBI components.

    Returns detailed data for each CBBI component metric:
    - PiCycle: Pi Cycle Top Indicator
    - RUPL: Relative Unrealized Profit/Loss
    - RHODL: Realized HODL Ratio
    - Puell: Puell Multiple
    - 2YMA: 2-Year Moving Average Multiplier
    - MVRV: MVRV Z-Score
    - ReserveRisk: Reserve Risk
    - Woobull: Top Cap vs CVDD
    - Trolololo: Bitcoin Trolololo
    """
    try:
        connector = await get_cbbi_connector()
        events = await connector.get_component_breakdown()

        return [
            {
                "component_name": e.payload.get("component_name", ""),
                "description": e.payload.get("description", ""),
                "current_value": e.payload.get("current_value"),
                "historical": e.payload.get("historical", []),
            }
            for e in events
        ]
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch CBBI components: {str(e)}",
        )


@router.get("/components/{component_name}", response_model=CBBIComponentResponse)
async def get_cbbi_component(component_name: str) -> dict[str, Any]:
    """Get data for a specific CBBI component.

    Available components:
    - PiCycle
    - RUPL
    - RHODL
    - Puell
    - 2YMA
    - MVRV
    - ReserveRisk
    - Woobull
    - Trolololo
    """
    try:
        connector = await get_cbbi_connector()
        event = await connector.get_specific_component(component_name)

        return {
            "component_name": event.payload.get("component_name", component_name),
            "description": event.payload.get("description", ""),
            "current_value": event.payload.get("current_value"),
            "historical": event.payload.get("historical", []),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch CBBI component: {str(e)}",
        )


@router.get("/health")
async def cbbi_health() -> dict[str, Any]:
    """Check CBBI connector health."""
    try:
        connector = await get_cbbi_connector()
        return await connector.health_check()
    except Exception as e:
        return {
            "status": "unhealthy",
            "latency_ms": 0,
            "message": str(e),
        }
