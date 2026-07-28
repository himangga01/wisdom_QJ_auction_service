from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class LocalSourceLock:
    source_id: UUID
    token: str


class LocalSourceLockManager:
    def __init__(self) -> None:
        self._guard = asyncio.Lock()
        self._locked_sources: set[UUID] = set()
        self._tokens: dict[UUID, str] = {}

    async def acquire(
        self, source_id: UUID, *, ttl_seconds: int = 600
    ) -> LocalSourceLock | None:
        del ttl_seconds
        async with self._guard:
            if source_id in self._locked_sources:
                return None
            token = str(uuid4())
            self._locked_sources.add(source_id)
            self._tokens[source_id] = token
            return LocalSourceLock(source_id=source_id, token=token)

    async def release(self, lock: LocalSourceLock) -> None:
        async with self._guard:
            if self._tokens.get(lock.source_id) != lock.token:
                return
            self._tokens.pop(lock.source_id, None)
            self._locked_sources.discard(lock.source_id)


_local_source_lock_manager = LocalSourceLockManager()


def get_local_source_lock_manager() -> LocalSourceLockManager:
    return _local_source_lock_manager
