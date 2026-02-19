# src/market_scraper/orchestration/scheduler.py

import asyncio
from asyncio import Task
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ScheduledTask:
    """Represents a scheduled task."""

    interval: timedelta
    callback: Callable[[], Awaitable[Any]]
    task: Task | None = None


class Scheduler:
    """Task scheduler for periodic background jobs."""

    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False

    def schedule(
        self,
        name: str,
        interval: timedelta,
        callback: Callable[[], Awaitable[Any]],
    ) -> None:
        """Schedule a periodic task.

        Args:
            name: Unique name for the task
            interval: Interval between executions
            callback: Async function to call
        """
        self._tasks[name] = ScheduledTask(interval=interval, callback=callback)
        logger.info("Task scheduled", name=name, interval=str(interval))

    async def start(self) -> None:
        """Start the scheduler and all scheduled tasks."""
        if self._running:
            return

        self._running = True
        logger.info("Starting scheduler", task_count=len(self._tasks))

        for name, scheduled_task in self._tasks.items():
            task = asyncio.create_task(self._run_task(name, scheduled_task))
            scheduled_task.task = task

    async def stop(self) -> None:
        """Stop the scheduler and all scheduled tasks."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping scheduler")

        for _name, scheduled_task in self._tasks.items():
            if scheduled_task.task and not scheduled_task.task.done():
                scheduled_task.task.cancel()
                with suppress(asyncio.CancelledError):
                    await scheduled_task.task

    async def _run_task(self, name: str, scheduled_task: ScheduledTask) -> None:
        """Run a scheduled task in a loop."""
        while self._running:
            try:
                await scheduled_task.callback()
            except Exception as e:
                logger.error("Task execution error", name=name, error=str(e))

            await asyncio.sleep(scheduled_task.interval.total_seconds())
