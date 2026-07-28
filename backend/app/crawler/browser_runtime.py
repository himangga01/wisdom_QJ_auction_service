import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from app.core.config import Settings
from app.crawler.errors import BrowserDisconnectedError, BrowserUnavailableError

Sleep = Callable[[float], Awaitable[None]]
BACKOFF_SECONDS = (0.5, 1.0)


def _is_connected(browser: object) -> bool:
    check = getattr(browser, "is_connected", None)
    return bool(check()) if callable(check) else True


async def connect_external_chrome(
    playwright: object,
    endpoint_url: str,
    *,
    attempts: int = 3,
    sleep: Sleep = asyncio.sleep,
) -> object:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            browser = await playwright.chromium.connect_over_cdp(endpoint_url)
            if not browser.contexts:
                raise RuntimeError("Chrome default context is unavailable")
            return browser
        except Exception as exc:
            last_error = exc
            if attempt + 1 >= attempts:
                break
            delay_index = min(attempt, len(BACKOFF_SECONDS) - 1)
            await sleep(BACKOFF_SECONDS[delay_index])

    raise BrowserUnavailableError(
        "수집용 Chrome에 연결할 수 없습니다."
    ) from last_error


@asynccontextmanager
async def open_crawler_page(
    playwright: object,
    settings: Settings,
) -> AsyncIterator[object]:
    browser = await connect_external_chrome(
        playwright,
        settings.crawler_cdp_url,
    )
    context = browser.contexts[0]
    page: object | None = None
    try:
        try:
            page = await context.new_page()
        except Exception as exc:
            if not _is_connected(browser):
                raise BrowserDisconnectedError(
                    "조사 중 Chrome 연결이 끊겼습니다."
                ) from exc
            raise

        try:
            yield page
        except Exception as exc:
            if not _is_connected(browser):
                raise BrowserDisconnectedError(
                    "조사 중 Chrome 연결이 끊겼습니다."
                ) from exc
            raise
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception as exc:
                if not _is_connected(browser):
                    raise BrowserDisconnectedError(
                        "조사 중 Chrome 연결이 끊겼습니다."
                    ) from exc
                raise
