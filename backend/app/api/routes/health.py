from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import check_database
from app.crawler.browser_readiness import (
    BrowserStatus as RequiredBrowserStatus,
    probe_browser_cdp,
)

router = APIRouter(tags=["health"])
ConnectionStatus = Literal["connected", "disconnected"]
RedisStatus = Literal["connected", "disconnected", "not_required"]
BrowserStatus = Literal["ready", "unavailable", "not_required"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: ConnectionStatus
    redis: RedisStatus
    browser: BrowserStatus


async def database_status() -> ConnectionStatus:
    return await check_database()  # type: ignore[return-value]


async def redis_status() -> RedisStatus:
    if get_settings().is_local:
        return "not_required"
    try:
        from redis.asyncio import Redis

        client = Redis.from_url(get_settings().redis_url)
        try:
            await client.ping()
        finally:
            await client.aclose()
    except Exception:
        return "disconnected"
    return "connected"


async def browser_status() -> RequiredBrowserStatus:
    settings = get_settings()
    return await probe_browser_cdp(settings.crawler_cdp_url)


@router.get("/health", response_model=HealthResponse)
async def health(
    database: Annotated[ConnectionStatus, Depends(database_status)],
    redis: Annotated[RedisStatus, Depends(redis_status)],
    browser: Annotated[BrowserStatus, Depends(browser_status)],
) -> HealthResponse:
    return HealthResponse(
        status=(
            "ok"
            if (
                database == "connected"
                and redis in {"connected", "not_required"}
                and browser in {"ready", "not_required"}
            )
            else "degraded"
        ),
        database=database,
        redis=redis,
        browser=browser,
    )
