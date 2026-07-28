import asyncio
from types import SimpleNamespace

from app import main
from app.runtime import local_scheduler


def test_scheduler_runs_immediately_and_survives_a_cycle_error(monkeypatch) -> None:
    calls = 0

    async def cycle() -> dict[str, int]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary")
        stop_event.set()
        return {"due": 0, "enqueued": 0, "deduplicated": 0, "locked": 0}

    stop_event = asyncio.Event()
    monkeypatch.setattr(local_scheduler, "run_local_schedule_cycle", cycle)

    asyncio.run(local_scheduler.local_scheduler_loop(stop_event, interval_seconds=0))

    assert calls == 2


def test_docker_lifespan_does_not_start_local_scheduler(monkeypatch) -> None:
    scheduler_started = False

    async def scheduler(_stop_event, _interval_seconds=60) -> None:
        nonlocal scheduler_started
        scheduler_started = True

    async def dispose() -> None:
        return None

    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(is_local=False))
    monkeypatch.setattr(main, "local_scheduler_loop", scheduler)
    monkeypatch.setattr(main, "dispose_database", dispose)

    async def scenario() -> None:
        async with main.lifespan(None):
            pass

    asyncio.run(scenario())

    assert scheduler_started is False
