import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import CrawlRun, TrackedSource
from app.services.analysis_service import AnalysisOptionConflictError, AnalysisService


class ConcurrentRequestSession:
    def __init__(self, source: TrackedSource, active_run: CrawlRun) -> None:
        self.scalar_results = iter([None, source, None, active_run])
        self.flush_conflict = True
        self.commit_conflict = True
        self.rollback_count = 0

    async def scalar(self, _statement):
        return next(self.scalar_results)

    def add(self, _instance) -> None:
        return None

    async def flush(self) -> None:
        if self.flush_conflict:
            self.flush_conflict = False
            raise IntegrityError("INSERT tracked_sources", {}, Exception("url_hash"))

    async def commit(self) -> None:
        if self.commit_conflict:
            self.commit_conflict = False
            raise IntegrityError("INSERT crawl_runs", {}, Exception("active source"))

    async def rollback(self) -> None:
        self.rollback_count += 1


class RecordingDispatcher:
    def __init__(self) -> None:
        self.enqueued: list = []

    def enqueue(self, run_id) -> None:
        self.enqueued.append(run_id)

    def cancel(self, _run_id) -> None:
        return None


def test_concurrent_unique_conflicts_return_the_existing_active_run() -> None:
    actor_user_id = uuid4()
    source = TrackedSource(
        id=uuid4(),
        source_url="https://fin.land.naver.com/map?a=1",
        normalized_url="https://fin.land.naver.com/map?a=1",
        url_hash="a" * 64,
        owner_user_id=actor_user_id,
    )
    active_run = CrawlRun(
        id=uuid4(),
        source_id=source.id,
        status="queued",
        stage="url",
        progress=0,
        collect_broker_details=True,
        interaction_delay_preset="normal",
    )
    session = ConcurrentRequestSession(source, active_run)
    dispatcher = RecordingDispatcher()

    run, created = asyncio.run(
        AnalysisService(session, dispatcher).create_for_user(
            actor_user_id,
            "https://fin.land.naver.com/map?a=1"
        )
    )

    assert (run, created) == (active_run, False)
    assert session.rollback_count == 2
    assert dispatcher.enqueued == []


class ExistingSourceSession:
    def __init__(self, source: TrackedSource, active_run: CrawlRun | None) -> None:
        self.source = source
        self.active_run = active_run
        self.added: list[object] = []

    async def scalar(self, _statement):
        if self.source is not None:
            source, self.source = self.source, None
            return source
        return self.active_run

    def add(self, instance) -> None:
        self.added.append(instance)

    async def commit(self) -> None:
        return None

    async def refresh(self, instance) -> None:
        if instance.id is None:
            instance.id = uuid4()


def test_analysis_option_is_saved_and_active_run_requires_same_option() -> None:
    actor_user_id = uuid4()
    source = TrackedSource(
        id=uuid4(),
        source_url="https://fin.land.naver.com/map?a=1",
        normalized_url="https://fin.land.naver.com/map?a=1",
        url_hash="a" * 64,
        owner_user_id=actor_user_id,
    )
    dispatcher = RecordingDispatcher()
    session = ExistingSourceSession(source, None)

    run, created = asyncio.run(
        AnalysisService(session, dispatcher).create_for_user(
            actor_user_id,
            source.source_url,
            collect_broker_details=False,
            interaction_delay_preset="fast",
        )
    )

    assert created is True
    assert run.collect_broker_details is False
    assert run.interaction_delay_preset == "fast"
    assert dispatcher.enqueued == [run.id]

    active_run = CrawlRun(
        id=uuid4(),
        source_id=source.id,
        status="queued",
        stage="url",
        progress=0,
        collect_broker_details=False,
        interaction_delay_preset="fast",
    )
    reused, created = asyncio.run(
        AnalysisService(
            ExistingSourceSession(source, active_run),
            dispatcher,
        ).create_for_user(
            actor_user_id,
            source.source_url,
            collect_broker_details=False,
            interaction_delay_preset="fast",
        )
    )
    assert (reused, created) == (active_run, False)

    with pytest.raises(AnalysisOptionConflictError):
        asyncio.run(
            AnalysisService(
                ExistingSourceSession(source, active_run),
                dispatcher,
            ).create_for_user(
                actor_user_id,
                source.source_url,
                collect_broker_details=True,
                interaction_delay_preset="fast",
            )
        )

    with pytest.raises(AnalysisOptionConflictError):
        asyncio.run(
            AnalysisService(
                ExistingSourceSession(source, active_run),
                dispatcher,
            ).create_for_user(
                actor_user_id,
                source.source_url,
                collect_broker_details=False,
                interaction_delay_preset="careful",
            )
        )
