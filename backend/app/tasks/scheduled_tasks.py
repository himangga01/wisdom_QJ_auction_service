import asyncio
from datetime import datetime, timezone

from app.core.database import dispose_database, get_session_factory
from app.core.config import get_settings
from app.core.locks import RedisSourceLockManager
from app.crawler.browser_readiness import probe_browser_cdp
from app.services.analysis_service import CeleryCrawlTaskDispatcher
from app.services.schedule_runner_service import ScheduleRunnerService
from app.tasks.crawl_tasks import celery_app


celery_app.conf.beat_schedule = {
    **(celery_app.conf.beat_schedule or {}),
    "enqueue-due-crawl-schedules-every-minute": {
        "task": "app.tasks.scheduled_tasks.enqueue_due_schedules",
        "schedule": 60.0,
    },
}


@celery_app.task(name="app.tasks.scheduled_tasks.enqueue_due_schedules")
def enqueue_due_schedules() -> dict[str, int]:
    return asyncio.run(_enqueue_due_and_dispose())


async def _enqueue_due_and_dispose() -> dict[str, int]:
    lock_manager = RedisSourceLockManager()
    try:
        browser_status = await probe_browser_cdp(get_settings().crawler_cdp_url)
        async with get_session_factory()() as session:
            return await ScheduleRunnerService(session).enqueue_due(
                lock_manager=lock_manager,
                dispatcher=CeleryCrawlTaskDispatcher(),
                browser_status=browser_status,
                now=datetime.now(timezone.utc),
            )
    finally:
        await lock_manager.aclose()
        await dispose_database()
