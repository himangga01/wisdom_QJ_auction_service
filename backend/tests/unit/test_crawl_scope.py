import asyncio
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from inspect import getsource, signature
import re
from types import SimpleNamespace

import pytest

import app.crawler.browser as browser_module
import app.crawler.selectors as selector_module
from app.crawler.errors import (
    BlockedCrawlError,
    IncompleteListingCollectionError,
    SelectorMismatchError,
)
from app.crawler.live_dom import BrokerCardObservation
from app.crawler.navigation import UnsafeArticleTarget
from app.crawler.scope import CrawlScope
from app.crawler.browser import (
    PlaywrightNaverLandCollector,
    _iter_nonempty_trade_types,
    _is_full_collection,
    _should_scan_group,
    _should_visit_article,
)
from app.crawler.selectors import (
    BROKER_ARTICLE_LINK,
    BROKER_OPEN_BUTTON,
    COMPLEX_LINK,
    DETAIL_READY,
    LISTING_CARD,
    LISTING_SCROLL_CONTAINER,
    LOGIN_TEXT_MARKERS,
    SINGLE_ARTICLE_LINK,
    TRADE_COUNT_BUTTON,
)
from app.crawler.types import (
    BrokerArticleDetail,
    ComplexDetail,
    CrawlPayload,
    ListingDetail,
    MarketDetails,
)


class _NoDelay:
    async def wait(self, reason: str) -> None:
        return None


class _OpenButton:
    def __init__(self) -> None:
        self.clicked = False

    @property
    def first(self):
        return self

    async def count(self) -> int:
        return 1

    async def click(self) -> None:
        self.clicked = True


class _BrokerLink:
    def __init__(self, row_html: str) -> None:
        self.row_html = row_html

    async def wait_for(self, **kwargs: object) -> None:
        return None

    async def evaluate(self, expression: str) -> str:
        return self.row_html

    async def scroll_into_view_if_needed(self) -> None:
        return None


class _BrokerLinks:
    def __init__(self, rows: list[str]) -> None:
        self.links = [_BrokerLink(row) for row in rows]

    @property
    def first(self) -> _BrokerLink:
        return self.links[0]

    @property
    def last(self) -> _BrokerLink:
        return self.links[-1]

    async def count(self) -> int:
        return len(self.links)

    def nth(self, index: int) -> _BrokerLink:
        return self.links[index]


class _BrokerCard:
    def __init__(self, rows: list[str]) -> None:
        self.open_button = _OpenButton()
        self.broker_links = _BrokerLinks(rows)

    def locator(self, selector: str):
        if selector == BROKER_OPEN_BUTTON:
            return self.open_button
        if selector == BROKER_ARTICLE_LINK:
            return self.broker_links
        raise AssertionError(f"unexpected selector: {selector}")

    async def evaluate(self, expression: str) -> str:
        return "<li>group</li>"


class _Keyboard:
    def __init__(self) -> None:
        self.keys: list[str] = []

    async def press(self, key: str) -> None:
        self.keys.append(key)


class _BrokerPage:
    def __init__(self) -> None:
        self.keyboard = _Keyboard()


def test_sampled_and_full_scope_values_are_immutable() -> None:
    sampled = CrawlScope.sampled({"2639879471", "2639879472"})
    full = CrawlScope.full()

    assert sampled.trade_types == ("매매", "전세", "월세")
    assert sampled.max_groups_per_trade_type == 25
    assert sampled.expected_article_ids == frozenset(
        {"2639879471", "2639879472"}
    )
    assert full.trade_types == ("매매", "전세", "월세")
    assert full.max_groups_per_trade_type is None
    assert full.expected_article_ids == frozenset()
    with pytest.raises(FrozenInstanceError):
        sampled.max_groups_per_trade_type = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    "values",
    [
        {"trade_types": ("단기임대",)},
        {"trade_types": ("매매", "매매")},
        {"max_groups_per_trade_type": 0},
        {"max_groups_per_trade_type": -1},
        {"expected_article_ids": frozenset({""})},
        {"expected_article_ids": frozenset({"   "})},
    ],
)
def test_scope_rejects_invalid_values(values: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        CrawlScope(**values)  # type: ignore[arg-type]


def test_crawl_payload_trade_counts_defaults_without_breaking_old_callers() -> None:
    payload = CrawlPayload(
        status="completed",
        apartment=ComplexDetail(
            complex_id="131197",
            name="신동탄포레자이",
            address="",
        ),
        listings=[],
    )

    assert payload.trade_counts == {}


def test_live_selector_contract_is_exact() -> None:
    assert COMPLEX_LINK == "a[href^='/complexes/']"
    assert TRADE_COUNT_BUTTON == "button[data-sentry-component='ButtonBoxLink']"
    assert LISTING_CARD == (
        "li:has(button[data-nlogs-area='article*l.group']), "
        "li:has(a[data-nlogs-area='article*l.list'][href^='/articles/'])"
    )
    assert BROKER_OPEN_BUTTON == "button[data-nlogs-area='article*l.group']"
    assert BROKER_ARTICLE_LINK == (
        "a[data-nlogs-area='article*l.group'][href^='/articles/']"
    )
    assert SINGLE_ARTICLE_LINK == (
        "a[data-nlogs-area='article*l.list'][href^='/articles/']"
    )
    assert LISTING_SCROLL_CONTAINER == "div[class*='ScrollBox'][class*='panel']"
    assert DETAIL_READY == "text=매물번호"
    assert getattr(selector_module, "BROKER_NPAY_DETAIL_TRIGGER", None) == (
        "a[data-sentry-component='ButtonBoxLink'][href^='/articles/']"
    )
    assert getattr(selector_module, "BROKER_STANDARD_DETAIL_TRIGGER", None) == (
        "a[data-nlogs-area='article*l.group'][href^='/articles/'], "
        "a[data-nlogs-area='article*l.list'][href^='/articles/']"
    )
    assert getattr(selector_module, "DETAIL_SLIDE_ROOT", None) == (
        "div[data-sentry-component='SideLayer']:"
        "has(div[class*='DataList'][class*='term']:text-is('매물번호'))"
    )
    assert getattr(selector_module, "DETAIL_SLIDE_CLOSE_BUTTON", None) == (
        "button:has-text('창닫기')"
    )


def test_collector_accepts_keyword_only_scope() -> None:
    parameters = signature(PlaywrightNaverLandCollector.collect).parameters

    assert tuple(parameters) == ("self", "source_url", "scope")
    assert parameters["scope"].kind.name == "KEYWORD_ONLY"
    assert parameters["scope"].default is None


def test_zero_count_trade_types_are_not_selected_for_clicking() -> None:
    scope = CrawlScope(
        trade_types=("매매", "전세", "월세"),
    )

    assert _iter_nonempty_trade_types(
        scope,
        {"매매": 53, "전세": 0, "월세": 1},
    ) == ("매매", "월세")


def test_expected_article_filter_and_sample_group_limit() -> None:
    sampled = CrawlScope.sampled({"2639879471"})
    full = CrawlScope.full()

    assert _should_scan_group(sampled, groups_scanned=0) is True
    assert _should_scan_group(sampled, groups_scanned=24) is True
    assert _should_scan_group(sampled, groups_scanned=25) is False
    assert _should_scan_group(full, groups_scanned=100) is True
    assert _should_visit_article(sampled, "2639879471") is True
    assert _should_visit_article(sampled, "2639879472") is False
    assert _should_visit_article(full, "2639879472") is True


def test_address_uses_first_nonempty_explicit_detail_location() -> None:
    empty = MarketDetails()
    located = MarketDetails(extra_fields={"위치": " 경기도 화성시 "})
    later = MarketDetails(extra_fields={"위치": "다른 주소"})

    address = browser_module._first_explicit_location("", empty)
    address = browser_module._first_explicit_location(address, located)
    address = browser_module._first_explicit_location(address, later)

    assert address == "경기도 화성시"


def test_login_marker_does_not_match_general_logged_out_header() -> None:
    assert LOGIN_TEXT_MARKERS == ("로그인이 필요",)


class _ListingCards:
    async def count(self) -> int:
        return 1

    def nth(self, index: int) -> object:
        assert index == 0
        return object()


class _ScrollContainer:
    def __init__(self) -> None:
        self.end_states = iter([False, True, True])
        self.mutations = 0

    @property
    def first(self):
        return self

    async def count(self) -> int:
        return 1

    async def evaluate(self, expression: str):
        if "scrollTop + element.clientHeight" in expression:
            return next(self.end_states)
        self.mutations += 1
        return None


class _TradeCountButton:
    def __init__(self, count: int) -> None:
        self.count_value = count

    async def inner_text(self) -> str:
        return f"매매 {self.count_value}"


class _TradeCountButtons:
    def __init__(self, count: int) -> None:
        self.button = _TradeCountButton(count)

    async def count(self) -> int:
        return 1

    def nth(self, index: int) -> _TradeCountButton:
        assert index == 0
        return self.button


class _ScanPage:
    def __init__(self) -> None:
        self.cards = _ListingCards()
        self.container = _ScrollContainer()
        self.trade_counts = _TradeCountButtons(1)

    def locator(self, selector: str):
        if selector == LISTING_CARD:
            return self.cards
        if selector == LISTING_SCROLL_CONTAINER:
            return self.container
        if selector == TRADE_COUNT_BUTTON:
            return self.trade_counts
        raise AssertionError(f"unexpected selector: {selector}")


class _SettleRecordingCollector(PlaywrightNaverLandCollector):
    def __init__(self) -> None:
        self.delay = _NoDelay()
        self.settle_calls = 0

    async def _card_key(self, card) -> tuple[str, tuple[str, ...]]:
        return ("same visible card", ("/articles/1",))

    async def _collect_visible_group(
        self,
        page,
        card,
        *,
        scope,
        captured_at,
        seen_article_ids,
        blocked_statuses,
    ):
        group_type = getattr(browser_module, "CollectedListingGroup", None)
        assert group_type is not None
        return group_type(
            group_html="<li>group</li>",
            broker_rows=["<li><a href='/articles/1'>매물 보러가기</a></li>"],
            articles=[],
            market_details=None,
            warnings=[],
        )

    async def _listing_snapshot(self, page):
        return (("same visible card", ("/articles/1",)),)

    async def _wait_for_listing_settle(self, page, previous_snapshot) -> None:
        self.settle_calls += 1


def test_full_scroll_settles_after_each_scroll_mutation() -> None:
    collector = _SettleRecordingCollector()
    page = _ScanPage()

    groups, _ = asyncio.run(
        collector._scan_listing_groups(
            page,
            CrawlScope.full(),
            trade_type="매매",
            expected_group_count=1,
            captured_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
            seen_article_ids=set(),
            blocked_statuses=set(),
        )
    )

    assert [group.group_html for group in groups] == ["<li>group</li>"]
    assert page.container.mutations == 1
    assert collector.settle_calls == page.container.mutations


def test_scroll_settle_polls_until_visible_dom_changes(monkeypatch) -> None:
    collector = object.__new__(PlaywrightNaverLandCollector)
    snapshots = iter(
        [
            (("before", ()),),
            (("after", ("/articles/2",)),),
        ]
    )
    sleep_calls: list[float] = []

    async def fake_snapshot(page):
        return next(snapshots)

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    collector._listing_snapshot = fake_snapshot
    monkeypatch.setattr(browser_module.asyncio, "sleep", fake_sleep)

    asyncio.run(
        collector._wait_for_listing_settle(
            object(),
            (("before", ()),),
        )
    )

    assert len(sleep_calls) == 2


class _RecordingDelay:
    def __init__(self) -> None:
        self.reasons: list[str] = []

    async def wait(self, reason: str) -> None:
        self.reasons.append(reason)


class _ResetScrollContainer:
    def __init__(self, scroll_top: int) -> None:
        self.scroll_top = scroll_top
        self.mutations = 0

    @property
    def first(self):
        return self

    async def count(self) -> int:
        return 1

    async def evaluate(self, expression: str):
        if "scrollTop = 0" in expression:
            self.mutations += 1
            self.scroll_top = 0
            return None
        if "scrollTop" in expression:
            return self.scroll_top
        raise AssertionError(f"unexpected expression: {expression}")


class _ResetScrollPage:
    def __init__(self, scroll_top: int) -> None:
        self.container = _ResetScrollContainer(scroll_top)

    def locator(self, selector: str):
        assert selector == LISTING_SCROLL_CONTAINER
        return self.container


class _ResetScrollCollector(PlaywrightNaverLandCollector):
    def __init__(
        self,
        snapshots: list[tuple[tuple[str, tuple[str, ...]], ...]],
    ) -> None:
        self.delay = _RecordingDelay()
        self.snapshots = iter(snapshots)
        self.snapshot_calls = 0

    async def _listing_snapshot(self, page):
        self.snapshot_calls += 1
        return next(self.snapshots)


def test_nonzero_listing_scroll_is_reset_with_delay_and_top_settle(
    monkeypatch,
) -> None:
    old_snapshot = (("old viewport", ("/articles/9",)),)
    top_snapshot = (("first group", ("/articles/1",)),)
    collector = _ResetScrollCollector(
        [old_snapshot, top_snapshot, top_snapshot]
    )
    page = _ResetScrollPage(scroll_top=720)
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(browser_module.asyncio, "sleep", fake_sleep)

    asyncio.run(collector._reset_listing_scroll(page))

    assert collector.delay.reasons == ["reset_listing_scroll"]
    assert page.container.mutations == 1
    assert page.container.scroll_top == 0
    assert collector.snapshot_calls == 2
    assert len(sleep_calls) == 1


def test_zero_listing_scroll_skips_reset_mutation_and_delay() -> None:
    collector = _ResetScrollCollector([])
    page = _ResetScrollPage(scroll_top=0)

    asyncio.run(collector._reset_listing_scroll(page))

    assert collector.delay.reasons == []
    assert page.container.mutations == 0
    assert collector.snapshot_calls == 0


class _SwitchButton:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    @property
    def first(self):
        return self

    def filter(self, *, has_text: str):
        assert has_text == "매매"
        return self

    async def count(self) -> int:
        return 1

    async def click(self) -> None:
        self.events.append("click")


class _SwitchCards:
    def __init__(
        self,
        events: list[str],
        *,
        already_selected: bool = False,
        misleading_description: bool = False,
    ) -> None:
        self.events = events
        self.already_selected = already_selected
        self.misleading_description = misleading_description

    @property
    def first(self):
        return self

    async def count(self) -> int:
        return 1

    async def inner_text(self) -> str:
        self.events.append("read")
        if self.already_selected:
            return "매매 9억"
        if self.misleading_description and "reset" not in self.events:
            return "전세 22억\n매매 조건 협의"
        return "매매 9억" if "reset" in self.events else "월세 1000/50"


class _SwitchPage:
    def __init__(
        self,
        events: list[str],
        *,
        already_selected: bool = False,
        misleading_description: bool = False,
    ) -> None:
        self.button = _SwitchButton(events)
        self.cards = _SwitchCards(
            events,
            already_selected=already_selected,
            misleading_description=misleading_description,
        )

    def locator(self, selector: str):
        if selector == TRADE_COUNT_BUTTON:
            return self.button
        if selector == LISTING_CARD:
            return self.cards
        raise AssertionError(f"unexpected selector: {selector}")


class _SwitchResetCollector(PlaywrightNaverLandCollector):
    def __init__(self, events: list[str]) -> None:
        self.delay = _RecordingDelay()
        self.events = events

    async def _reset_listing_scroll(self, page) -> None:
        self.events.append("reset")


def test_trade_switch_resets_scroll_before_first_card_is_judged(
    monkeypatch,
) -> None:
    events: list[str] = []
    collector = _SwitchResetCollector(events)

    async def fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr(browser_module.asyncio, "sleep", fake_sleep)

    asyncio.run(collector._switch_trade_type(_SwitchPage(events), "매매"))

    assert events == ["read", "click", "reset", "read"]


def test_trade_switch_skips_click_when_requested_trade_is_already_loaded() -> None:
    events: list[str] = []
    collector = _SwitchResetCollector(events)

    asyncio.run(
        collector._switch_trade_type(
            _SwitchPage(events, already_selected=True),
            "매매",
        )
    )

    assert events == ["read", "reset"]


def test_trade_switch_does_not_treat_description_as_selected_trade() -> None:
    events: list[str] = []
    collector = _SwitchResetCollector(events)

    asyncio.run(
        collector._switch_trade_type(
            _SwitchPage(events, misleading_description=True),
            "매매",
        )
    )

    assert events == ["read", "click", "reset", "read"]


class _ExpectedCard:
    def __init__(self, name: str) -> None:
        self.name = name


class _ExpectedCards:
    def __init__(self, names: list[str]) -> None:
        self.cards = [_ExpectedCard(name) for name in names]

    async def count(self) -> int:
        return len(self.cards)

    def nth(self, index: int) -> _ExpectedCard:
        return self.cards[index]


class _ExpectedScanPage:
    def __init__(self, names: list[str]) -> None:
        self.cards = _ExpectedCards(names)
        self.container = _ExpectedScrollContainer()

    def locator(self, selector: str):
        if selector == LISTING_CARD:
            return self.cards
        if selector == LISTING_SCROLL_CONTAINER:
            return self.container
        raise AssertionError("expected match must stop before scrolling")


class _ExpectedScrollContainer:
    @property
    def first(self):
        return self

    async def count(self) -> int:
        return 1


class _ExpectedScanCollector(PlaywrightNaverLandCollector):
    def __init__(self, hrefs: dict[str, str]) -> None:
        self.delay = _NoDelay()
        self.hrefs = hrefs
        self.broker_calls: list[str] = []

    async def _card_key(self, card) -> tuple[str, tuple[str, ...]]:
        return (card.name, (self.hrefs[card.name],))

    async def _collect_visible_group(
        self,
        page,
        card,
        *,
        scope,
        captured_at,
        seen_article_ids,
        blocked_statuses,
    ):
        self.broker_calls.append(card.name)
        href = self.hrefs[card.name]
        row = (
            "<li>"
            f"<a href='{href}'>매물 보러가기</a>"
            "</li>"
        )
        browser_module._broker_target(row)
        group_type = getattr(browser_module, "CollectedListingGroup", None)
        assert group_type is not None
        return group_type(
            group_html=f"<li>{card.name}</li>",
            broker_rows=[row],
            articles=[],
            market_details=None,
            warnings=[],
        )


def test_sampled_scan_stops_when_expected_id_is_found_in_a_group() -> None:
    collector = _ExpectedScanCollector(
        {
            "first": "/articles/1",
            "expected": "/articles/2",
            "third": "/articles/3",
        }
    )
    page = _ExpectedScanPage(["first", "expected", "third"])

    groups, _ = asyncio.run(
        collector._scan_listing_groups(
            page,
            CrawlScope.sampled({"2"}),
            trade_type="매매",
            expected_group_count=3,
            captured_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
            seen_article_ids=set(),
            blocked_statuses=set(),
        )
    )

    assert [group.group_html for group in groups] == [
        "<li>first</li>",
        "<li>expected</li>",
    ]
    assert collector.broker_calls == ["first", "expected"]


def test_sampled_expected_scan_propagates_unsafe_article_target() -> None:
    collector = _ExpectedScanCollector(
        {"unsafe": "https://example.com/articles/2"}
    )
    page = _ExpectedScanPage(["unsafe"])

    with pytest.raises(UnsafeArticleTarget):
        asyncio.run(
            collector._scan_listing_groups(
                page,
                CrawlScope.sampled({"2"}),
                trade_type="매매",
                expected_group_count=1,
                captured_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
                seen_article_ids=set(),
                blocked_statuses=set(),
            )
        )


class _StatusOnlyResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    @property
    def url(self) -> str:
        raise AssertionError("response URL must not be read")


class _ResponseObserverPage:
    def __init__(self) -> None:
        self.response_callback = None

    def on(self, event: str, callback) -> None:
        assert event == "response"
        self.response_callback = callback

    def emit(self, status: int) -> None:
        assert self.response_callback is not None
        self.response_callback(_StatusOnlyResponse(status))


def test_response_observer_records_only_403_and_429_statuses() -> None:
    page = _ResponseObserverPage()

    blocked_statuses = browser_module._observe_blocking_responses(page)
    page.emit(200)
    page.emit(403)
    page.emit(429)
    page.emit(429)

    assert blocked_statuses == {403, 429}
    assert getattr(blocked_statuses, "revision", None) == 3


class _MissingComplexLocator:
    @property
    def first(self):
        return self

    async def wait_for(self, **kwargs: object) -> None:
        raise RuntimeError("complex link missing")


class _MissingComplexPage:
    def locator(self, selector: str) -> _MissingComplexLocator:
        assert selector == COMPLEX_LINK
        return _MissingComplexLocator()


def test_missing_complex_after_429_is_access_blocked() -> None:
    collector = object.__new__(PlaywrightNaverLandCollector)

    with pytest.raises(BlockedCrawlError) as raised:
        asyncio.run(
            collector._wait_for_complex_link(
                _MissingComplexPage(),
                blocked_statuses={429},
            )
        )

    assert raised.value.code == "access_blocked"
    assert "429" not in str(raised.value)


def test_missing_complex_without_block_response_is_selector_mismatch() -> None:
    collector = object.__new__(PlaywrightNaverLandCollector)

    with pytest.raises(SelectorMismatchError):
        asyncio.run(
            collector._wait_for_complex_link(
                _MissingComplexPage(),
                blocked_statuses=set(),
            )
        )


def test_live_e2e_classifies_access_block_as_e2e_blocked() -> None:
    from tests.e2e import test_naver_live_scrape

    with pytest.raises(
        pytest.fail.Exception,
        match=r"^E2E_BLOCKED: access_blocked$",
    ):
        test_naver_live_scrape._fail_e2e_blocked(
            BlockedCrawlError("blocked")
        )


_SLIDE_TARGET = "/articles/2637329815"
_SLIDE_CAPTURED_AT = datetime(2026, 7, 25, tzinfo=timezone.utc)
_SLIDE_OUTER_HTML = (
    "<div data-sentry-component='SideLayer'>"
    "<div>매물번호</div><div>2637329815</div>"
    "</div>"
)


class _SlideTrigger:
    def __init__(
        self,
        *,
        available: bool,
        blocked_statuses: set[int],
        new_blocked_status: int | None = None,
    ) -> None:
        self.available = available
        self.blocked_statuses = blocked_statuses
        self.new_blocked_status = new_blocked_status
        self.clicked = False
        self.has_text = None

    @property
    def first(self):
        return self

    def filter(self, *, has_text):
        self.has_text = has_text
        return self

    async def count(self) -> int:
        return int(self.available)

    async def click(self) -> None:
        self.clicked = True
        if self.new_blocked_status is not None:
            self.blocked_statuses.add(self.new_blocked_status)


class _SlideCard:
    def __init__(
        self,
        blocked_statuses: set[int],
        *,
        npay_available: bool = True,
        standard_available: bool = True,
        new_blocked_status: int | None = None,
    ) -> None:
        self.locator_calls: list[str] = []
        self.npay = _SlideTrigger(
            available=npay_available,
            blocked_statuses=blocked_statuses,
            new_blocked_status=new_blocked_status,
        )
        self.standard = _SlideTrigger(
            available=standard_available,
            blocked_statuses=blocked_statuses,
            new_blocked_status=new_blocked_status,
        )

    def locator(self, selector: str) -> _SlideTrigger:
        self.locator_calls.append(selector)
        if "data-sentry-component='ButtonBoxLink'" in selector:
            return self.npay
        if "data-nlogs-area='article*l." in selector:
            return self.standard
        raise AssertionError(f"unexpected trigger selector: {selector}")


class _SlideReady:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.wait_calls: list[dict[str, object]] = []

    @property
    def first(self):
        return self

    async def wait_for(self, **kwargs: object) -> None:
        self.wait_calls.append(kwargs)
        if self.error is not None:
            raise self.error


class _SlideCloseButton:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.clicked = False

    @property
    def first(self):
        return self

    async def click(self) -> None:
        self.clicked = True
        if self.error is not None:
            raise self.error


class _ActiveSlide:
    def __init__(
        self,
        *,
        outer_html: str = _SLIDE_OUTER_HTML,
        ready_error: Exception | None = None,
        match_count: int = 1,
    ) -> None:
        self.match_count = match_count
        self.count_calls = 0
        self.outer_html = outer_html
        self.ready = _SlideReady(
            ready_error
            or (
                TimeoutError("detail slide does not exist")
                if match_count == 0
                else None
            )
        )
        self.close_button = _SlideCloseButton(
            TimeoutError("missing slide close button")
            if match_count == 0
            else None
        )
        self.locator_calls: list[str] = []
        self.wait_calls: list[dict[str, object]] = []
        self.evaluate_calls: list[str] = []

    @property
    def last(self):
        return self

    async def count(self) -> int:
        self.count_calls += 1
        return self.match_count

    def locator(self, selector: str):
        self.locator_calls.append(selector)
        if selector == DETAIL_READY:
            return self.ready
        if selector == selector_module.DETAIL_SLIDE_CLOSE_BUTTON:
            return self.close_button
        raise AssertionError(f"unexpected slide selector: {selector}")

    async def evaluate(self, expression: str) -> str:
        self.evaluate_calls.append(expression)
        assert expression == "element => element.outerHTML"
        return self.outer_html

    async def wait_for(self, **kwargs: object) -> None:
        self.wait_calls.append(kwargs)


class _MountingSlideReady(_SlideReady):
    def __init__(self, slide: _ActiveSlide) -> None:
        super().__init__()
        self.slide = slide

    async def wait_for(self, **kwargs: object) -> None:
        self.wait_calls.append(kwargs)
        self.slide.match_count = 1


class _MountingSlide(_ActiveSlide):
    def __init__(self) -> None:
        super().__init__(match_count=0)
        self.ready = _MountingSlideReady(self)
        self.close_button = _SlideCloseButton()


class _SlidePage:
    def __init__(self, slide: _ActiveSlide) -> None:
        self.slide = slide
        self.goto_calls: list[str] = []
        self.content_calls = 0

    def locator(self, selector: str) -> _ActiveSlide:
        assert selector == selector_module.DETAIL_SLIDE_ROOT
        return self.slide

    async def goto(self, url: str, **kwargs: object) -> None:
        self.goto_calls.append(url)
        raise AssertionError("slide collection must not navigate")

    async def content(self) -> str:
        self.content_calls += 1
        raise AssertionError("slide collection must not parse full page content")


def _slide_collector() -> PlaywrightNaverLandCollector:
    collector = object.__new__(PlaywrightNaverLandCollector)
    collector.delay = _RecordingDelay()
    return collector


def _stub_slide_parsers(
    monkeypatch,
    *,
    article_id: str = "2637329815",
    captured: dict[str, object] | None = None,
):
    market = MarketDetails()
    article = BrokerArticleDetail(
        article_id=article_id,
        provider="부동산포스",
        is_npay=False,
        market_details=market,
        captured_at=_SLIDE_CAPTURED_AT,
    )

    def fake_parse_article(html: str, **kwargs: object):
        if captured is not None:
            captured["article_html"] = html
            captured["article_kwargs"] = kwargs
        return article

    def fake_parse_market(html: str, **kwargs: object):
        if captured is not None:
            captured["market_html"] = html
            captured["market_kwargs"] = kwargs
        return market

    monkeypatch.setattr(browser_module, "parse_broker_article", fake_parse_article)
    monkeypatch.setattr(browser_module, "parse_market_details", fake_parse_market)
    return article, market


def _run_slide_collection(
    collector: PlaywrightNaverLandCollector,
    page: _SlidePage,
    card: _SlideCard,
    observation: BrokerCardObservation,
    blocked_statuses: set[int],
):
    return asyncio.run(
        collector._collect_slide_article(
            page,
            card,
            observation=observation,
            target=_SLIDE_TARGET,
            article_id="2637329815",
            captured_at=_SLIDE_CAPTURED_AT,
            blocked_statuses=blocked_statuses,
        )
    )


def test_slide_collection_clicks_only_exact_npay_trigger_without_navigation(
    monkeypatch,
) -> None:
    blocked_statuses: set[int] = set()
    card = _SlideCard(blocked_statuses)
    page = _SlidePage(_ActiveSlide())
    collector = _slide_collector()
    article, market = _stub_slide_parsers(monkeypatch)

    result = _run_slide_collection(
        collector,
        page,
        card,
        BrokerCardObservation(
            article_href=_SLIDE_TARGET,
            provider="부동산포스",
            description="",
            is_npay=True,
        ),
        blocked_statuses,
    )

    assert result == (article, market)
    assert len(card.locator_calls) == 1
    assert selector_module.BROKER_NPAY_DETAIL_TRIGGER in card.locator_calls[0]
    assert f"[href='{_SLIDE_TARGET}']" in card.locator_calls[0]
    assert card.npay.has_text.fullmatch("Npay 부동산에서 보기")
    assert card.npay.clicked is True
    assert card.standard.clicked is False
    assert page.goto_calls == []
    assert collector.delay.reasons == [
        "open_article_detail",
        "close_article_detail",
    ]
    assert page.slide.close_button.clicked is True


def test_slide_collection_clicks_only_exact_standard_trigger_without_npay(
    monkeypatch,
) -> None:
    blocked_statuses: set[int] = set()
    card = _SlideCard(
        blocked_statuses,
        npay_available=False,
        standard_available=True,
    )
    page = _SlidePage(_ActiveSlide())
    collector = _slide_collector()
    _stub_slide_parsers(monkeypatch)

    _run_slide_collection(
        collector,
        page,
        card,
        BrokerCardObservation(
            article_href=_SLIDE_TARGET,
            provider="부동산포스",
            description="",
            is_npay=False,
        ),
        blocked_statuses,
    )

    assert len(card.locator_calls) == 1
    assert selector_module.BROKER_STANDARD_DETAIL_TRIGGER.split(", ")[0] in (
        card.locator_calls[0]
    )
    assert card.locator_calls[0].count(f"[href='{_SLIDE_TARGET}']") == 2
    assert card.standard.has_text.fullmatch("매물 보러가기")
    assert card.standard.clicked is True
    assert card.npay.clicked is False
    assert page.goto_calls == []


def test_slide_collection_parses_only_outer_html_and_preserves_metadata(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    blocked_statuses: set[int] = set()
    card = _SlideCard(blocked_statuses)
    page = _SlidePage(_ActiveSlide())
    collector = _slide_collector()
    _stub_slide_parsers(monkeypatch, captured=captured)

    _run_slide_collection(
        collector,
        page,
        card,
        BrokerCardObservation(
            article_href=_SLIDE_TARGET,
            provider="",
            description="",
            is_npay=True,
        ),
        blocked_statuses,
    )

    assert captured["article_html"] == _SLIDE_OUTER_HTML
    assert captured["market_html"] == _SLIDE_OUTER_HTML
    assert captured["article_kwargs"] == {
        "article_url": "https://fin.land.naver.com/articles/2637329815",
        "provider": None,
        "is_npay": True,
        "captured_at": _SLIDE_CAPTURED_AT,
    }
    assert captured["market_kwargs"] == {"captured_at": _SLIDE_CAPTURED_AT}
    assert page.content_calls == 0
    assert page.slide.evaluate_calls == ["element => element.outerHTML"]


def test_slide_collection_closes_with_delays_when_parser_fails(
    monkeypatch,
) -> None:
    blocked_statuses: set[int] = set()
    card = _SlideCard(blocked_statuses)
    page = _SlidePage(_ActiveSlide())
    collector = _slide_collector()

    def fail_parser(html: str, **kwargs: object):
        raise RuntimeError("parser failed")

    monkeypatch.setattr(browser_module, "parse_broker_article", fail_parser)

    with pytest.raises(Exception) as raised:
        _run_slide_collection(
            collector,
            page,
            card,
            BrokerCardObservation(
                article_href=_SLIDE_TARGET,
                provider="부동산포스",
                description="",
                is_npay=True,
            ),
            blocked_statuses,
        )

    assert type(raised.value).__name__ == "_RecoverableDetailParseError"
    assert "parser failed" in str(raised.value.__cause__)
    assert collector.delay.reasons == [
        "open_article_detail",
        "close_article_detail",
    ]
    assert page.slide.close_button.clicked is True
    assert page.slide.wait_calls == [{"state": "hidden", "timeout": 15_000}]


def test_slide_close_failure_is_typed_fatal_not_recoverable_warning(
    monkeypatch,
) -> None:
    blocked_statuses: set[int] = set()
    card = _SlideCard(blocked_statuses)
    slide = _ActiveSlide()
    slide.close_button = _SlideCloseButton(RuntimeError("close failed"))
    page = _SlidePage(slide)
    collector = _slide_collector()
    _stub_slide_parsers(monkeypatch)

    with pytest.raises(SelectorMismatchError) as raised:
        _run_slide_collection(
            collector,
            page,
            card,
            BrokerCardObservation(
                article_href=_SLIDE_TARGET,
                provider="부동산포스",
                description="",
                is_npay=True,
            ),
            blocked_statuses,
        )

    assert isinstance(raised.value.__cause__, RuntimeError)
    assert slide.close_button.clicked is True


def test_slide_collection_rejects_mismatched_article_id_and_closes(
    monkeypatch,
) -> None:
    blocked_statuses: set[int] = set()
    card = _SlideCard(blocked_statuses)
    page = _SlidePage(_ActiveSlide())
    collector = _slide_collector()
    _stub_slide_parsers(monkeypatch, article_id="wrong-article")

    with pytest.raises(SelectorMismatchError):
        _run_slide_collection(
            collector,
            page,
            card,
            BrokerCardObservation(
                article_href=_SLIDE_TARGET,
                provider="부동산포스",
                description="",
                is_npay=True,
            ),
            blocked_statuses,
        )

    assert page.slide.close_button.clicked is True


@pytest.mark.parametrize(
    ("new_blocked_status", "expected_error"),
    [
        (None, SelectorMismatchError),
        (403, BlockedCrawlError),
    ],
)
def test_slide_ready_failure_uses_only_new_blocking_statuses(
    new_blocked_status: int | None,
    expected_error: type[Exception],
) -> None:
    blocked_statuses = {429}
    card = _SlideCard(
        blocked_statuses,
        npay_available=False,
        standard_available=True,
        new_blocked_status=new_blocked_status,
    )
    page = _SlidePage(
        _ActiveSlide(ready_error=RuntimeError("slide not ready"))
    )
    collector = _slide_collector()

    with pytest.raises(expected_error):
        _run_slide_collection(
            collector,
            page,
            card,
            BrokerCardObservation(
                article_href=_SLIDE_TARGET,
                provider="부동산포스",
                description="",
                is_npay=False,
            ),
            blocked_statuses,
        )

    assert page.slide.close_button.clicked is True


@pytest.mark.parametrize(
    ("new_blocked_status", "expected_error"),
    [
        (None, SelectorMismatchError),
        (403, BlockedCrawlError),
    ],
)
def test_zero_match_slide_preserves_typed_readiness_error_without_closing(
    new_blocked_status: int | None,
    expected_error: type[Exception],
) -> None:
    blocked_statuses: set[int] = set()
    card = _SlideCard(
        blocked_statuses,
        npay_available=False,
        standard_available=True,
        new_blocked_status=new_blocked_status,
    )
    slide = _ActiveSlide(match_count=0)
    page = _SlidePage(slide)
    collector = _slide_collector()

    with pytest.raises(expected_error):
        _run_slide_collection(
            collector,
            page,
            card,
            BrokerCardObservation(
                article_href=_SLIDE_TARGET,
                provider="부동산포스",
                description="",
                is_npay=False,
            ),
            blocked_statuses,
        )

    assert slide.count_calls == 1
    assert slide.close_button.clicked is False
    assert collector.delay.reasons == ["open_article_detail"]


def test_repeated_429_after_click_counts_as_new_blocking_response() -> None:
    response_page = _ResponseObserverPage()
    blocked_statuses = browser_module._observe_blocking_responses(response_page)
    response_page.emit(429)
    card = _SlideCard(
        blocked_statuses,
        npay_available=False,
        standard_available=True,
        new_blocked_status=429,
    )
    page = _SlidePage(
        _ActiveSlide(ready_error=RuntimeError("slide not ready"))
    )
    collector = _slide_collector()

    with pytest.raises(BlockedCrawlError):
        _run_slide_collection(
            collector,
            page,
            card,
            BrokerCardObservation(
                article_href=_SLIDE_TARGET,
                provider="부동산포스",
                description="",
                is_npay=False,
            ),
            blocked_statuses,
        )


def test_slide_readiness_wait_allows_initial_zero_match_to_mount(
    monkeypatch,
) -> None:
    blocked_statuses: set[int] = set()
    card = _SlideCard(
        blocked_statuses,
        npay_available=False,
        standard_available=True,
    )
    slide = _MountingSlide()
    page = _SlidePage(slide)
    collector = _slide_collector()
    article, market = _stub_slide_parsers(monkeypatch)

    result = _run_slide_collection(
        collector,
        page,
        card,
        BrokerCardObservation(
            article_href=_SLIDE_TARGET,
            provider="부동산포스",
            description="",
            is_npay=False,
        ),
        blocked_statuses,
    )

    assert result == (article, market)
    assert slide.ready.wait_calls == [
        {"state": "visible", "timeout": 15_000}
    ]
    assert slide.count_calls == 0
    assert slide.close_button.clicked is True
    assert collector.delay.reasons == [
        "open_article_detail",
        "close_article_detail",
    ]


_UI3_CAPTURED_AT = datetime(2026, 7, 25, 6, 0, tzinfo=timezone.utc)


def _ui3_row(
    article_id: str,
    *,
    suffix: str = "",
    href: str | None = None,
    npay: bool = False,
    include_standard_fallback: bool = False,
) -> str:
    target = href or f"/articles/{article_id}"
    if npay:
        links = (
            "<a data-sentry-component='ButtonBoxLink' "
            f"href='{target}'>Npay 부동산에서 보기</a>"
        )
        if include_standard_fallback:
            links += (
                "<a data-nlogs-area='article*l.group' "
                f"href='/articles/{article_id}'>매물 보러가기</a>"
            )
    else:
        links = (
            "<a data-nlogs-area='article*l.group' "
            f"href='{target}'>매물 보러가기</a>"
        )
    return f"<li>{links}<span>{suffix}</span></li>"


def _ui3_article(article_id: str) -> BrokerArticleDetail:
    return BrokerArticleDetail(
        article_id=article_id,
        provider="부동산포스",
        is_npay=False,
        captured_at=_UI3_CAPTURED_AT,
    )


class _Ui3Toggle:
    def __init__(self, available: bool) -> None:
        self.available = available
        self.clicked = False
        self.expanded = False

    @property
    def first(self):
        return self

    async def count(self) -> int:
        return int(self.available)

    async def click(self) -> None:
        self.clicked = True
        self.expanded = not self.expanded

    async def inner_text(self) -> str:
        return "접기" if self.expanded else "펼치기"


class _Ui3Card:
    def __init__(
        self,
        group_html: str,
        rows: list[str],
        *,
        grouped: bool,
        detail_targets: set[str] | None = None,
    ) -> None:
        self.group_html = group_html
        self.rows = rows
        combined_html = " ".join([group_html, *rows])
        self.detail_targets = (
            set(detail_targets)
            if detail_targets is not None
            else {
                f"/articles/{article_id}"
                for article_id in re.findall(
                    r"/articles/([A-Za-z0-9_-]+)",
                    combined_html,
                )
            }
        )
        self.wait_calls: list[dict[str, object]] = []
        self.open_button = _Ui3Toggle(grouped)
        self.single_link = _Ui3Toggle(not grouped)
        self.broker_links = _BrokerLinks(rows)

    def locator(self, selector: str):
        if selector == BROKER_OPEN_BUTTON:
            return self.open_button
        if selector == BROKER_ARTICLE_LINK:
            return self.broker_links
        if selector == SINGLE_ARTICLE_LINK:
            return self.single_link
        match = re.fullmatch(r"a\[href='([^']+)'\]", selector)
        if match is not None:
            return _Ui3Toggle(match.group(1) in self.detail_targets)
        raise AssertionError(f"unexpected UI-3 card selector: {selector}")

    async def evaluate(self, expression: str) -> str:
        assert expression == "element => element.outerHTML"
        return self.group_html

    async def wait_for(self, **kwargs: object) -> None:
        self.wait_calls.append(kwargs)


class _Ui3Keyboard:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.keys: list[str] = []

    async def press(self, key: str) -> None:
        self.keys.append(key)
        if self.error is not None:
            raise self.error


class _Ui3Cards:
    def __init__(self, cards: list[_Ui3Card]) -> None:
        self.cards = cards

    async def count(self) -> int:
        return len(self.cards)

    def nth(self, index: int) -> _Ui3Card:
        return self.cards[index]


class _Ui3ScrollContainer:
    def __init__(self) -> None:
        self.end_states = iter([False, True, True])
        self.mutations = 0

    @property
    def first(self):
        return self

    async def count(self) -> int:
        return 1

    async def evaluate(self, expression: str):
        if "scrollTop + element.clientHeight" in expression:
            return next(self.end_states)
        self.mutations += 1
        return None


class _Ui3Page:
    def __init__(
        self,
        cards: list[_Ui3Card],
        *,
        keyboard_error: Exception | None = None,
    ) -> None:
        self.cards = _Ui3Cards(cards)
        self.container = _Ui3ScrollContainer()
        self.trade_counts = _TradeCountButtons(len(cards))
        self.keyboard = _Ui3Keyboard(keyboard_error)

    def locator(self, selector: str):
        if selector == LISTING_CARD:
            return self.cards
        if selector == LISTING_SCROLL_CONTAINER:
            return self.container
        if selector == TRADE_COUNT_BUTTON:
            return self.trade_counts
        raise AssertionError(f"unexpected UI-3 page selector: {selector}")


class _Ui3Delay:
    EVENT_NAMES = {
        "open_broker_group": "open_group",
        "close_broker_group": "close_group",
        "scroll_listing_list": "scroll_listing_list",
    }

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.reasons: list[str] = []

    async def wait(self, reason: str) -> None:
        self.reasons.append(reason)
        event = self.EVENT_NAMES.get(reason)
        if event is not None:
            self.events.append(event)


class _Ui3ParserFailure(RuntimeError):
    pass


class _Ui3Collector(PlaywrightNaverLandCollector):
    def __init__(
        self,
        *,
        events: list[str] | None = None,
        outcomes: dict[
            str,
            Exception | tuple[BrokerArticleDetail, MarketDetails],
        ]
        | None = None,
    ) -> None:
        self.events = events if events is not None else []
        self.delay = _Ui3Delay(self.events)
        self.outcomes = outcomes or {}
        self.slide_calls: list[str] = []

    async def _card_key(self, card) -> tuple[str, tuple[str, ...]]:
        return card.group_html, tuple(card.rows)

    async def _listing_snapshot(self, page):
        return tuple(
            (card.group_html, tuple(card.rows))
            for card in page.cards.cards
        )

    async def _wait_for_listing_settle(self, page, previous_snapshot) -> None:
        return None

    async def _collect_slide_article(
        self,
        page,
        card,
        *,
        observation,
        target,
        article_id,
        captured_at,
        blocked_statuses,
    ):
        self.slide_calls.append(article_id)
        self.events.append("open_article_detail")
        try:
            outcome = self.outcomes.get(article_id)
            if isinstance(outcome, _Ui3ParserFailure):
                recoverable_type = getattr(
                    browser_module,
                    "_RecoverableDetailParseError",
                    RuntimeError,
                )
                raise recoverable_type(str(outcome))
            if isinstance(outcome, Exception):
                raise outcome
            if outcome is not None:
                return outcome
            return _ui3_article(article_id), MarketDetails(
                captured_at=_UI3_CAPTURED_AT
            )
        finally:
            self.events.append("close_article_detail")


def _run_visible_group(
    collector: PlaywrightNaverLandCollector,
    page: _Ui3Page,
    card: _Ui3Card,
    *,
    scope: CrawlScope,
    seen_article_ids: set[str],
):
    return asyncio.run(
        collector._collect_visible_group(
            page,
            card,
            scope=scope,
            captured_at=_UI3_CAPTURED_AT,
            seen_article_ids=seen_article_ids,
            blocked_statuses=set(),
        )
    )


def test_visible_group_lifecycle_finishes_before_listing_scroll() -> None:
    events: list[str] = []
    row = _ui3_row("1")
    card = _Ui3Card("<li>group 1</li>", [row], grouped=True)
    page = _Ui3Page([card])
    collector = _Ui3Collector(events=events)

    groups, _ = asyncio.run(
        collector._scan_listing_groups(
            page,
            CrawlScope.full(),
            trade_type="매매",
            expected_group_count=1,
            captured_at=_UI3_CAPTURED_AT,
            seen_article_ids=set(),
            blocked_statuses=set(),
        )
    )

    assert isinstance(
        groups[0],
        getattr(browser_module, "CollectedListingGroup", type(None)),
    )
    assert [article.article_id for article in groups[0].articles] == ["1"]
    assert events[:5] == [
        "open_group",
        "open_article_detail",
        "close_article_detail",
        "close_group",
        "scroll_listing_list",
    ]
    assert page.keyboard.keys == []


def test_full_scope_without_details_collects_every_minimal_broker_without_detail_clicks() -> None:
    rows = [_ui3_row("1"), _ui3_row("2")]
    card = _Ui3Card("<li>group</li>", rows, grouped=True)
    collector = _Ui3Collector()
    scope = CrawlScope.full(collect_broker_details=False)

    result = _run_visible_group(
        collector,
        _Ui3Page([card]),
        card,
        scope=scope,
        seen_article_ids=set(),
    )

    assert _is_full_collection(scope) is True
    assert [article.article_id for article in result.articles] == ["1", "2"]
    assert all(article.detail_collected is False for article in result.articles)
    assert collector.slide_calls == []


def test_full_scope_without_details_keeps_broker_count_fail_closed() -> None:
    card = _Ui3Card(
        "<li>중개사 3곳에서 등록했어요</li>",
        [_ui3_row("1"), _ui3_row("2")],
        grouped=True,
    )

    with pytest.raises(IncompleteListingCollectionError):
        _run_visible_group(
            _Ui3Collector(),
            _Ui3Page([card]),
            card,
            scope=CrawlScope.full(collect_broker_details=False),
            seen_article_ids=set(),
        )


def test_visible_group_separates_row_article_and_global_dedupe_and_warnings() -> None:
    row_1 = _ui3_row("1")
    row_2 = _ui3_row("2")
    row_2_other_broker = _ui3_row("2", suffix="other broker")
    row_3 = _ui3_row("3")
    row_4 = _ui3_row("4")
    rows = [row_1, row_2, row_2, row_2_other_broker, row_3, row_4]
    card = _Ui3Card("<li>group</li>", rows, grouped=True)
    page = _Ui3Page([card])
    first_market = MarketDetails(captured_at=_UI3_CAPTURED_AT)
    later_market = MarketDetails(
        extra_fields={"위치": "경기도 화성시"},
        captured_at=_UI3_CAPTURED_AT,
    )
    collector = _Ui3Collector(
        outcomes={
            "2": (_ui3_article("2"), first_market),
            "3": (_ui3_article("3"), later_market),
            "4": _Ui3ParserFailure("parser failed"),
        }
    )
    seen_article_ids: set[str] = set()
    scope = CrawlScope.sampled({"2", "3", "4"})

    first = _run_visible_group(
        collector,
        page,
        card,
        scope=scope,
        seen_article_ids=seen_article_ids,
    )
    second = _run_visible_group(
        collector,
        page,
        card,
        scope=scope,
        seen_article_ids=seen_article_ids,
    )

    assert len(first.broker_rows) == 4
    assert collector.slide_calls == ["2", "3", "4", "4"]
    assert seen_article_ids == {"2", "3"}
    assert [article.article_id for article in first.articles] == ["2", "3"]
    assert first.market_details is first_market
    assert first.address_candidate == "경기도 화성시"
    assert first.warnings == ["detail_collection_failed"]
    assert second.articles == []
    assert second.warnings == ["detail_collection_failed"]


def test_visible_group_does_not_downgrade_non_parser_failure_to_warning() -> None:
    row = _ui3_row("8")
    card = _Ui3Card("<li>group</li>", [row], grouped=True)
    page = _Ui3Page([card])
    collector = _Ui3Collector(
        outcomes={"8": RuntimeError("detail lifecycle failed")}
    )

    with pytest.raises(RuntimeError, match="detail lifecycle failed"):
        _run_visible_group(
            collector,
            page,
            card,
            scope=CrawlScope.full(),
            seen_article_ids=set(),
        )

    assert page.keyboard.keys == []


def test_unsafe_npay_never_falls_back_and_group_close_cannot_mask_error() -> None:
    row = _ui3_row(
        "9",
        href="https://example.com/articles/9",
        npay=True,
        include_standard_fallback=True,
    )
    card = _Ui3Card("<li>unsafe group</li>", [row], grouped=True)
    page = _Ui3Page(
        [card],
        keyboard_error=RuntimeError("group close failed"),
    )
    collector = _Ui3Collector()

    with pytest.raises(UnsafeArticleTarget):
        _run_visible_group(
            collector,
            page,
            card,
            scope=CrawlScope.full(),
            seen_article_ids=set(),
        )

    assert collector.slide_calls == []
    assert page.keyboard.keys == []
    assert collector.delay.reasons == [
        "open_broker_group",
        "close_broker_group",
    ]


def test_single_listing_collects_detail_without_group_open_or_close() -> None:
    row = _ui3_row("7")
    card = _Ui3Card(row, [row], grouped=False)
    page = _Ui3Page([card])
    collector = _Ui3Collector()

    result = _run_visible_group(
        collector,
        page,
        card,
        scope=CrawlScope.full(),
        seen_article_ids=set(),
    )

    assert result.group_html == row
    assert result.broker_rows == [row]
    assert [article.article_id for article in result.articles] == ["7"]
    assert collector.slide_calls == ["7"]
    assert "open_broker_group" not in collector.delay.reasons
    assert "close_broker_group" not in collector.delay.reasons
    assert page.keyboard.keys == []


def test_collect_source_has_one_map_page_and_no_legacy_article_navigation() -> None:
    collect_source = getsource(PlaywrightNaverLandCollector.collect)
    class_source = getsource(PlaywrightNaverLandCollector)

    assert "open_crawler_page(playwright, self.settings)" in collect_source
    assert collect_source.count("page.goto(") == 1
    assert "source_identity.normalized_url" in collect_source
    assert "detail_page" not in collect_source
    assert "_collect_article" not in collect_source
    assert "def _collect_article" not in class_source


class _ExactTargetReacquireCollector(_Ui3Collector):
    def __init__(self, replacement_card: _Ui3Card) -> None:
        super().__init__()
        self.replacement_card = replacement_card
        self.detail_cards: list[_Ui3Card] = []

    async def _collect_slide_article(
        self,
        page,
        card,
        *,
        observation,
        target,
        article_id,
        captured_at,
        blocked_statuses,
    ):
        assert target in card.detail_targets
        assert card.wait_calls == [
            {"state": "visible", "timeout": 8_000}
        ]
        self.detail_cards.append(card)
        if len(self.detail_cards) == 1:
            page.cards.cards[0] = self.replacement_card
        return _ui3_article(article_id), MarketDetails(
            captured_at=_UI3_CAPTURED_AT
        )


def test_each_detail_reacquires_current_card_by_exact_target_after_retarget() -> None:
    row_1 = _ui3_row("1")
    row_2 = _ui3_row("2")
    stale_group_card = _Ui3Card(
        "<li>stale group locator</li>",
        [row_1, row_2],
        grouped=True,
        detail_targets=set(),
    )
    current_first = _Ui3Card(
        "<li>current first render</li>",
        [row_1, row_2],
        grouped=True,
        detail_targets={"/articles/1"},
    )
    current_second = _Ui3Card(
        "<li>current second render</li>",
        [row_1, row_2],
        grouped=True,
        detail_targets={"/articles/2"},
    )
    page = _Ui3Page([current_first])
    collector = _ExactTargetReacquireCollector(current_second)

    result = _run_visible_group(
        collector,
        page,
        stale_group_card,
        scope=CrawlScope.full(),
        seen_article_ids=set(),
    )

    assert [article.article_id for article in result.articles] == ["1", "2"]
    assert collector.detail_cards == [current_first, current_second]


class _RestartViewportPage:
    def __init__(
        self,
        first_cards: list[_Ui3Card],
        current_cards: list[_Ui3Card],
    ) -> None:
        self.first_cards = _Ui3Cards(first_cards)
        self.current_cards = _Ui3Cards(current_cards)
        self.listing_locator_calls = 0
        self.container = _Ui3ScrollContainer()
        self.trade_counts = _TradeCountButtons(len(current_cards))
        self.keyboard = _Ui3Keyboard()

    def locator(self, selector: str):
        if selector == LISTING_CARD:
            self.listing_locator_calls += 1
            if self.listing_locator_calls == 1:
                return self.first_cards
            return self.current_cards
        if selector == LISTING_SCROLL_CONTAINER:
            return self.container
        if selector == TRADE_COUNT_BUTTON:
            return self.trade_counts
        raise AssertionError(f"unexpected restart-page selector: {selector}")


class _RestartViewportCollector(PlaywrightNaverLandCollector):
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.delay = _Ui3Delay(events)

    async def _card_key(self, card) -> tuple[str, tuple[str, ...]]:
        return card.group_html, tuple(card.rows)

    async def _collect_visible_group(
        self,
        page,
        card,
        *,
        scope,
        captured_at,
        seen_article_ids,
        blocked_statuses,
    ):
        self.events.append(f"group:{card.group_html}")
        return browser_module.CollectedListingGroup(
            group_html=card.group_html,
            broker_rows=card.rows,
            articles=[],
            market_details=None,
            warnings=[],
        )

    async def _listing_snapshot(self, page):
        return ()

    async def _wait_for_listing_settle(self, page, previous_snapshot) -> None:
        return None


def test_scan_reenumerates_page_root_after_each_virtual_group() -> None:
    events: list[str] = []
    row_1 = _ui3_row("1")
    row_2 = _ui3_row("2")
    card_1 = _Ui3Card("first", [row_1], grouped=True)
    stale_duplicate = _Ui3Card("first", [row_1], grouped=True)
    card_2 = _Ui3Card("second", [row_2], grouped=True)
    page = _RestartViewportPage(
        [card_1, stale_duplicate],
        [card_1, card_2],
    )
    page.container.end_states = iter([False, True, True, True])
    collector = _RestartViewportCollector(events)

    groups, _ = asyncio.run(
        collector._scan_listing_groups(
            page,
            CrawlScope.full(),
            trade_type="매매",
            expected_group_count=2,
            captured_at=_UI3_CAPTURED_AT,
            seen_article_ids=set(),
            blocked_statuses=set(),
        )
    )

    assert [group.group_html for group in groups] == ["first", "second"]
    assert events[:3] == [
        "group:first",
        "group:second",
        "scroll_listing_list",
    ]


class _AssemblyMapPage:
    def __init__(self) -> None:
        self.goto_calls: list[str] = []
        self.response_callback = None

    def on(self, event: str, callback) -> None:
        assert event == "response"
        self.response_callback = callback

    async def goto(self, url: str, **kwargs: object) -> None:
        self.goto_calls.append(url)

    async def content(self) -> str:
        return "<main>complex panel</main>"

    async def title(self) -> str:
        return "신동탄포레자이"


class _AssemblyContext:
    def __init__(self, page: _AssemblyMapPage) -> None:
        self.page = page
        self.new_page_calls = 0
        self.closed = False

    async def new_page(self) -> _AssemblyMapPage:
        self.new_page_calls += 1
        return self.page

    async def close(self) -> None:
        self.closed = True


class _AssemblyBrowser:
    def __init__(self, context: _AssemblyContext) -> None:
        self.context = context
        self.closed = False

    async def new_context(self) -> _AssemblyContext:
        return self.context

    async def close(self) -> None:
        self.closed = True


class _AssemblyChromium:
    def __init__(self, browser: _AssemblyBrowser) -> None:
        self.browser = browser

    async def launch(self, **kwargs: object) -> _AssemblyBrowser:
        return self.browser


class _AssemblyPlaywright:
    def __init__(self, browser: _AssemblyBrowser) -> None:
        self.chromium = _AssemblyChromium(browser)


class _AssemblyPlaywrightManager:
    def __init__(self, playwright: _AssemblyPlaywright) -> None:
        self.playwright = playwright

    async def __aenter__(self) -> _AssemblyPlaywright:
        return self.playwright

    async def __aexit__(self, *args: object) -> None:
        return None


class _AssemblyCollector(PlaywrightNaverLandCollector):
    def __init__(
        self,
        groups: list[object],
        *,
        attempted_ids: set[str],
    ) -> None:
        self.settings = SimpleNamespace(
            crawler_cdp_url="http://127.0.0.1:42973",
        )
        self.progress = None
        self.delay = _NoDelay()
        self.groups = groups
        self.attempted_ids = attempted_ids
        self.blocking_trackers: list[set[int]] = []

    async def _assert_not_blocked(self, page) -> None:
        return None

    async def _wait_for_complex_link(
        self,
        page,
        *,
        blocked_statuses,
    ) -> None:
        return None

    async def _switch_trade_type(self, page, trade_type: str) -> None:
        return None

    async def _scan_listing_groups(
        self,
        page,
        scope,
        *,
        trade_type,
        expected_group_count,
        captured_at,
        seen_article_ids,
        blocked_statuses,
    ):
        seen_article_ids.update(self.attempted_ids)
        self.blocking_trackers.append(blocked_statuses)
        return self.groups, expected_group_count


def _run_collect_assembly(
    monkeypatch,
    *,
    collector: _AssemblyCollector,
    scope: CrawlScope,
    trade_counts: dict[str, int],
    listings_by_html: dict[str, ListingDetail],
):
    import playwright.async_api as playwright_async_api

    page = _AssemblyMapPage()
    context = _AssemblyContext(page)
    browser = _AssemblyBrowser(context)
    manager = _AssemblyPlaywrightManager(_AssemblyPlaywright(browser))
    monkeypatch.setattr(
        playwright_async_api,
        "async_playwright",
        lambda: manager,
    )
    monkeypatch.setattr(
        browser_module,
        "normalize_source_url",
        lambda source_url: SimpleNamespace(normalized_url="map-source"),
    )
    monkeypatch.setattr(
        browser_module,
        "parse_complex_panel",
        lambda html, title: SimpleNamespace(
            complex_id="131197",
            name="신동탄포레자이",
            trade_counts=trade_counts,
        ),
    )
    monkeypatch.setattr(
        browser_module,
        "parse_live_listing_group",
        lambda html, captured_at: listings_by_html[html],
    )

    payload = asyncio.run(
        collector.collect("https://example.invalid/source", scope=scope)
    )
    return payload, page, context, browser


def test_collect_assembly_uses_success_ids_and_group_warning_for_partial(
    monkeypatch,
) -> None:
    group = browser_module.CollectedListingGroup(
        group_html="sampled-group",
        broker_rows=[_ui3_row("1"), _ui3_row("2")],
        articles=[_ui3_article("1")],
        market_details=MarketDetails(captured_at=_UI3_CAPTURED_AT),
        warnings=["detail_collection_failed"],
        address_candidate="첫 명시 주소",
    )
    collector = _AssemblyCollector(
        [group],
        attempted_ids={"1", "2"},
    )
    listing = ListingDetail(
        trade_type="매매",
        displayed_broker_count=2,
        warnings=["parser_warning"],
        captured_at=_UI3_CAPTURED_AT,
    )

    payload, page, context, browser = _run_collect_assembly(
        monkeypatch,
        collector=collector,
        scope=CrawlScope.sampled({"1", "2"}),
        trade_counts={"매매": 1},
        listings_by_html={"sampled-group": listing},
    )

    assert payload.status == "partial"
    assert payload.warnings == ["expected_article_missing:2"]
    assert payload.apartment.address == "첫 명시 주소"
    assert payload.listings[0].warnings == [
        "parser_warning",
        "detail_collection_failed",
    ]
    assert payload.listings[0].article_ids == frozenset({"1"})
    assert context.new_page_calls == 1
    assert page.goto_calls == ["map-source"]
    assert len(collector.blocking_trackers) == 1
    assert type(collector.blocking_trackers[0]).__name__ == (
        "_BlockingResponseTracker"
    )
    assert context.closed is True
    assert browser.closed is True


def test_collect_assembly_fails_closed_when_full_count_exceeds_groups(
    monkeypatch,
) -> None:
    first_group = browser_module.CollectedListingGroup(
        group_html="first-group",
        broker_rows=[_ui3_row("1"), _ui3_row("missing-broker")],
        articles=[_ui3_article("1")],
        market_details=MarketDetails(captured_at=_UI3_CAPTURED_AT),
        warnings=[],
        address_candidate="첫 주소",
    )
    second_group = browser_module.CollectedListingGroup(
        group_html="second-group",
        broker_rows=[_ui3_row("2")],
        articles=[_ui3_article("2")],
        market_details=MarketDetails(captured_at=_UI3_CAPTURED_AT),
        warnings=[],
        address_candidate="나중 주소",
    )
    collector = _AssemblyCollector(
        [first_group, second_group],
        attempted_ids={"1", "2"},
    )
    first_listing = ListingDetail(
        trade_type="매매",
        displayed_broker_count=2,
        captured_at=_UI3_CAPTURED_AT,
    )
    second_listing = ListingDetail(
        trade_type="매매",
        displayed_broker_count=1,
        captured_at=_UI3_CAPTURED_AT,
    )

    with pytest.raises(
        IncompleteListingCollectionError,
        match="매매 표시 3건 중 2건만 수집했습니다",
    ):
        _run_collect_assembly(
            monkeypatch,
            collector=collector,
            scope=CrawlScope.full(),
            trade_counts={"매매": 3},
            listings_by_html={
                "first-group": first_listing,
                "second-group": second_listing,
            },
        )
