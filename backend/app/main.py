import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import dispose_database
from app.core.logging import configure_logging
from app.runtime.local_dispatcher import shutdown_local_dispatcher
from app.runtime.local_scheduler import local_scheduler_loop


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    stop_event = asyncio.Event()
    scheduler_task: asyncio.Task[None] | None = None
    if settings.is_local:
        scheduler_task = asyncio.create_task(
            local_scheduler_loop(stop_event, interval_seconds=60),
            name="local-schedule-loop",
        )
    try:
        yield
    finally:
        if scheduler_task is not None:
            stop_event.set()
            scheduler_task.cancel()
            with suppress(asyncio.CancelledError):
                await scheduler_task
            shutdown_local_dispatcher()
        await dispose_database()


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    application = FastAPI(title="Wisdom QJ Auction API", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)
    return application


app = create_app()
