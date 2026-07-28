import asyncio
from datetime import datetime, time, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import app.services.schedule_service as schedule_module
from app.models import CrawlRun, CrawlSchedule, TrackedSource
from app.schemas.schedule import ScheduleCreate, SchedulePatch
from app.services.schedule_service import (
    ScheduleService,
    calculate_next_run,
    enqueue_with_source_lock,
)

SEOUL = ZoneInfo("Asia/Seoul")


def test_calculate_next_run_for_daily_weekdays_and_weekly() -> None:
    friday = datetime(2026, 7, 24, 10, 0, tzinfo=SEOUL)

    assert calculate_next_run("daily", time(9), friday) == datetime(
        2026, 7, 25, 9, 0, tzinfo=SEOUL
    )
    assert calculate_next_run("weekdays", time(9), friday) == datetime(
        2026, 7, 27, 9, 0, tzinfo=SEOUL
    )
    assert calculate_next_run("weekly", time(9), friday, weekday=2) == datetime(
        2026, 7, 29, 9, 0, tzinfo=SEOUL
    )


class DeniedLockManager:
    async def acquire(self, _source_id, *, ttl_seconds=600):
        return None

    async def release(self, _lock):
        raise AssertionError("a missing lock must not be released")


def test_lock_failure_never_calls_enqueue() -> None:
    called = False

    async def enqueue() -> None:
        nonlocal called
        called = True

    result = asyncio.run(
        enqueue_with_source_lock(DeniedLockManager(), uuid4(), enqueue)
    )

    assert result is False
    assert called is False


class Rows:
    def __init__(self, values) -> None:
        self.values = list(values)

    def all(self):
        return list(self.values)


class ScheduleSession:
    def __init__(
        self,
        source: TrackedSource,
        *,
        schedule: CrawlSchedule | None = None,
        runs=(),
        due_rows=(),
    ) -> None:
        self.source = source
        self.schedule = schedule
        self.runs = list(runs)
        self.due_rows = list(due_rows)

    async def get(self, model, identity):
        if model is TrackedSource and identity == self.source.id:
            return self.source
        if model is CrawlSchedule and self.schedule and identity == self.schedule.id:
            return self.schedule
        return None

    async def scalar(self, _statement):
        return None

    def add(self, instance) -> None:
        instance.id = instance.id or uuid4()
        self.schedule = instance

    async def commit(self) -> None:
        return None

    async def refresh(self, _instance) -> None:
        return None

    async def scalars(self, _statement):
        return Rows(self.runs)

    async def execute(self, _statement):
        return Rows(self.due_rows)


def _source() -> TrackedSource:
    return TrackedSource(
        id=uuid4(),
        source_url="https://fin.land.naver.com/map?a=1",
        normalized_url="https://fin.land.naver.com/map?a=1",
        url_hash="a" * 64,
        is_active=True,
    )


def test_schedule_create_patch_and_history_preserve_collection_option() -> None:
    source = _source()
    session = ScheduleSession(source)
    service = ScheduleService(session)
    default_schedule = ScheduleCreate(
        sourceId=source.id,
        cadence="daily",
        time=time(9),
    )
    assert default_schedule.interaction_delay_preset == "normal"

    response = asyncio.run(
        service.create(
            ScheduleCreate(
                sourceId=source.id,
                cadence="daily",
                time=time(9),
                collectBrokerDetails=False,
                interactionDelayPreset="fast",
            ),
            now=datetime(2026, 7, 28, tzinfo=SEOUL),
        )
    )
    assert response.collect_broker_details is False
    assert response.interaction_delay_preset == "fast"

    patched = asyncio.run(
        service.patch(
            session.schedule.id,
            SchedulePatch(
                collectBrokerDetails=True,
                interactionDelayPreset="careful",
            ),
        )
    )
    assert patched.collect_broker_details is True
    assert patched.interaction_delay_preset == "careful"

    run = CrawlRun(
        id=uuid4(),
        source_id=source.id,
        status="completed",
        stage="save",
        progress=100,
        collect_broker_details=False,
        interaction_delay_preset="fast",
        created_at=datetime(2026, 7, 28, tzinfo=SEOUL),
    )
    session.runs = [run]
    history = asyncio.run(service.runs(session.schedule.id))
    assert history.items[0].collect_broker_details is False
    assert history.items[0].interaction_delay_preset == "fast"


class GrantedLockManager:
    async def acquire(self, _source_id, *, ttl_seconds=600):
        return object()

    async def release(self, _lock):
        return None


def test_due_enqueue_passes_schedule_collection_option(monkeypatch) -> None:
    source = _source()
    schedule = CrawlSchedule(
        id=uuid4(),
        source_id=source.id,
        cadence="daily",
        time_of_day=time(9),
        timezone="Asia/Seoul",
        weekday=None,
        enabled=True,
        collect_broker_details=False,
        interaction_delay_preset="very_careful",
        next_run_at=datetime(2026, 7, 28, 0, 0, tzinfo=timezone.utc),
    )
    captured: list[tuple[bool, str]] = []

    class FakeAnalysisService:
        def __init__(self, _session, _dispatcher) -> None:
            pass

        async def create(
            self,
            _url,
            *,
            collect_broker_details=True,
            interaction_delay_preset="normal",
        ):
            captured.append(
                (collect_broker_details, interaction_delay_preset)
            )
            return object(), True

    monkeypatch.setattr(schedule_module, "AnalysisService", FakeAnalysisService)
    session = ScheduleSession(source, schedule=schedule, due_rows=[(schedule, source)])
    counts = asyncio.run(
        ScheduleService(session).enqueue_due(
            lock_manager=GrantedLockManager(),
            dispatcher=object(),
            now=datetime(2026, 7, 28, 1, 0, tzinfo=timezone.utc),
        )
    )

    assert counts["enqueued"] == 1
    assert captured == [(False, "very_careful")]
