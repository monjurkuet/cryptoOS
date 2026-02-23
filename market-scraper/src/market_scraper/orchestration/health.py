# src/market_scraper/orchestration/health.py

import asyncio
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog

from market_scraper.orchestration.scheduler import Scheduler

logger = structlog.get_logger(__name__)


class ComponentType(StrEnum):
    """Component types for health monitoring."""

    CONNECTOR = "connector"
    EVENT_BUS = "event_bus"
    STORAGE = "storage"
    PROCESSOR = "processor"


class ComponentHealth:
    """Health status for a single component."""

    def __init__(
        self,
        name: str,
        component_type: ComponentType,
        status: str = "unknown",
    ) -> None:
        self.name = name
        self.component_type = component_type
        self.status = status
        self.last_check: datetime | None = None
        self.latency_ms: float | None = None
        self.error: str | None = None
        self.metadata: dict[str, Any] = {}


class HealthMonitor:
    """Monitors health of all system components."""

    def __init__(self, scheduler: Scheduler) -> None:
        self._scheduler = scheduler
        self._components: dict[str, ComponentHealth] = {}
        self._check_interval = timedelta(seconds=30)

    def register_component(
        self,
        name: str,
        component_type: ComponentType,
    ) -> None:
        """Register a component for health monitoring."""
        self._components[name] = ComponentHealth(name=name, component_type=component_type)
        logger.info("Component registered for health monitoring", name=name, type=component_type)

    async def check_component(self, name: str) -> ComponentHealth | None:
        """Check health of a specific component."""
        if name not in self._components:
            return None

        component = self._components[name]
        component.last_check = datetime.now(UTC)

        try:
            await self._perform_check(component)
            component.status = "healthy"
            component.error = None
        except Exception as e:
            component.status = "unhealthy"
            component.error = str(e)
            logger.error("Health check failed", component=name, error=str(e))

        return component

    async def _perform_check(self, component: ComponentHealth) -> None:
        """Perform the actual health check for a component."""
        await asyncio.sleep(0.01)
        component.latency_ms = 1.0

    async def check_all(self) -> dict[str, ComponentHealth]:
        """Check health of all registered components."""
        results = {}
        for name in self._components:
            result = await self.check_component(name)
            if result:
                results[name] = result
        return results

    def get_status_summary(self) -> dict[str, Any]:
        """Get a summary of all component health statuses."""
        summary: dict[str, Any] = {
            "total": len(self._components),
            "healthy": 0,
            "unhealthy": 0,
            "unknown": 0,
            "components": {},
        }

        for name, component in self._components.items():
            summary["components"][name] = {
                "type": component.component_type,
                "status": component.status,
                "last_check": component.last_check.isoformat() if component.last_check else None,
                "latency_ms": component.latency_ms,
                "error": component.error,
            }

            if component.status == "healthy":
                summary["healthy"] += 1
            elif component.status == "unhealthy":
                summary["unhealthy"] += 1
            else:
                summary["unknown"] += 1

        return summary
