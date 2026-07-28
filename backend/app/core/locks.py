from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from redis.asyncio import Redis, from_url

from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class SourceLock:
    key: str
    token: str


class RedisSourceLockManager:
    _RELEASE_SCRIPT = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
      return redis.call('del', KEYS[1])
    end
    return 0
    """

    def __init__(self, client: Redis | None = None) -> None:
        self.client = client or from_url(
            get_settings().redis_url, encoding="utf-8", decode_responses=True
        )

    async def acquire(
        self, source_id: UUID, *, ttl_seconds: int = 600
    ) -> SourceLock | None:
        key = f"crawl:source:{source_id}"
        token = str(uuid4())
        acquired = await self.client.set(key, token, nx=True, ex=ttl_seconds)
        return SourceLock(key=key, token=token) if acquired else None

    async def release(self, lock: SourceLock) -> None:
        await self.client.eval(self._RELEASE_SCRIPT, 1, lock.key, lock.token)

    async def aclose(self) -> None:
        await self.client.aclose()

