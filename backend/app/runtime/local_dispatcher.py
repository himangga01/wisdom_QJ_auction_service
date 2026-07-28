from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Lock
from typing import Any
from uuid import UUID

AsyncCrawlRunner = Callable[[UUID], Awaitable[Any]]


async def _run_crawl(run_id: UUID) -> Any:
    from app.tasks import crawl_tasks

    return await crawl_tasks._execute_pipeline(run_id)


class LocalCrawlTaskDispatcher:
    def __init__(self, *, runner: AsyncCrawlRunner = _run_crawl) -> None:
        self._runner = runner
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="local-crawl",
        )
        self._futures: dict[UUID, Future[Any]] = {}
        self._futures_lock = Lock()

    def _execute(self, run_id: UUID) -> Any:
        return asyncio.run(self._runner(run_id))

    def enqueue(self, run_id: UUID) -> None:
        with self._futures_lock:
            current = self._futures.get(run_id)
            if current is not None and not current.done():
                return
            future = self._executor.submit(self._execute, run_id)
            self._futures[run_id] = future
        future.add_done_callback(
            lambda completed, current_run_id=run_id: self._discard(
                current_run_id, completed
            )
        )

    def _discard(self, run_id: UUID, completed: Future[Any]) -> None:
        with self._futures_lock:
            if self._futures.get(run_id) is completed:
                self._futures.pop(run_id, None)

    def cancel(self, run_id: UUID) -> None:
        with self._futures_lock:
            future = self._futures.get(run_id)
        if future is not None:
            future.cancel()

    def shutdown(self, *, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)


_singleton_lock = Lock()
_local_dispatcher: LocalCrawlTaskDispatcher | None = None


def get_local_dispatcher() -> LocalCrawlTaskDispatcher:
    global _local_dispatcher
    with _singleton_lock:
        if _local_dispatcher is None:
            _local_dispatcher = LocalCrawlTaskDispatcher()
        return _local_dispatcher


def shutdown_local_dispatcher() -> None:
    global _local_dispatcher
    with _singleton_lock:
        dispatcher = _local_dispatcher
        _local_dispatcher = None
    if dispatcher is not None:
        dispatcher.shutdown(wait=False)
