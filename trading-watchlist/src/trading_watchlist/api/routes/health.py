"""Health routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/live", response_model=dict)
async def liveness_probe() -> dict[str, str]:
    """Simple liveness endpoint."""

    return {"status": "alive"}
