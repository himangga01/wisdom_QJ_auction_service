from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from functools import cache
import os
from pathlib import Path

import pytest

from app.crawler.errors import BlockedCrawlError
from tests.e2e.comparison import ComparisonReport, compare_case
from tests.e2e.reference_schema import GptCaseObservation, load_reference


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SAMPLED_REFERENCE_PATH = (
    Path(__file__).parent / "reference" / "gpt_naver_observations.json"
)
DIFF_ROOT = REPOSITORY_ROOT / "temp" / "e2e" / "naver-live"
REFERENCE_MAX_AGE = timedelta(minutes=30)
SAMPLED_CASE_IDS = ("case-131197", "case-155817", "case-22746")


def _fail_e2e_blocked(exc: BlockedCrawlError) -> None:
    pytest.fail(f"E2E_BLOCKED: {exc.code}", pytrace=False)


@cache
def _load_sampled_reference():
    return load_reference(
        SAMPLED_REFERENCE_PATH,
        now=datetime.now(timezone.utc),
        max_age=REFERENCE_MAX_AGE,
    )


def _load_sampled_case(case_id: str) -> GptCaseObservation:
    reference = _load_sampled_reference()
    assert reference.mode == "sample"
    return next(case for case in reference.cases if case.case_id == case_id)


def _collector():
    from app.core.config import Settings
    from app.crawler.browser import PlaywrightNaverLandCollector
    from app.crawler.delay import HumanizedDelay

    cdp_url = os.getenv(
        "NAVER_E2E_CDP_URL",
        "http://127.0.0.1:42973",
    )
    return PlaywrightNaverLandCollector(
        settings=Settings(
            app_runtime="local",
            crawler_browser_mode="external_chrome",
            crawler_cdp_url=cdp_url,
            crawler_headless=False,
            _env_file=None,
        ),
        delay=HumanizedDelay(1.0, 3.0),
    )


def _counting_collector():
    from app.core.config import Settings
    from app.crawler.browser import PlaywrightNaverLandCollector
    from app.crawler.delay import HumanizedDelay

    class DetailCountingCollector(PlaywrightNaverLandCollector):
        def __init__(self) -> None:
            cdp_url = os.getenv(
                "NAVER_E2E_CDP_URL",
                "http://127.0.0.1:42973",
            )
            super().__init__(
                settings=Settings(
                    app_runtime="local",
                    crawler_browser_mode="external_chrome",
                    crawler_cdp_url=cdp_url,
                    crawler_headless=False,
                    _env_file=None,
                ),
                delay=HumanizedDelay(1.0, 3.0),
            )
            self.detail_slide_calls = 0

        async def _collect_slide_article(self, *args, **kwargs):
            self.detail_slide_calls += 1
            return await super()._collect_slide_article(*args, **kwargs)

    return DetailCountingCollector()


def _write_diff(report: ComparisonReport) -> Path:
    diff_path = DIFF_ROOT / report.case_id / "diff.json"
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return diff_path


@pytest.mark.live_naver
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_NAVER_E2E") != "1",
    reason="set RUN_LIVE_NAVER_E2E=1 to run sampled Naver live E2E",
)
@pytest.mark.parametrize("case_id", SAMPLED_CASE_IDS)
def test_sampled_naver_live_scrape(case_id: str) -> None:
    from app.crawler.scope import CrawlScope

    expected = _load_sampled_case(case_id)
    article_ids = {article.article_id for article in expected.articles}
    try:
        actual = asyncio.run(
            _collector().collect(
                expected.source_url,
                scope=CrawlScope.sampled(article_ids),
            )
        )
    except BlockedCrawlError as exc:
        _fail_e2e_blocked(exc)

    report = compare_case(expected, actual)
    diff_path = _write_diff(report)
    assert report.ok, f"live comparison failed; see {diff_path}"


@pytest.mark.live_naver_full
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_NAVER_FULL_E2E") != "1",
    reason="set RUN_LIVE_NAVER_FULL_E2E=1 to run exhaustive Naver live E2E",
)
def test_full_naver_live_scrape() -> None:
    from app.crawler.scope import CrawlScope

    reference_path = os.getenv("GPT_NAVER_FULL_REFERENCE_PATH")
    assert reference_path is not None, (
        "GPT_NAVER_FULL_REFERENCE_PATH is required for exhaustive live E2E"
    )
    reference = load_reference(
        Path(reference_path),
        now=datetime.now(timezone.utc),
        max_age=REFERENCE_MAX_AGE,
    )
    assert reference.mode == "full"

    async def collect_and_compare() -> None:
        collector = _collector()
        for expected in reference.cases:
            try:
                actual = await collector.collect(
                    expected.source_url,
                    scope=CrawlScope.full(),
                )
            except BlockedCrawlError as exc:
                _fail_e2e_blocked(exc)
            report = compare_case(expected, actual)
            diff_path = _write_diff(report)
            assert report.ok, f"live comparison failed; see {diff_path}"

    asyncio.run(collect_and_compare())


@pytest.mark.live_naver_full
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_NAVER_OPTION_E2E") != "1",
    reason="set RUN_LIVE_NAVER_OPTION_E2E=1 to run one-apartment option E2E",
)
def test_one_apartment_detail_collection_on_and_off() -> None:
    from app.crawler.scope import CrawlScope

    source_url = os.getenv("NAVER_OPTION_E2E_SOURCE_URL")
    assert source_url is not None, (
        "NAVER_OPTION_E2E_SOURCE_URL is required for the one-apartment option E2E"
    )

    async def collect_both_modes() -> None:
        off_collector = _counting_collector()
        off_payload = await off_collector.collect(
            source_url,
            scope=CrawlScope.full(collect_broker_details=False),
        )
        off_articles = [
            article
            for listing in off_payload.listings
            for article in listing.broker_articles
        ]

        assert off_collector.detail_slide_calls == 0
        assert off_articles
        assert all(article.detail_collected is False for article in off_articles)
        assert all(article.market_details is None for article in off_articles)
        print(
            "OPTION_E2E_OFF_COMPLETE "
            f"groups={len(off_payload.listings)} "
            f"articles={len(off_articles)} "
            "detail_slide_calls=0",
            flush=True,
        )

        on_collector = _counting_collector()
        on_payload = await on_collector.collect(
            source_url,
            scope=CrawlScope.full(collect_broker_details=True),
        )
        on_articles = [
            article
            for listing in on_payload.listings
            for article in listing.broker_articles
        ]

        assert on_articles
        assert on_collector.detail_slide_calls == len(on_articles)
        assert all(article.detail_collected is True for article in on_articles)
        print(
            "OPTION_E2E_ON_COMPLETE "
            f"groups={len(on_payload.listings)} "
            f"articles={len(on_articles)} "
            f"detail_slide_calls={on_collector.detail_slide_calls}",
            flush=True,
        )

        off_ids = {article.article_id for article in off_articles}
        on_ids = {article.article_id for article in on_articles}
        assert off_ids & on_ids
        assert abs(len(off_payload.listings) - len(on_payload.listings)) <= 2
        assert abs(len(off_ids) - len(on_ids)) <= 2

    try:
        asyncio.run(collect_both_modes())
    except BlockedCrawlError as exc:
        _fail_e2e_blocked(exc)
