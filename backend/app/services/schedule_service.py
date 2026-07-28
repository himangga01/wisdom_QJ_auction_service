from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, time, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.url_identity import normalize_source_url
from app.models import CrawlRun, CrawlSchedule, TrackedSource
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleDelete,
    SchedulePatch,
    ScheduleResponse,
    ScheduleRun,
    ScheduleRuns,
)
from app.services.query_service import seoul_iso


class ScheduleNotFoundError(LookupError):
    code = "dataset_not_found"


class ScheduleSourceNotFoundError(LookupError):
    code = "dataset_not_found"


class ScheduleConflictError(RuntimeError):
    code = "schedule_exists"


class ScheduleDeleteConflictError(RuntimeError):
    code = "schedule_must_be_disabled"


class SourceLockManager(Protocol):
    async def acquire(
        self, source_id: UUID, *, ttl_seconds: int = 600
    ) -> Any | None: ...

    async def release(self, lock: Any) -> None: ...


def calculate_next_run(
    cadence: str,
    time_of_day: time,
    after: datetime,
    *,
    timezone_name: str = "Asia/Seoul",
    weekday: int | None = None,
) -> datetime:
    if after.tzinfo is None or after.utcoffset() is None:
        raise ValueError("after must be timezone-aware")
    if cadence not in {"daily", "weekdays", "weekly"}:
        raise ValueError("unsupported cadence")
    if cadence == "weekly" and weekday is None:
        raise ValueError("weekly cadence requires weekday")

    local_zone = ZoneInfo(timezone_name)
    local_after = after.astimezone(local_zone)
    for offset in range(8):
        candidate_date = local_after.date() + timedelta(days=offset)
        if cadence == "weekdays" and candidate_date.weekday() >= 5:
            continue
        if cadence == "weekly" and candidate_date.weekday() != weekday:
            continue
        candidate = datetime.combine(candidate_date, time_of_day, tzinfo=local_zone)
        if candidate > local_after:
            return candidate
    raise RuntimeError("next schedule occurrence could not be calculated")


async def enqueue_with_source_lock(
    lock_manager: SourceLockManager,
    source_id: UUID,
    enqueue: Callable[[], Awaitable[Any]],
) -> bool:
    lock = await lock_manager.acquire(source_id, ttl_seconds=600)
    if lock is None:
        return False
    try:
        await enqueue()
    finally:
        await lock_manager.release(lock)
    return True


class ScheduleService:
    def __init__(self, session: AsyncSession, actor_user_id: UUID) -> None:
        self.session = session
        self.actor_user_id = actor_user_id

    async def _source(self, payload: ScheduleCreate) -> TrackedSource:
        source: TrackedSource | None = None
        if payload.source_id is not None:
            source = await self.session.scalar(
                select(TrackedSource).where(
                    TrackedSource.id == payload.source_id,
                    TrackedSource.owner_user_id == self.actor_user_id,
                )
            )
            if source is None:
                raise ScheduleSourceNotFoundError(
                    "소유한 활성 조사 URL을 찾을 수 없습니다."
                )
        elif payload.source_url:
            identity = normalize_source_url(payload.source_url)
            source = await self.session.scalar(
                select(TrackedSource).where(
                    TrackedSource.owner_user_id == self.actor_user_id,
                    TrackedSource.url_hash == identity.url_hash,
                )
            )
        if source is None or not source.is_active:
            raise ScheduleSourceNotFoundError(
                "먼저 조사해 저장된 활성 URL만 스케줄에 연결할 수 있습니다."
            )
        if payload.source_url:
            identity = normalize_source_url(payload.source_url)
            if source.url_hash != identity.url_hash:
                raise ScheduleSourceNotFoundError("sourceId와 sourceUrl이 일치하지 않습니다.")
        return source

    @staticmethod
    def _response(schedule: CrawlSchedule, source: TrackedSource) -> ScheduleResponse:
        return ScheduleResponse(
            id=schedule.id,
            source_id=source.id,
            source_url=source.normalized_url,
            cadence=schedule.cadence,
            time_of_day=schedule.time_of_day,
            timezone=schedule.timezone,
            weekday=schedule.weekday,
            enabled=schedule.enabled,
            collect_broker_details=schedule.collect_broker_details,
            interaction_delay_preset=schedule.interaction_delay_preset,
            next_run_at=seoul_iso(schedule.next_run_at),
        )

    async def list(self) -> list[ScheduleResponse]:
        rows = (
            await self.session.execute(
                select(CrawlSchedule, TrackedSource)
                .join(TrackedSource, TrackedSource.id == CrawlSchedule.source_id)
                .where(TrackedSource.owner_user_id == self.actor_user_id)
                .order_by(CrawlSchedule.next_run_at.asc(), CrawlSchedule.id.asc())
            )
        ).all()
        return [self._response(schedule, source) for schedule, source in rows]

    async def _get(self, schedule_id: UUID) -> CrawlSchedule:
        schedule = await self.session.scalar(
            select(CrawlSchedule)
            .join(TrackedSource, TrackedSource.id == CrawlSchedule.source_id)
            .where(
                CrawlSchedule.id == schedule_id,
                TrackedSource.owner_user_id == self.actor_user_id,
            )
        )
        if schedule is None:
            raise ScheduleNotFoundError("스케줄을 찾을 수 없습니다.")
        return schedule

    async def create(
        self, payload: ScheduleCreate, *, now: datetime | None = None
    ) -> ScheduleResponse:
        source = await self._source(payload)
        existing = await self.session.scalar(
            select(CrawlSchedule).where(CrawlSchedule.source_id == source.id)
        )
        if existing is not None:
            raise ScheduleConflictError("이 URL에는 이미 스케줄이 있습니다.")
        current = now or datetime.now(timezone.utc)
        next_run_at = calculate_next_run(
            payload.cadence,
            payload.time_of_day,
            current,
            timezone_name=payload.timezone,
            weekday=payload.weekday,
        ).astimezone(timezone.utc)
        schedule = CrawlSchedule(
            source_id=source.id,
            cadence=payload.cadence,
            time_of_day=payload.time_of_day,
            timezone=payload.timezone,
            weekday=payload.weekday if payload.cadence == "weekly" else None,
            enabled=payload.enabled,
            collect_broker_details=payload.collect_broker_details,
            interaction_delay_preset=payload.interaction_delay_preset,
            next_run_at=next_run_at,
        )
        self.session.add(schedule)
        try:
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise ScheduleConflictError("이 URL에는 이미 스케줄이 있습니다.") from error
        await self.session.refresh(schedule)
        return self._response(schedule, source)

    async def patch(
        self,
        schedule_id: UUID,
        payload: SchedulePatch,
        *,
        now: datetime | None = None,
    ) -> ScheduleResponse:
        schedule = await self._get(schedule_id)
        source = await self.session.get(TrackedSource, schedule.source_id)
        if source is None:
            raise ScheduleSourceNotFoundError("연결된 URL을 찾을 수 없습니다.")

        final_cadence = payload.cadence or schedule.cadence
        if "weekday" in payload.model_fields_set:
            final_weekday = payload.weekday
        else:
            final_weekday = schedule.weekday
        if final_cadence == "weekly" and final_weekday is None:
            raise ValueError("weekly 스케줄에는 weekday가 필요합니다.")
        if final_cadence != "weekly":
            final_weekday = None

        schedule.cadence = final_cadence
        schedule.weekday = final_weekday
        if payload.time_of_day is not None:
            schedule.time_of_day = payload.time_of_day
        if payload.timezone is not None:
            schedule.timezone = payload.timezone
        if payload.enabled is not None:
            schedule.enabled = payload.enabled
        if payload.collect_broker_details is not None:
            schedule.collect_broker_details = payload.collect_broker_details
        if payload.interaction_delay_preset is not None:
            schedule.interaction_delay_preset = payload.interaction_delay_preset

        scheduling_fields = {"cadence", "time_of_day", "timezone", "weekday"}
        if payload.model_fields_set & scheduling_fields or payload.enabled is True:
            schedule.next_run_at = calculate_next_run(
                schedule.cadence,
                schedule.time_of_day,
                now or datetime.now(timezone.utc),
                timezone_name=schedule.timezone,
                weekday=schedule.weekday,
            ).astimezone(timezone.utc)
        await self.session.commit()
        await self.session.refresh(schedule)
        return self._response(schedule, source)

    async def delete(self, schedule_id: UUID, *, hard: bool) -> ScheduleDelete:
        schedule = await self._get(schedule_id)
        if hard:
            if schedule.enabled:
                raise ScheduleDeleteConflictError(
                    "활성 스케줄은 먼저 비활성화한 뒤 삭제해야 합니다."
                )
            await self.session.delete(schedule)
            action = "deleted"
        else:
            schedule.enabled = False
            action = "disabled"
        await self.session.commit()
        return ScheduleDelete(id=schedule_id, action=action)

    async def runs(self, schedule_id: UUID, *, limit: int = 20) -> ScheduleRuns:
        schedule = await self._get(schedule_id)
        runs = list(
            (
                await self.session.scalars(
                    select(CrawlRun)
                    .where(CrawlRun.source_id == schedule.source_id)
                    .order_by(CrawlRun.created_at.desc())
                    .limit(limit)
                )
            ).all()
        )
        return ScheduleRuns(
            schedule_id=schedule.id,
            items=[
                ScheduleRun(
                    run_id=run.id,
                    status=run.status,
                    stage=run.stage,
                    progress=run.progress,
                    error_code=run.error_code,
                    collect_broker_details=run.collect_broker_details,
                    interaction_delay_preset=run.interaction_delay_preset,
                    created_at=seoul_iso(run.created_at),
                    started_at=seoul_iso(run.started_at) if run.started_at else None,
                    finished_at=seoul_iso(run.finished_at) if run.finished_at else None,
                )
                for run in runs
            ],
        )
