import asyncio
from types import SimpleNamespace

import pytest

from app.crawler.browser_runtime import connect_external_chrome, open_crawler_page
from app.crawler.errors import BrowserDisconnectedError, BrowserUnavailableError


class _Page:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class _Context:
    def __init__(self, page: _Page, *, new_page_error: Exception | None = None) -> None:
        self.page = page
        self.new_page_error = new_page_error
        self.new_page_calls = 0
        self.closed = False

    async def new_page(self) -> _Page:
        self.new_page_calls += 1
        if self.new_page_error is not None:
            raise self.new_page_error
        return self.page


class _Browser:
    def __init__(self, contexts: list[_Context], *, connected: bool = True) -> None:
        self.contexts = contexts
        self.connected = connected
        self.closed = False

    def is_connected(self) -> bool:
        return self.connected

    async def close(self) -> None:
        self.closed = True


class _Chromium:
    def __init__(self, outcomes: list[_Browser | Exception]) -> None:
        self.outcomes = outcomes
        self.cdp_urls: list[str] = []
        self.launch_calls = 0

    async def connect_over_cdp(self, url: str) -> _Browser:
        self.cdp_urls.append(url)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def launch(self, **_: object) -> _Browser:
        self.launch_calls += 1
        raise AssertionError("crawler must never launch a browser")


class _Playwright:
    def __init__(self, chromium: _Chromium) -> None:
        self.chromium = chromium


def test_external_chrome_uses_default_context_and_closes_only_task_page() -> None:
    page = _Page()
    context = _Context(page)
    browser = _Browser([context])
    chromium = _Chromium([browser])
    settings = SimpleNamespace(crawler_cdp_url="http://127.0.0.1:42973")

    async def run() -> None:
        async with open_crawler_page(_Playwright(chromium), settings) as opened_page:
            assert opened_page is page

    asyncio.run(run())

    assert chromium.cdp_urls == ["http://127.0.0.1:42973"]
    assert chromium.launch_calls == 0
    assert page.closed is True
    assert context.closed is False
    assert browser.closed is False


def test_cdp_connection_retries_three_times_with_bounded_backoff() -> None:
    page = _Page()
    browser = _Browser([_Context(page)])
    chromium = _Chromium(
        [OSError("first"), OSError("second"), browser]
    )
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    connected = asyncio.run(
        connect_external_chrome(
            _Playwright(chromium),
            "http://127.0.0.1:42973",
            sleep=record_sleep,
        )
    )

    assert connected is browser
    assert len(chromium.cdp_urls) == 3
    assert delays == [0.5, 1.0]


def test_cdp_connection_exhaustion_uses_stable_unavailable_error() -> None:
    chromium = _Chromium([OSError("one"), OSError("two"), OSError("three")])

    async def no_sleep(_: float) -> None:
        return None

    with pytest.raises(BrowserUnavailableError) as raised:
        asyncio.run(
            connect_external_chrome(
                _Playwright(chromium),
                "http://127.0.0.1:42973",
                sleep=no_sleep,
            )
        )

    assert raised.value.code == "browser_unavailable"
    assert len(chromium.cdp_urls) == 3


def test_cdp_connection_does_not_convert_task_cancellation_to_browser_failure() -> None:
    class _CancelledChromium(_Chromium):
        async def connect_over_cdp(self, url: str) -> _Browser:
            self.cdp_urls.append(url)
            raise asyncio.CancelledError

    chromium = _CancelledChromium([])

    async def no_sleep(_: float) -> None:
        return None

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            connect_external_chrome(
                _Playwright(chromium),
                "http://127.0.0.1:42973",
                sleep=no_sleep,
            )
        )

    assert len(chromium.cdp_urls) == 1


def test_missing_default_context_is_unavailable_without_closing_chrome() -> None:
    browser = _Browser([])
    chromium = _Chromium([browser, browser, browser])

    async def no_sleep(_: float) -> None:
        return None

    with pytest.raises(BrowserUnavailableError):
        asyncio.run(
            connect_external_chrome(
                _Playwright(chromium),
                "http://127.0.0.1:42973",
                sleep=no_sleep,
            )
        )

    assert browser.closed is False


def test_disconnect_while_crawling_uses_stable_disconnected_error() -> None:
    page = _Page()
    browser = _Browser([_Context(page)])
    settings = SimpleNamespace(crawler_cdp_url="http://127.0.0.1:42973")

    async def run() -> None:
        async with open_crawler_page(
            _Playwright(_Chromium([browser])),
            settings,
        ):
            browser.connected = False
            raise RuntimeError("target closed")

    with pytest.raises(BrowserDisconnectedError) as raised:
        asyncio.run(run())

    assert raised.value.code == "browser_disconnected"
    assert page.closed is True
    assert browser.closed is False
