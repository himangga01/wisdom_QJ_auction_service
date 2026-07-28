from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crawler.delay import (
    DEFAULT_INTERACTION_DELAY_PRESET,
    InteractionDelayPreset,
)
from app.domain.url_identity import normalize_source_url
from app.models import Apartment, ApartmentSnapshot, CrawlRun, TrackedSource

ACTIVE_STATUSES = ("queued", "running")
TERMINAL_STATUSES = ("completed", "partial", "failed", "blocked", "cancelled")


class AnalysisNotFoundError(LookupError):
    code = "dataset_not_found"


class AnalysisNotReadyError(RuntimeError):
    code = "analysis_not_ready"


class AnalysisCannotCancelError(RuntimeError):
    code = "analysis_cannot_cancel"


class AnalysisOptionConflictError(RuntimeError):
    code = "analysis_option_conflict"


class QueueUnavailableError(RuntimeError):
    code = "queue_unavailable"


class CrawlTaskDispatcher(Protocol):
    def enqueue(self, run_id: UUID) -> None: ...

    def cancel(self, run_id: UUID) -> None: ...


class CeleryCrawlTaskDispatcher:
    def enqueue(self, run_id: UUID) -> None:
        from app.tasks.crawl_tasks import crawl_run

        crawl_run.apply_async(args=[str(run_id)], task_id=str(run_id))

    def cancel(self, run_id: UUID) -> None:
        from app.tasks.crawl_tasks import celery_app

        celery_app.control.revoke(str(run_id), terminate=False)


class AnalysisService:
    def __init__(self, session: AsyncSession, dispatcher: CrawlTaskDispatcher) -> None:
        self.session = session
        self.dispatcher = dispatcher

    async def _source_by_hash(
        self,
        actor_user_id: UUID,
        url_hash: str,
    ) -> TrackedSource | None:
        return await self.session.scalar(
            select(TrackedSource).where(
                TrackedSource.owner_user_id == actor_user_id,
                TrackedSource.url_hash == url_hash,
            )
        )

    async def _active_run(self, source_id: UUID) -> CrawlRun | None:
        return await self.session.scalar(
            select(CrawlRun)
            .where(
                CrawlRun.source_id == source_id,
                CrawlRun.status.in_(ACTIVE_STATUSES),
            )
            .order_by(CrawlRun.created_at.desc())
        )

    @staticmethod
    def _deduplicated_run(
        active_run: CrawlRun,
        collect_broker_details: bool,
        interaction_delay_preset: InteractionDelayPreset,
    ) -> tuple[CrawlRun, bool]:
        if (
            active_run.collect_broker_details != collect_broker_details
            or active_run.interaction_delay_preset != interaction_delay_preset
        ):
            raise AnalysisOptionConflictError(
                "An active analysis already exists with different collection options."
            )
        return active_run, False

    async def _create_for_source(
        self,
        source: TrackedSource,
        *,
        collect_broker_details: bool,
        interaction_delay_preset: InteractionDelayPreset,
    ) -> tuple[CrawlRun, bool]:
        active_run = await self._active_run(source.id)
        if active_run is not None:
            return self._deduplicated_run(
                active_run,
                collect_broker_details,
                interaction_delay_preset,
            )

        run = CrawlRun(
            source_id=source.id,
            status="queued",
            stage="url",
            progress=0,
            collect_broker_details=collect_broker_details,
            interaction_delay_preset=interaction_delay_preset,
        )
        self.session.add(run)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            active_run = await self._active_run(source.id)
            if active_run is None:
                raise
            return self._deduplicated_run(
                active_run,
                collect_broker_details,
                interaction_delay_preset,
            )
        await self.session.refresh(run)

        try:
            self.dispatcher.enqueue(run.id)
        except Exception as exc:
            run.status = "failed"
            run.error_code = "queue_unavailable"
            run.finished_at = datetime.now(timezone.utc)
            await self.session.commit()
            raise QueueUnavailableError("조사 작업 큐에 연결할 수 없습니다.") from exc
        return run, True

    async def create_for_user(
        self,
        actor_user_id: UUID,
        source_url: str,
        *,
        collect_broker_details: bool = True,
        interaction_delay_preset: InteractionDelayPreset = (
            DEFAULT_INTERACTION_DELAY_PRESET
        ),
    ) -> tuple[CrawlRun, bool]:
        identity = normalize_source_url(source_url)
        source = await self._source_by_hash(actor_user_id, identity.url_hash)
        if source is None:
            source = TrackedSource(
                source_url=identity.source_url,
                normalized_url=identity.normalized_url,
                url_hash=identity.url_hash,
                owner_user_id=actor_user_id,
            )
            self.session.add(source)
            try:
                await self.session.flush()
            except IntegrityError:
                await self.session.rollback()
                source = await self._source_by_hash(
                    actor_user_id,
                    identity.url_hash,
                )
                if source is None:
                    raise
        return await self._create_for_source(
            source,
            collect_broker_details=collect_broker_details,
            interaction_delay_preset=interaction_delay_preset,
        )

    async def create_for_source(
        self,
        source_id: UUID,
        *,
        collect_broker_details: bool = True,
        interaction_delay_preset: InteractionDelayPreset = (
            DEFAULT_INTERACTION_DELAY_PRESET
        ),
    ) -> tuple[CrawlRun, bool]:
        source = await self.session.scalar(
            select(TrackedSource).where(
                TrackedSource.id == source_id,
                TrackedSource.is_active.is_(True),
            )
        )
        if source is None:
            raise AnalysisNotFoundError("조사 source를 찾을 수 없습니다.")
        return await self._create_for_source(
            source,
            collect_broker_details=collect_broker_details,
            interaction_delay_preset=interaction_delay_preset,
        )

    async def get(self, actor_user_id: UUID, run_id: UUID) -> CrawlRun:
        run = await self.session.scalar(
            select(CrawlRun)
            .join(TrackedSource, TrackedSource.id == CrawlRun.source_id)
            .where(
                CrawlRun.id == run_id,
                TrackedSource.owner_user_id == actor_user_id,
            )
        )
        if run is None:
            raise AnalysisNotFoundError("분석 작업을 찾을 수 없습니다.")
        return run

    async def result(
        self,
        actor_user_id: UUID,
        run_id: UUID,
    ) -> tuple[CrawlRun, Apartment, ApartmentSnapshot]:
        run = await self.get(actor_user_id, run_id)
        if run.status not in ("completed", "partial"):
            raise AnalysisNotReadyError("분석 작업이 아직 완료되지 않았습니다.")

        row = (
            await self.session.execute(
                select(Apartment, ApartmentSnapshot)
                .join(ApartmentSnapshot, ApartmentSnapshot.apartment_id == Apartment.id)
                .where(ApartmentSnapshot.run_id == run.id)
            )
        ).first()
        if row is None:
            raise AnalysisNotReadyError("완료된 아파트 결과가 없습니다.")
        return run, row[0], row[1]

    async def cancel(self, actor_user_id: UUID, run_id: UUID) -> CrawlRun:
        run = await self.get(actor_user_id, run_id)
        if run.status != "queued":
            raise AnalysisCannotCancelError("대기 중인 작업만 취소할 수 있습니다.")
        self.dispatcher.cancel(run.id)
        run.status = "cancelled"
        run.finished_at = datetime.now(timezone.utc)
        await self.session.commit()
        return run
