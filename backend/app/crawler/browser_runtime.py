from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from app.core.config import Settings
from app.crawler.errors import BrowserUnavailableError


BrowserMode = Literal["external_chrome", "playwright"]


@asynccontextmanager
async def open_crawler_page(
    playwright: object,
    settings: Settings,
) -> AsyncIterator[object]:
    if settings.crawler_browser_mode == "external_chrome":
        try:
            browser = await playwright.chromium.connect_over_cdp(
                settings.crawler_cdp_url
            )
        except Exception as exc:
            raise BrowserUnavailableError(
                "전용 Chrome 브라우저에 연결할 수 없습니다."
            ) from exc

        if not browser.contexts:
            error = BrowserUnavailableError(
                "전용 Chrome의 기본 브라우저 context가 없습니다."
            )
            try:
                await browser.close()
            except BaseException as exc:
                error.add_note(f"Browser close failed: {exc}")
                raise error from exc
            raise error

        context = browser.contexts[0]
        try:
            page = await context.new_page()
        except BaseException:
            await browser.close()
            raise
        try:
            yield page
        finally:
            try:
                await page.close()
            finally:
                await browser.close()
        return

    browser = await playwright.chromium.launch(
        headless=settings.crawler_headless
    )
    context = None
    try:
        context = await browser.new_context()
        page = await context.new_page()
        yield page
    finally:
        if context is None:
            await browser.close()
        else:
            try:
                await context.close()
            finally:
                await browser.close()
