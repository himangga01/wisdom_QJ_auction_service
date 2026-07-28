from __future__ import annotations

from datetime import datetime, timezone
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crawler.browser_readiness import BrowserStatus
from app.models import CrawlRun, CrawlSchedule, TrackedSource
from app.services.analysis_service import AnalysisService, CrawlTaskDispatcher
from app.services.schedule_service import (
    SourceLockManager,
    calculate_next_run,
    enqueue_with_source_lock,
)

logger = logging.getLogger(__name__)


class ScheduleRunnerService:
    """Background-only schedule runner that derives ownership from each source."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue_due(
        self,
        *,
        lock_manager: SourceLockManager,
        dispatcher: CrawlTaskDispatcher,
        browser_status: BrowserStatus = "ready",
        now: datetime | None = None,
    ) -> dict[str, int]:
        current = now or datetime.now(timezone.utc)
        rows = (
            await self.session.execute(
                select(CrawlSchedule, TrackedSource)
                .join(TrackedSource, TrackedSource.id == CrawlSchedule.source_id)
                .where(
                    CrawlSchedule.enabled.is_(True),
                    CrawlSchedule.next_run_at <= current,
                    TrackedSource.is_active.is_(True),
                )
                .order_by(CrawlSchedule.next_run_at.asc())
            )
        ).all()
        counts = {
            "due": len(rows),
            "enqueued": 0,
            "deduplicated": 0,
            "locked": 0,
            "failed": 0,
        }
        analysis = AnalysisService(self.session, dispatcher)
        for schedule, source in rows:
            if browser_status == "unavailable":
                self.session.add(
                    CrawlRun(
                        source_id=source.id,
                        status="failed",
                        stage="url",
                        progress=0,
                        error_code="browser_unavailable",
                        collect_broker_details=schedule.collect_broker_details,
                        interaction_delay_preset=schedule.interaction_delay_preset,
                        finished_at=current,
                    )
                )
                counts["failed"] += 1
                schedule.next_run_at = calculate_next_run(
                    schedule.cadence,
                    schedule.time_of_day,
                    current,
                    timezone_name=schedule.timezone,
                    weekday=schedule.weekday,
                ).astimezone(timezone.utc)
                await self.session.commit()
                continue

            created = False

            async def enqueue() -> None:
                nonlocal created
                _, created = await analysis.create_for_source(
                    source.id,
                    collect_broker_details=schedule.collect_broker_details,
                    interaction_delay_preset=schedule.interaction_delay_preset,
                )

            try:
                acquired = await enqueue_with_source_lock(
                    lock_manager,
                    source.id,
                    enqueue,
                )
            except Exception:
                logger.exception(
                    "Scheduled crawl dispatch failed",
                    extra={
                        "schedule_id": str(schedule.id),
                        "source_id": str(source.id),
                    },
                )
                self.session.add(
                    CrawlRun(
                        source_id=source.id,
                        status="failed",
                        stage="url",
                        progress=0,
                        error_code="schedule_dispatch_failed",
                        collect_broker_details=schedule.collect_broker_details,
                        interaction_delay_preset=schedule.interaction_delay_preset,
                        finished_at=current,
                    )
                )
                counts["failed"] += 1
                schedule.next_run_at = calculate_next_run(
                    schedule.cadence,
                    schedule.time_of_day,
                    current,
                    timezone_name=schedule.timezone,
                    weekday=schedule.weekday,
                ).astimezone(timezone.utc)
                await self.session.commit()
                continue
            if not acquired:
                counts["locked"] += 1
                continue
            counts["enqueued" if created else "deduplicated"] += 1
            schedule.next_run_at = calculate_next_run(
                schedule.cadence,
                schedule.time_of_day,
                current,
                timezone_name=schedule.timezone,
                weekday=schedule.weekday,
            ).astimezone(timezone.utc)
            await self.session.commit()
        return counts
