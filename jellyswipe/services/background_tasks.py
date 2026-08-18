"""Background task registry — a visible, shutdown-aware task tracking seam.

Introduces an explicit place for long-running background work (e.g. the
room-cleanup after the grace period) that was previously started with a bare
fire-and-forget ``asyncio.create_task`` inside service methods. Making it a
first-class, trackable registry means the work is observable in tests and can
be awaited/cancelled cleanly when the application shuts down (issue #295).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable

logger = logging.getLogger(__name__)


class BackgroundTaskRegistry:
    """Tracks background asyncio tasks so they can be awaited or cancelled.

    Tasks are wrapped so an unexpected failure is logged rather than silently
    swallowed, and ``shutdown()`` cancels and drains whatever is still pending
    on application teardown.
    """

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def schedule(self, coro: Awaitable[None]) -> asyncio.Task:
        """Run ``coro`` in the background and track it until it completes."""
        task = asyncio.get_running_loop().create_task(self._run(coro))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _run(self, coro: Awaitable[None]) -> None:
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("background task failed")

    @property
    def pending(self) -> int:
        """Number of tasks still running."""
        return len(self._tasks)

    async def shutdown(self) -> None:
        """Cancel all pending tasks and await their completion."""
        if not self._tasks:
            return
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()


# Module-level singleton shared by the app. Tests inject their own registry.
background_task_registry = BackgroundTaskRegistry()


__all__ = ["BackgroundTaskRegistry", "background_task_registry"]
