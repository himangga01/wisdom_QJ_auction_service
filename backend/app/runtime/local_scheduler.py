from __future__ import annotations

import asyncio

from app.core.database import get_session_factory
from app.core.logging import log_run_event
from app.services.schedule_service import ScheduleService

from .local_dispatcher import get_local_dispatcher
from .local_locks import get_local_source_lock_manager


async def run_local_schedule_cycle() -> dict[str, int]:
    async with get_session_factory()() as session:
        return await ScheduleService(session).enqueue_due(
            lock_manager=get_local_source_lock_manager(),
            dispatcher=get_local_dispatcher(),
        )


async def local_scheduler_loop(
    stop_event: asyncio.Event,
    interval_seconds: float = 60,
) -> None:
    while not stop_event.is_set():
        try:
            await run_local_schedule_cycle()
        except asyncio.CancelledError:
            raise
        except Exception:
            log_run_event(
                "crawl_metric",
                error="local_scheduler_cycle_failed",
                level="error",
            )

        if stop_event.is_set():
            break
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            pass
