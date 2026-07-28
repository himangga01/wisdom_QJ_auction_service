from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from urllib.parse import urljoin

from app.core.config import Settings, get_settings
from app.crawler.delay import HumanizedDelay
from app.crawler.browser_runtime import open_crawler_page
from app.crawler.errors import (
    AmbiguousSourceError,
    BlockedCrawlError,
    ComplexNotFoundError,
    IncompleteListingCollectionError,
    SelectorMismatchError,
)
from app.crawler.live_dom import (
    BrokerCardObservation,
    parse_complex_panel,
    parse_live_broker_card,
    parse_live_displayed_broker_count,
    parse_live_listing_group,
)
from app.crawler.navigation import (
    UnsafeArticleTarget,
    choose_article_target,
)
from app.crawler.parsers.broker_article import parse_broker_article
from app.crawler.parsers.market_details import parse_market_details
from app.crawler.scope import CrawlScope
from app.crawler.selectors import (
    BLOCKED_TEXT_MARKERS,
    BROKER_ARTICLE_LINK,
    BROKER_NPAY_DETAIL_TRIGGER,
    BROKER_OPEN_BUTTON,
    BROKER_STANDARD_DETAIL_TRIGGER,
    CAPTCHA_TEXT_MARKERS,
    COMPLEX_LINK,
    DETAIL_READY,
    DETAIL_SLIDE_CLOSE_BUTTON,
    DETAIL_SLIDE_ROOT,
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
from app.domain.url_identity import normalize_source_url


ProgressCallback = Callable[[str, int], Awaitable[None]]
_TRADE_SWITCH_POLLS = 80
_TRADE_SWITCH_POLL_SECONDS = 0.1
_COMPLEX_PANEL_POLLS = 50
_COMPLEX_PANEL_POLL_SECONDS = 0.1
_SCROLL_SETTLE_POLLS = 5
_SCROLL_SETTLE_SECONDS = 0.1
_BLOCKING_HTTP_STATUSES = frozenset({403, 429})
_DISPLAYED_TRADE_TYPE = re.compile(
    r"(?<!\S)(매매|전세|월세)\s*(?=\d)"
)


@dataclass(slots=True)
class CollectedListingGroup:
    group_html: str
    broker_rows: list[str]
    articles: list[BrokerArticleDetail]
    market_details: MarketDetails | None
    warnings: list[str]
    address_candidate: str = ""


class _RecoverableDetailParseError(RuntimeError):
    pass


class _BlockingResponseTracker(set[int]):
    def __init__(self) -> None:
        super().__init__()
        self.revision = 0

    def add(self, status: int) -> None:
        super().add(status)
        self.revision += 1


def _iter_nonempty_trade_types(
    scope: CrawlScope,
    trade_counts: Mapping[str, int],
) -> tuple[str, ...]:
    return tuple(
        trade_type
        for trade_type in scope.trade_types
        if trade_counts.get(trade_type, 0) > 0
    )


def _displayed_trade_type(card_text: str) -> str | None:
    match = _DISPLAYED_TRADE_TYPE.search(card_text)
    return match.group(1) if match is not None else None


def _should_scan_group(scope: CrawlScope, *, groups_scanned: int) -> bool:
    limit = scope.max_groups_per_trade_type
    return limit is None or groups_scanned < limit


def _should_visit_article(scope: CrawlScope, article_id: str) -> bool:
    return (
        not scope.expected_article_ids
        or article_id in scope.expected_article_ids
    )


def _is_full_collection(scope: CrawlScope) -> bool:
    return (
        scope.max_groups_per_trade_type is None
        and not scope.expected_article_ids
    )


def _broker_target(
    broker_html: str,
) -> tuple[BrokerCardObservation, str, str]:
    observation = parse_live_broker_card(broker_html)
    target = choose_article_target(
        npay_href=observation.article_href if observation.is_npay else None,
        internal_href=observation.article_href if not observation.is_npay else None,
    )
    return observation, target, target.rsplit("/", 1)[-1]


def _minimal_broker_article(
    *,
    observation: BrokerCardObservation,
    target: str,
    article_id: str,
    captured_at: datetime,
) -> BrokerArticleDetail:
    provider = observation.provider.strip()
    return BrokerArticleDetail(
        article_id=article_id,
        article_url=urljoin("https://fin.land.naver.com", target),
        provider=provider or "미표시",
        is_npay=observation.is_npay,
        detail_collected=False,
        description=observation.description,
        market_details=None,
        warnings=[] if provider else ["provider_missing"],
        captured_at=captured_at,
    )


def _group_contains_expected_article(
    scope: CrawlScope,
    broker_rows: list[str],
) -> bool:
    article_ids = {
        _broker_target(broker_html)[2]
        for broker_html in broker_rows
    }
    return bool(scope.expected_article_ids.intersection(article_ids))


def _explicit_location(details: MarketDetails) -> str:
    return (
        details.location.get("위치")
        or details.extra_fields.get("위치")
        or ""
    ).strip()


def _first_explicit_location(
    current_address: str,
    details: MarketDetails,
) -> str:
    return current_address or _explicit_location(details)


def _append_once(warnings: list[str], warning: str) -> None:
    if warning not in warnings:
        warnings.append(warning)


def _observe_blocking_responses(page) -> _BlockingResponseTracker:
    blocked_statuses = _BlockingResponseTracker()

    def observe(response) -> None:
        if response.status in _BLOCKING_HTTP_STATUSES:
            blocked_statuses.add(response.status)

    page.on("response", observe)
    return blocked_statuses


class PlaywrightNaverLandCollector:
    """Serial collector that opens only validated Naver article targets."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        progress: ProgressCallback | None = None,
        delay: HumanizedDelay | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.progress = progress
        self.delay = delay if delay is not None else HumanizedDelay(
            self.settings.naver_request_delay_min,
            self.settings.naver_request_delay_max,
        )

    async def _progress(self, stage: str, progress: int) -> None:
        if self.progress is not None:
            await self.progress(stage, progress)

    async def _interaction_delay(self, reason: str) -> None:
        await self.delay.wait(reason)

    async def _assert_not_blocked(self, page) -> None:
        body = await page.locator("body").inner_text(timeout=10_000)
        if any(marker.casefold() in body.casefold() for marker in CAPTCHA_TEXT_MARKERS):
            from app.crawler.errors import CaptchaDetectedError

            raise CaptchaDetectedError("CAPTCHA가 표시되어 수집을 중단했습니다.")
        if any(marker.casefold() in body.casefold() for marker in LOGIN_TEXT_MARKERS):
            from app.crawler.errors import LoginRequiredError

            raise LoginRequiredError("로그인이 요구되어 수집을 중단했습니다.")
        if any(marker.casefold() in body.casefold() for marker in BLOCKED_TEXT_MARKERS):
            raise BlockedCrawlError("접근 제한이 표시되어 수집을 중단했습니다.")

    async def _outer_html(self, locator) -> str:
        return await locator.evaluate("element => element.outerHTML")

    async def _wait_for_complex_link(
        self,
        page,
        *,
        blocked_statuses: set[int],
    ) -> None:
        try:
            await page.locator(COMPLEX_LINK).first.wait_for(
                state="visible", timeout=15_000
            )
        except Exception as exc:
            if blocked_statuses:
                raise BlockedCrawlError(
                    "접근 제한 응답이 관찰되어 수집을 중단했습니다."
                ) from exc
            raise SelectorMismatchError(
                "단지 링크 selector를 찾지 못했습니다."
            ) from exc

    async def _parse_stable_complex_panel(self, page):
        last_error: ValueError | None = None
        for _ in range(_COMPLEX_PANEL_POLLS):
            try:
                return parse_complex_panel(
                    await page.content(),
                    title=await page.title(),
                )
            except ValueError as exc:
                last_error = exc
                await asyncio.sleep(_COMPLEX_PANEL_POLL_SECONDS)

        if last_error is None:
            raise ValueError("complex panel is unavailable")
        raise last_error

    async def _current_trade_count(self, page, trade_type: str) -> int:
        buttons = page.locator(TRADE_COUNT_BUTTON)
        pattern = re.compile(
            rf"^\s*{re.escape(trade_type)}\s*([0-9][0-9,]*)\s*$"
        )
        for index in range(await buttons.count()):
            match = pattern.fullmatch(await buttons.nth(index).inner_text())
            if match is not None:
                return int(match.group(1).replace(",", ""))
        raise SelectorMismatchError(
            f"{trade_type} 거래유형의 현재 표시 건수를 읽지 못했습니다."
        )

    async def _switch_trade_type(self, page, trade_type: str) -> None:
        cards = page.locator(LISTING_CARD)
        if await cards.count():
            first_text = await cards.first.inner_text()
            if _displayed_trade_type(first_text) == trade_type:
                await self._reset_listing_scroll(page)
                return

        button = page.locator(TRADE_COUNT_BUTTON).filter(
            has_text=trade_type
        ).first
        if not await button.count():
            raise SelectorMismatchError(
                f"{trade_type} 거래유형 버튼을 찾지 못했습니다."
            )
        await self._interaction_delay(f"switch_trade_type:{trade_type}")
        await button.click()
        await self._reset_listing_scroll(page)

        for _ in range(_TRADE_SWITCH_POLLS):
            if await cards.count():
                first_text = await cards.first.inner_text()
                if _displayed_trade_type(first_text) == trade_type:
                    return
            await asyncio.sleep(_TRADE_SWITCH_POLL_SECONDS)
        raise SelectorMismatchError(
            f"{trade_type} 거래유형의 첫 매물 카드를 확인하지 못했습니다."
        )

    async def _card_key(self, card) -> tuple[str, tuple[str, ...]]:
        key = await card.evaluate(
            """
            element => {
                const clone = element.cloneNode(true);
                const brokerLinks = [
                    ...clone.querySelectorAll(
                        "a[data-nlogs-area='article*l.group']"
                        + "[href^='/articles/']"
                    ),
                ];
                for (const link of brokerLinks) {
                    const row = link.closest("li");
                    if (row && row !== clone) {
                        row.remove();
                    } else {
                        link.remove();
                    }
                }
                for (const button of clone.querySelectorAll(
                    "button[data-nlogs-area='article*l.group']"
                )) {
                    button.textContent = "";
                }
                const visibleText = (clone.textContent || "")
                    .replace(/\\s+/g, " ")
                    .trim();
                const hrefs = [
                    ...clone.querySelectorAll(
                        "a[data-nlogs-area='article*l.list']"
                        + "[href^='/articles/']"
                    ),
                ]
                    .map(node => node.getAttribute("href") || "")
                    .filter(Boolean)
                    .sort();
                return [visibleText, hrefs];
            }
            """
        )
        return str(key[0]), tuple(str(href) for href in key[1])

    async def _current_card_for_target(self, page, target: str):
        exact_link_selector = f"a[href='{target}']"
        try:
            cards = page.locator(LISTING_CARD)
            for index in range(await cards.count()):
                current_card = cards.nth(index)
                if not await current_card.locator(
                    exact_link_selector
                ).count():
                    continue
                await current_card.wait_for(
                    state="visible",
                    timeout=8_000,
                )
                return current_card
        except Exception as exc:
            raise SelectorMismatchError(
                "현재 매물 목록에서 상세 대상 card를 다시 찾지 못했습니다."
            ) from exc
        raise SelectorMismatchError(
            "현재 매물 목록에서 상세 대상 card를 다시 찾지 못했습니다."
        )

    async def _wait_for_expanded_broker_links(self, card):
        broker_links = card.locator(BROKER_ARTICLE_LINK)
        for attempt in range(2):
            try:
                await broker_links.first.wait_for(
                    state="attached",
                    timeout=8_000,
                )
                return broker_links
            except Exception:
                if attempt:
                    raise

                open_button = card.locator(BROKER_OPEN_BUTTON).first
                if not await open_button.count():
                    continue
                if "펼치기" not in await open_button.inner_text():
                    continue
                await self._interaction_delay("retry_open_broker_group")
                await open_button.click()

        return broker_links

    async def _collect_expanded_broker_rows(
        self,
        card,
        expected_count: int | None,
    ) -> list[str]:
        rows_by_article_id: dict[str, str] = {}
        while True:
            broker_links = card.locator(BROKER_ARTICLE_LINK)
            broker_link_count = await broker_links.count()
            for index in range(broker_link_count):
                row_html = await broker_links.nth(index).evaluate(
                    "element => element.closest('li')?.outerHTML || ''"
                )
                if not row_html:
                    raise SelectorMismatchError(
                        "중개사 매물 링크의 li 행을 찾지 못했습니다."
                    )
                try:
                    article_id = _broker_target(row_html)[2]
                except UnsafeArticleTarget:
                    raise
                except ValueError as exc:
                    raise SelectorMismatchError(
                        "중개사 행의 내부 매물 링크를 읽지 못했습니다."
                    ) from exc
                rows_by_article_id.setdefault(article_id, row_html)

            if (
                expected_count is None
                or len(rows_by_article_id) >= expected_count
            ):
                return list(rows_by_article_id.values())

            await self._interaction_delay("scroll_expanded_broker_list")
            await broker_links.last.scroll_into_view_if_needed()
            try:
                await card.locator(BROKER_ARTICLE_LINK).nth(
                    broker_link_count
                ).wait_for(state="attached", timeout=8_000)
            except Exception as exc:
                raise IncompleteListingCollectionError(
                    f"중개사 {expected_count}곳 중 "
                    f"{len(rows_by_article_id)}곳만 목록에서 확인했습니다."
                ) from exc

    async def _collect_visible_group(
        self,
        page,
        card,
        *,
        scope: CrawlScope,
        captured_at: datetime,
        seen_article_ids: set[str],
        blocked_statuses: set[int],
    ) -> CollectedListingGroup:
        group_html = await self._outer_html(card)
        displayed_broker_count = parse_live_displayed_broker_count(
            group_html
        )
        open_button = card.locator(BROKER_OPEN_BUTTON).first
        group_opened = False
        primary_error = False
        if await open_button.count():
            if "접기" not in await open_button.inner_text():
                await self._interaction_delay("open_broker_group")
                await open_button.click()
            group_opened = True

        try:
            if group_opened:
                try:
                    broker_links = await self._wait_for_expanded_broker_links(
                        card
                    )
                except Exception as exc:
                    raise SelectorMismatchError(
                        "펼친 중개사 그룹의 매물 링크를 찾지 못했습니다."
                    ) from exc

                rows = await self._collect_expanded_broker_rows(
                    card,
                    displayed_broker_count,
                )
            elif await card.locator(SINGLE_ARTICLE_LINK).count():
                rows = [group_html]
            else:
                raise SelectorMismatchError(
                    "매물 카드에서 상세 링크를 찾지 못했습니다."
                )

            articles: list[BrokerArticleDetail] = []
            market_details: MarketDetails | None = None
            warnings: list[str] = []
            address_candidate = ""
            for broker_html in rows:
                try:
                    observation, target, article_id = _broker_target(
                        broker_html
                    )
                except UnsafeArticleTarget:
                    raise
                except ValueError as exc:
                    raise SelectorMismatchError(
                        "중개사 행의 내부 매물 링크를 읽지 못했습니다."
                    ) from exc

                if not _should_visit_article(scope, article_id):
                    continue
                if article_id in seen_article_ids:
                    continue

                details: MarketDetails | None = None
                if scope.collect_broker_details:
                    try:
                        current_card = await self._current_card_for_target(
                            page,
                            target,
                        )
                        article, details = await self._collect_slide_article(
                            page,
                            current_card,
                            observation=observation,
                            target=target,
                            article_id=article_id,
                            captured_at=captured_at,
                            blocked_statuses=blocked_statuses,
                        )
                    except _RecoverableDetailParseError:
                        _append_once(warnings, "detail_collection_failed")
                        continue
                else:
                    article = _minimal_broker_article(
                        observation=observation,
                        target=target,
                        article_id=article_id,
                        captured_at=captured_at,
                    )

                seen_article_ids.add(article_id)
                articles.append(article)
                if market_details is None and details is not None:
                    market_details = details
                if details is not None:
                    address_candidate = _first_explicit_location(
                        address_candidate,
                        details,
                    )

            return CollectedListingGroup(
                group_html=group_html,
                broker_rows=rows,
                articles=articles,
                market_details=market_details,
                warnings=warnings,
                address_candidate=address_candidate,
            )
        except BaseException:
            primary_error = True
            raise
        finally:
            if group_opened:
                try:
                    current_button = card.locator(
                        BROKER_OPEN_BUTTON
                    ).first
                    if (
                        await current_button.count()
                        and "접기" in await current_button.inner_text()
                    ):
                        await self._interaction_delay(
                            "close_broker_group"
                        )
                        await current_button.click()
                        for _ in range(_TRADE_SWITCH_POLLS):
                            if (
                                "펼치기"
                                in await current_button.inner_text()
                            ):
                                break
                            await asyncio.sleep(
                                _TRADE_SWITCH_POLL_SECONDS
                            )
                        else:
                            raise SelectorMismatchError(
                                "중개사 매물 목록을 접지 못했습니다."
                            )
                except BaseException:
                    if not primary_error:
                        raise

    async def _listing_snapshot(
        self,
        page,
    ) -> tuple[tuple[str, tuple[str, ...]], ...]:
        cards = page.locator(LISTING_CARD)
        return tuple(
            [
                await self._card_key(cards.nth(index))
                for index in range(await cards.count())
            ]
        )

    async def _wait_for_listing_settle(
        self,
        page,
        previous_snapshot: tuple[tuple[str, tuple[str, ...]], ...],
    ) -> None:
        for _ in range(_SCROLL_SETTLE_POLLS):
            await asyncio.sleep(_SCROLL_SETTLE_SECONDS)
            try:
                current_snapshot = await self._listing_snapshot(page)
            except Exception:
                continue
            if current_snapshot != previous_snapshot:
                return

    async def _wait_for_listing_top(
        self,
        page,
        container,
        previous_snapshot: tuple[tuple[str, tuple[str, ...]], ...],
    ) -> None:
        snapshot_changed = False
        for _ in range(_SCROLL_SETTLE_POLLS):
            await asyncio.sleep(_SCROLL_SETTLE_SECONDS)
            try:
                scroll_top = await container.evaluate(
                    "element => element.scrollTop"
                )
                current_snapshot = await self._listing_snapshot(page)
            except Exception:
                continue
            snapshot_changed = (
                snapshot_changed
                or current_snapshot != previous_snapshot
            )
            if scroll_top == 0 and snapshot_changed:
                return

    async def _reset_listing_scroll(self, page) -> None:
        container = page.locator(LISTING_SCROLL_CONTAINER).first
        if not await container.count():
            return
        scroll_top = await container.evaluate(
            "element => element.scrollTop"
        )
        if scroll_top == 0:
            return

        previous_snapshot = await self._listing_snapshot(page)
        await self._interaction_delay("reset_listing_scroll")
        await container.evaluate(
            "element => { element.scrollTop = 0; }"
        )
        await self._wait_for_listing_top(
            page,
            container,
            previous_snapshot,
        )

    async def _scan_listing_groups(
        self,
        page,
        scope: CrawlScope,
        *,
        trade_type: str,
        expected_group_count: int,
        captured_at: datetime,
        seen_article_ids: set[str],
        blocked_statuses: set[int],
    ) -> tuple[list[CollectedListingGroup], int]:
        seen: set[tuple[str, tuple[str, ...]]] = set()
        groups: list[CollectedListingGroup] = []
        container = page.locator(LISTING_SCROLL_CONTAINER).first
        if not await container.count():
            raise SelectorMismatchError(
                "매물 스크롤 영역을 찾지 못했습니다."
            )

        full_collection = _is_full_collection(scope)
        full_pass_start_count = len(groups)
        latest_count = expected_group_count

        while True:
            while True:
                if not _should_scan_group(scope, groups_scanned=len(groups)):
                    return groups, latest_count

                cards = page.locator(LISTING_CARD)
                card = None
                key = None
                for index in range(await cards.count()):
                    candidate = cards.nth(index)
                    candidate_key = await self._card_key(candidate)
                    if candidate_key in seen:
                        continue
                    card = candidate
                    key = candidate_key
                    break

                if card is None or key is None:
                    break

                seen.add(key)
                group = await self._collect_visible_group(
                    page,
                    card,
                    scope=scope,
                    captured_at=captured_at,
                    seen_article_ids=seen_article_ids,
                    blocked_statuses=blocked_statuses,
                )
                groups.append(group)
                if (
                    scope.expected_article_ids
                    and _group_contains_expected_article(
                        scope,
                        group.broker_rows,
                    )
                ):
                    return groups, latest_count

            if not _should_scan_group(scope, groups_scanned=len(groups)):
                return groups, latest_count

            at_end = await container.evaluate(
                "element => element.scrollTop + element.clientHeight "
                ">= element.scrollHeight - 2"
            )
            if at_end:
                if not full_collection:
                    return groups, latest_count
                latest_count = await self._current_trade_count(
                    page,
                    trade_type,
                )
                if len(groups) >= latest_count:
                    return groups, latest_count
                if len(groups) == full_pass_start_count:
                    raise IncompleteListingCollectionError(
                        f"{trade_type} 표시 {latest_count}건 중 "
                        f"{len(groups)}건만 수집했습니다."
                    )
                full_pass_start_count = len(groups)
                await self._reset_listing_scroll(page)
                continue

            previous_snapshot = await self._listing_snapshot(page)
            await self._interaction_delay("scroll_listing_list")
            await container.evaluate(
                "element => { element.scrollTop = Math.min("
                "element.scrollHeight, element.scrollTop + "
                "Math.max(element.clientHeight, 600)); }"
            )
            await self._wait_for_listing_settle(page, previous_snapshot)

    async def _close_detail_slide(self, slide) -> None:
        try:
            await self._interaction_delay("close_article_detail")
            await slide.locator(DETAIL_SLIDE_CLOSE_BUTTON).first.click()
            await slide.wait_for(state="hidden", timeout=15_000)
        except Exception as exc:
            raise SelectorMismatchError(
                "상세 슬라이드를 닫지 못했습니다."
            ) from exc

    async def _collect_slide_article(
        self,
        page,
        card,
        *,
        observation: BrokerCardObservation,
        target: str,
        article_id: str,
        captured_at: datetime,
        blocked_statuses: set[int],
    ) -> tuple[BrokerArticleDetail, MarketDetails]:
        if observation.is_npay:
            base_selector = BROKER_NPAY_DETAIL_TRIGGER
            trigger_text = "Npay 부동산에서 보기"
        else:
            base_selector = BROKER_STANDARD_DETAIL_TRIGGER
            trigger_text = "매물 보러가기"

        trigger_selector = ", ".join(
            f"{branch}[href='{target}']"
            for branch in base_selector.split(", ")
        )
        trigger = card.locator(trigger_selector).filter(
            has_text=re.compile(f"^{re.escape(trigger_text)}$")
        ).first
        try:
            trigger_exists = bool(await trigger.count())
        except Exception as exc:
            raise SelectorMismatchError(
                "검증된 내부 매물 상세 버튼을 확인하지 못했습니다."
            ) from exc
        if not trigger_exists:
            raise SelectorMismatchError(
                "검증된 내부 매물 상세 버튼을 찾지 못했습니다."
            )

        await self._interaction_delay("open_article_detail")
        blocked_before_click = set(blocked_statuses)
        blocked_revision_before_click = getattr(
            blocked_statuses,
            "revision",
            None,
        )
        try:
            await trigger.click()
        except Exception as exc:
            raise SelectorMismatchError(
                "검증된 내부 매물 상세 버튼을 열지 못했습니다."
            ) from exc

        slide = page.locator(DETAIL_SLIDE_ROOT).last
        slide_ready = False

        def new_blocking_response_observed() -> bool:
            if blocked_statuses - blocked_before_click:
                return True
            current_revision = getattr(blocked_statuses, "revision", None)
            return (
                blocked_revision_before_click is not None
                and current_revision is not None
                and current_revision > blocked_revision_before_click
            )

        try:
            try:
                await slide.locator(DETAIL_READY).first.wait_for(
                    state="visible", timeout=15_000
                )
            except Exception as exc:
                if new_blocking_response_observed():
                    raise BlockedCrawlError(
                        "상세 슬라이드를 여는 중 접근 제한 응답이 관찰되었습니다."
                    ) from exc
                raise SelectorMismatchError(
                    "활성 상세 슬라이드의 매물번호를 찾지 못했습니다."
                ) from exc
            slide_ready = True

            try:
                html = await self._outer_html(slide)
            except Exception as exc:
                raise SelectorMismatchError(
                    "활성 상세 슬라이드 HTML을 읽지 못했습니다."
                ) from exc
            article_url = urljoin("https://fin.land.naver.com", target)
            try:
                article = parse_broker_article(
                    html,
                    article_url=article_url,
                    provider=observation.provider or None,
                    is_npay=observation.is_npay,
                    captured_at=captured_at,
                )
            except Exception as exc:
                raise _RecoverableDetailParseError(
                    "중개사 매물 상세 파싱에 실패했습니다."
                ) from exc
            if article.article_id != article_id:
                raise SelectorMismatchError(
                    "활성 상세 슬라이드의 매물번호가 예상 값과 다릅니다."
                )
            try:
                market_details = parse_market_details(
                    html,
                    captured_at=captured_at,
                )
            except Exception as exc:
                raise _RecoverableDetailParseError(
                    "시세 상세 파싱에 실패했습니다."
                ) from exc
            return article.model_copy(
                update={"market_details": market_details}
            ), market_details
        finally:
            slide_exists = slide_ready
            if not slide_exists:
                try:
                    slide_exists = bool(await slide.count())
                except Exception as exc:
                    raise SelectorMismatchError(
                        "활성 상세 슬라이드 상태를 확인하지 못했습니다."
                    ) from exc
            if slide_exists:
                await self._close_detail_slide(slide)

    async def collect(
        self,
        source_url: str,
        *,
        scope: CrawlScope | None = None,
    ) -> CrawlPayload:
        active_scope = scope if scope is not None else CrawlScope.full()
        source_identity = normalize_source_url(source_url)
        captured_at = datetime.now(timezone.utc)
        await self._progress("complex", 10)

        from playwright.async_api import async_playwright

        async with (
            async_playwright() as playwright,
            open_crawler_page(playwright, self.settings) as page,
        ):
            blocked_statuses = _observe_blocking_responses(page)
            try:
                await self._interaction_delay("navigate_source")
                await page.goto(
                    source_identity.normalized_url,
                    wait_until="domcontentloaded",
                )
                await self._assert_not_blocked(page)
                await self._wait_for_complex_link(
                    page,
                    blocked_statuses=blocked_statuses,
                )
                try:
                    panel = await self._parse_stable_complex_panel(page)
                except ValueError as exc:
                    if "ambiguous" in str(exc):
                        raise AmbiguousSourceError(
                            "URL에서 아파트 단지 하나를 확정할 수 없습니다."
                        ) from exc
                    if "complex link" in str(exc):
                        raise ComplexNotFoundError(
                            "아파트 단지 식별 정보를 찾지 못했습니다."
                        ) from exc
                    raise SelectorMismatchError(
                        "단지 거래유형 정보를 읽지 못했습니다."
                    ) from exc

                trade_counts = dict(panel.trade_counts)
                apartment = ComplexDetail(
                    complex_id=panel.complex_id,
                    name=panel.name,
                    address="",
                    captured_at=captured_at,
                )

                await self._progress("listings", 25)
                listings: list[ListingDetail] = []
                payload_warnings: list[str] = []
                partial = False
                seen_article_ids: set[str] = set()
                collected_article_ids: set[str] = set()
                address = ""
                full_collection = _is_full_collection(active_scope)

                for trade_type in _iter_nonempty_trade_types(
                    active_scope, trade_counts
                ):
                    await self._switch_trade_type(page, trade_type)
                    collected_groups, latest_count = (
                        await self._scan_listing_groups(
                            page,
                            active_scope,
                            trade_type=trade_type,
                            expected_group_count=trade_counts[trade_type],
                            captured_at=captured_at,
                            seen_article_ids=seen_article_ids,
                            blocked_statuses=blocked_statuses,
                        )
                    )
                    trade_counts[trade_type] = latest_count
                    if (
                        full_collection
                        and latest_count > len(collected_groups)
                    ):
                        raise IncompleteListingCollectionError(
                            f"{trade_type} 표시 {latest_count}건 중 "
                            f"{len(collected_groups)}건만 수집했습니다."
                        )

                    for group in collected_groups:
                        try:
                            listing = parse_live_listing_group(
                                group.group_html,
                                captured_at=captured_at,
                            )
                        except ValueError as exc:
                            raise SelectorMismatchError(
                                "매물 카드의 표시 정보를 읽지 못했습니다."
                            ) from exc

                        expected_broker_count = (
                            listing.displayed_broker_count
                            if listing.displayed_broker_count is not None
                            else len(
                                {
                                    _broker_target(row_html)[2]
                                    for row_html in group.broker_rows
                                }
                            )
                        )
                        actual_broker_count = len(group.articles)
                        if (
                            full_collection
                            and actual_broker_count != expected_broker_count
                        ):
                            raise IncompleteListingCollectionError(
                                f"중개사 표시 {expected_broker_count}건 중 "
                                f"{actual_broker_count}건의 상세만 수집했습니다."
                            )
                        if full_collection and group.warnings:
                            raise IncompleteListingCollectionError(
                                "물건 상세 수집 경고"
                                f"(표시 {expected_broker_count}건, "
                                f"실제 {actual_broker_count}건): "
                                + ", ".join(group.warnings)
                            )

                        listing_warnings = list(listing.warnings)
                        for warning in group.warnings:
                            _append_once(listing_warnings, warning)
                        if group.warnings:
                            partial = True

                        collected_article_ids.update(
                            article.article_id
                            for article in group.articles
                        )
                        if group.address_candidate:
                            address = address or group.address_candidate

                        listings.append(
                            listing.model_copy(
                                update={
                                    "broker_articles": group.articles,
                                    "market_details": group.market_details,
                                    "warnings": listing_warnings,
                                }
                            )
                        )

                for article_id in sorted(
                    active_scope.expected_article_ids
                    - collected_article_ids
                ):
                    partial = True
                    payload_warnings.append(
                        f"expected_article_missing:{article_id}"
                    )

                await self._progress("details", 70)
                return CrawlPayload(
                    status="partial" if partial else "completed",
                    apartment=apartment.model_copy(
                        update={"address": address}
                    ),
                    listings=listings,
                    trade_counts=trade_counts,
                    displayed_listing_count=sum(
                        trade_counts.get(trade_type, 0)
                        for trade_type in active_scope.trade_types
                    ),
                    warnings=payload_warnings,
                    captured_at=captured_at,
                )
            finally:
                pass
