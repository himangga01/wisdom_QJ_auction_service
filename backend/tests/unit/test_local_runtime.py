import asyncio
import threading
from dataclasses import replace
from uuid import uuid4

from app.runtime.local_dispatcher import LocalCrawlTaskDispatcher
from app.runtime.local_locks import LocalSourceLockManager


def test_local_dispatcher_enqueues_without_waiting_and_runs_one_job_at_a_time() -> None:
    started = threading.Event()
    release = threading.Event()
    state_lock = threading.Lock()
    active = 0
    peak_active = 0

    async def runner(_run_id) -> None:
        nonlocal active, peak_active
        with state_lock:
            active += 1
            peak_active = max(peak_active, active)
        started.set()
        while not release.is_set():
            await asyncio.sleep(0.01)
        with state_lock:
            active -= 1

    dispatcher = LocalCrawlTaskDispatcher(runner=runner)
    first_id = uuid4()
    second_id = uuid4()
    try:
        dispatcher.enqueue(first_id)
        assert started.wait(timeout=1)
        dispatcher.enqueue(second_id)
    finally:
        release.set()
        dispatcher.shutdown(wait=True)

    assert peak_active == 1


def test_local_dispatcher_cancels_only_a_waiting_job() -> None:
    started = threading.Event()
    release = threading.Event()
    executed: list = []

    async def runner(run_id) -> None:
        executed.append(run_id)
        started.set()
        while not release.is_set():
            await asyncio.sleep(0.01)

    dispatcher = LocalCrawlTaskDispatcher(runner=runner)
    running_id = uuid4()
    waiting_id = uuid4()
    try:
        dispatcher.enqueue(running_id)
        assert started.wait(timeout=1)
        dispatcher.enqueue(waiting_id)
        dispatcher.cancel(running_id)
        dispatcher.cancel(waiting_id)
    finally:
        release.set()
        dispatcher.shutdown(wait=True)

    assert executed == [running_id]


def test_local_source_lock_requires_matching_token_to_release() -> None:
    async def scenario() -> None:
        manager = LocalSourceLockManager()
        source_id = uuid4()

        lock = await manager.acquire(source_id)
        assert lock is not None
        assert await manager.acquire(source_id) is None

        await manager.release(replace(lock, token="different"))
        assert await manager.acquire(source_id) is None

        await manager.release(lock)
        assert await manager.acquire(source_id) is not None

    asyncio.run(scenario())
