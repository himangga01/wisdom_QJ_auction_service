import asyncio
from types import SimpleNamespace

import pytest

from app.crawler.browser_runtime import open_crawler_page
from app.crawler.errors import BrowserUnavailableError


class _Page:
    def __init__(self, *, close_error: Exception | None = None) -> None:
        self.closed = False
        self.close_error = close_error

    async def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class _Context:
    def __init__(
        self,
        page: _Page,
        *,
        new_page_error: Exception | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self.page = page
        self.new_page_error = new_page_error
        self.close_error = close_error
        self.new_page_calls = 0
        self.closed = False

    async def new_page(self) -> _Page:
        self.new_page_calls += 1
        if self.new_page_error is not None:
            raise self.new_page_error
        return self.page

    async def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class _Browser:
    def __init__(
        self,
        contexts: list[_Context],
        *,
        new_context_error: Exception | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self.contexts = contexts
        self.new_context_error = new_context_error
        self.close_error = close_error
        self.new_context_calls = 0
        self.closed = False

    async def new_context(self) -> _Context:
        self.new_context_calls += 1
        if self.new_context_error is not None:
            raise self.new_context_error
        return self.contexts[0]

    async def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class _Chromium:
    def __init__(self, browser: _Browser, *, connect_error: Exception | None = None) -> None:
        self.browser = browser
        self.connect_error = connect_error
        self.cdp_urls: list[str] = []
        self.launch_options: list[dict[str, object]] = []

    async def connect_over_cdp(self, url: str) -> _Browser:
        self.cdp_urls.append(url)
        if self.connect_error is not None:
            raise self.connect_error
        return self.browser

    async def launch(self, **kwargs: object) -> _Browser:
        self.launch_options.append(kwargs)
        return self.browser


class _Playwright:
    def __init__(self, chromium: _Chromium) -> None:
        self.chromium = chromium


def test_external_chrome_uses_default_context_and_closes_only_task_page() -> None:
    page = _Page()
    context = _Context(page)
    browser = _Browser([context])
    chromium = _Chromium(browser)
    playwright = _Playwright(chromium)
    settings = SimpleNamespace(
        crawler_browser_mode="external_chrome",
        crawler_cdp_url="http://127.0.0.1:42973",
    )

    async def run() -> None:
        async with open_crawler_page(playwright, settings) as opened_page:
            assert opened_page is page
            assert chromium.cdp_urls == ["http://127.0.0.1:42973"]
            assert context.new_page_calls == 1
            assert context.closed is False

    asyncio.run(run())

    assert page.closed is True
    assert browser.closed is True
    assert context.closed is False
    assert browser.new_context_calls == 0


def test_external_chrome_translates_cdp_connection_failure() -> None:
    browser = _Browser([])
    chromium = _Chromium(browser, connect_error=OSError("connection refused"))
    settings = SimpleNamespace(
        crawler_browser_mode="external_chrome",
        crawler_cdp_url="http://127.0.0.1:42973",
    )

    async def run() -> None:
        async with open_crawler_page(_Playwright(chromium), settings):
            raise AssertionError("must not yield a page")

    with pytest.raises(BrowserUnavailableError):
        asyncio.run(run())


def test_external_chrome_translates_missing_default_context() -> None:
    browser = _Browser([])
    chromium = _Chromium(browser)
    settings = SimpleNamespace(
        crawler_browser_mode="external_chrome",
        crawler_cdp_url="http://127.0.0.1:42973",
    )

    async def run() -> None:
        async with open_crawler_page(_Playwright(chromium), settings):
            raise AssertionError("must not yield a page")

    with pytest.raises(BrowserUnavailableError):
        asyncio.run(run())

    assert browser.closed is True


def test_external_chrome_preserves_unavailable_error_when_missing_context_close_fails() -> None:
    browser = _Browser([], close_error=RuntimeError("close failed"))
    chromium = _Chromium(browser)
    settings = SimpleNamespace(
        crawler_browser_mode="external_chrome",
        crawler_cdp_url="http://127.0.0.1:42973",
    )

    async def run() -> None:
        async with open_crawler_page(_Playwright(chromium), settings):
            raise AssertionError("must not yield a page")

    with pytest.raises(BrowserUnavailableError) as raised:
        asyncio.run(run())

    assert "기본 브라우저 context" in str(raised.value)
    assert browser.closed is True


def test_external_chrome_closes_connection_when_task_page_creation_fails() -> None:
    context = _Context(_Page(), new_page_error=RuntimeError("page failed"))
    browser = _Browser([context])
    settings = SimpleNamespace(
        crawler_browser_mode="external_chrome",
        crawler_cdp_url="http://127.0.0.1:42973",
    )

    async def run() -> None:
        async with open_crawler_page(_Playwright(_Chromium(browser)), settings):
            raise AssertionError("must not yield a page")

    with pytest.raises(RuntimeError, match="page failed"):
        asyncio.run(run())

    assert browser.closed is True
    assert context.closed is False


def test_external_chrome_closes_connection_when_task_page_close_fails() -> None:
    page = _Page(close_error=RuntimeError("page close failed"))
    context = _Context(page)
    browser = _Browser([context])
    settings = SimpleNamespace(
        crawler_browser_mode="external_chrome",
        crawler_cdp_url="http://127.0.0.1:42973",
    )

    async def run() -> None:
        async with open_crawler_page(_Playwright(_Chromium(browser)), settings):
            return None

    with pytest.raises(RuntimeError, match="page close failed"):
        asyncio.run(run())

    assert browser.closed is True
    assert context.closed is False


def test_playwright_mode_preserves_legacy_launch_lifecycle() -> None:
    page = _Page()
    context = _Context(page)
    browser = _Browser([context])
    chromium = _Chromium(browser)
    settings = SimpleNamespace(
        crawler_browser_mode="playwright",
        crawler_headless=True,
    )

    async def run() -> None:
        async with open_crawler_page(_Playwright(chromium), settings) as opened_page:
            assert opened_page is page

    asyncio.run(run())

    assert chromium.launch_options == [{"headless": True}]
    assert browser.new_context_calls == 1
    assert context.new_page_calls == 1
    assert context.closed is True
    assert browser.closed is True


def test_playwright_mode_closes_browser_when_context_creation_fails() -> None:
    browser = _Browser([], new_context_error=RuntimeError("context failed"))
    settings = SimpleNamespace(
        crawler_browser_mode="playwright",
        crawler_headless=True,
    )

    async def run() -> None:
        async with open_crawler_page(_Playwright(_Chromium(browser)), settings):
            raise AssertionError("must not yield a page")

    with pytest.raises(RuntimeError, match="context failed"):
        asyncio.run(run())

    assert browser.closed is True


def test_playwright_mode_closes_context_and_browser_when_page_creation_fails() -> None:
    context = _Context(_Page(), new_page_error=RuntimeError("page failed"))
    browser = _Browser([context])
    settings = SimpleNamespace(
        crawler_browser_mode="playwright",
        crawler_headless=True,
    )

    async def run() -> None:
        async with open_crawler_page(_Playwright(_Chromium(browser)), settings):
            raise AssertionError("must not yield a page")

    with pytest.raises(RuntimeError, match="page failed"):
        asyncio.run(run())

    assert context.closed is True
    assert browser.closed is True


def test_playwright_mode_closes_browser_when_context_close_fails() -> None:
    context = _Context(_Page(), close_error=RuntimeError("context close failed"))
    browser = _Browser([context])
    settings = SimpleNamespace(
        crawler_browser_mode="playwright",
        crawler_headless=True,
    )

    async def run() -> None:
        async with open_crawler_page(_Playwright(_Chromium(browser)), settings):
            return None

    with pytest.raises(RuntimeError, match="context close failed"):
        asyncio.run(run())

    assert browser.closed is True
