import asyncio
from collections import Counter
from datetime import datetime, timezone
from time import monotonic
from uuid import UUID

from celery import Celery
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.database import dispose_database, get_session_factory
from app.core.logging import configure_logging, log_run_event
from app.crawler.browser import PlaywrightNaverLandCollector, ProgressCallback
from app.crawler.delay import humanized_delay_for_preset
from app.crawler.errors import CrawlError
from app.crawler.scope import CrawlScope
from app.crawler.selectors import SELECTOR_VERSION
from app.models import CrawlRun, TrackedSource
from app.services.persistence_service import (
    PersistenceError,
    PersistenceService,
    mark_run_terminal,
)

settings = get_settings()
configure_logging()
celery_app = Celery(
    "wisdom_qj_auction",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.task_track_started = True
celery_app.conf.worker_concurrency = settings.crawl_concurrency
celery_app.conf.imports = ("app.tasks.scheduled_tasks",)


def _collector_for_run(
    interaction_delay_preset: str,
    progress: ProgressCallback | None,
) -> PlaywrightNaverLandCollector:
    return PlaywrightNaverLandCollector(
        settings,
        progress=progress,
        delay=humanized_delay_for_preset(interaction_delay_preset),
    )


@celery_app.task(name="app.tasks.crawl_tasks.crawl_run")
def crawl_run(run_id: str) -> dict[str, str]:
    """Celery sync boundary; browser and SQLAlchemy work run on one task-local loop."""
    try:
        parsed_run_id = UUID(run_id)
    except ValueError:
        return {"runId": run_id, "status": "failed", "errorCode": "invalid_run_id"}
    return asyncio.run(_run_and_dispose(parsed_run_id))


async def _claim_run(
    run_id: UUID,
) -> tuple[str, str | None, UUID | None, bool, str | None]:
    async with get_session_factory()() as session:
        result = await session.execute(
            update(CrawlRun)
            .where(CrawlRun.id == run_id, CrawlRun.status == "queued")
            .values(
                status="running",
                stage="url",
                progress=1,
                started_at=datetime.now(timezone.utc),
                selector_version=SELECTOR_VERSION,
            )
        )
        await session.commit()
        if result.rowcount != 1:
            existing = (
                await session.execute(
                    select(
                        CrawlRun.status,
                        CrawlRun.source_id,
                        CrawlRun.collect_broker_details,
                        CrawlRun.interaction_delay_preset,
                    ).where(
                        CrawlRun.id == run_id
                    )
                )
            ).one_or_none()
            if existing is None:
                return "failed", None, None, True, None
            return (
                existing.status,
                None,
                existing.source_id,
                existing.collect_broker_details,
                existing.interaction_delay_preset,
            )
        source = (
            await session.execute(
                select(
                    CrawlRun.source_id,
                    TrackedSource.normalized_url,
                    CrawlRun.collect_broker_details,
                    CrawlRun.interaction_delay_preset,
                )
                .join(TrackedSource, CrawlRun.source_id == TrackedSource.id)
                .where(CrawlRun.id == run_id)
            )
        ).one_or_none()
        if source is None:
            return "failed", None, None, True, None
        return (
            "running",
            source.normalized_url,
            source.source_id,
            source.collect_broker_details,
            source.interaction_delay_preset,
        )


async def _update_progress(run_id: UUID, stage: str, progress: int) -> None:
    async with get_session_factory()() as session:
        await session.execute(
            update(CrawlRun)
            .where(CrawlRun.id == run_id, CrawlRun.status == "running")
            .values(stage=stage, progress=progress, selector_version=SELECTOR_VERSION)
        )
        await session.commit()


async def _finish_failure(
    run_id: UUID, *, status: str, error_code: str, stage: str
) -> None:
    async with get_session_factory()() as session:
        await mark_run_terminal(
            session,
            run_id=run_id,
            status=status,
            error_code=error_code,
            stage=stage,
        )


async def _execute_pipeline(run_id: UUID) -> dict[str, str]:
    started_at = monotonic()
    (
        status,
        source_url,
        source_id,
        collect_broker_details,
        interaction_delay_preset,
    ) = await _claim_run(run_id)
    if status != "running" or source_url is None:
        return {"runId": str(run_id), "status": status}

    current_stage = "url"
    log_run_event(
        "crawl_started",
        run_id=run_id,
        source_id=source_id,
        stage=current_stage,
        duration=0,
    )

    async def progress(stage: str, value: int) -> None:
        nonlocal current_stage
        current_stage = stage
        await _update_progress(run_id, stage, value)
        log_run_event(
            "crawl_stage",
            run_id=run_id,
            source_id=source_id,
            stage=stage,
            duration=round((monotonic() - started_at) * 1000),
        )

    try:
        if interaction_delay_preset is None:
            raise ValueError("running crawl is missing interaction delay preset")
        collector = _collector_for_run(interaction_delay_preset, progress)
        payload = await collector.collect(
            source_url,
            scope=CrawlScope.full(collect_broker_details=collect_broker_details),
        )
        warning_counts = Counter(payload.warnings)
        for listing in payload.listings:
            warning_counts.update(listing.warnings)
        for error_code, metric_count in sorted(warning_counts.items()):
            log_run_event(
                "crawl_metric",
                run_id=run_id,
                source_id=source_id,
                stage=current_stage,
                count=metric_count,
                error=error_code,
                duration=round((monotonic() - started_at) * 1000),
                level="warning",
            )
        await progress("compare", 80)
        current_stage = "save"
        async with get_session_factory()() as session:
            outcome = await PersistenceService(session).persist(run_id, payload)
        log_run_event(
            "crawl_finished",
            run_id=run_id,
            source_id=source_id,
            stage="save",
            count=outcome.listing_count,
            duration=round((monotonic() - started_at) * 1000),
            level="warning" if outcome.status == "partial" else "info",
        )
        return {
            "runId": str(run_id),
            "status": outcome.status,
            "apartmentId": str(outcome.apartment_id) if outcome.apartment_id else "",
        }
    except CrawlError as exc:
        await _finish_failure(
            run_id,
            status=exc.run_status,
            error_code=exc.code,
            stage=current_stage,
        )
        log_run_event(
            "crawl_finished",
            run_id=run_id,
            source_id=source_id,
            stage=current_stage,
            count=0,
            error=exc.code,
            duration=round((monotonic() - started_at) * 1000),
            level="warning" if exc.run_status == "blocked" else "error",
        )
        return {"runId": str(run_id), "status": exc.run_status, "errorCode": exc.code}
    except PersistenceError as exc:
        await _finish_failure(
            run_id, status="failed", error_code=exc.code, stage="save"
        )
        log_run_event(
            "crawl_finished",
            run_id=run_id,
            source_id=source_id,
            stage="save",
            count=0,
            error=exc.code,
            duration=round((monotonic() - started_at) * 1000),
            level="error",
        )
        return {"runId": str(run_id), "status": "failed", "errorCode": exc.code}
    except Exception:
        await _finish_failure(
            run_id,
            status="failed",
            error_code="unexpected_crawl_error",
            stage=current_stage,
        )
        log_run_event(
            "crawl_finished",
            run_id=run_id,
            source_id=source_id,
            stage=current_stage,
            count=0,
            error="unexpected_crawl_error",
            duration=round((monotonic() - started_at) * 1000),
            level="error",
        )
        return {
            "runId": str(run_id),
            "status": "failed",
            "errorCode": "unexpected_crawl_error",
        }


async def _run_and_dispose(run_id: UUID) -> dict[str, str]:
    try:
        return await _execute_pipeline(run_id)
    finally:
        await dispose_database()
