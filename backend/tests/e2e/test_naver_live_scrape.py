from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from functools import cache
import os
from pathlib import Path

import pytest

from app.crawler.errors import BlockedCrawlError
from tests.e2e.comparison import ComparisonReport, compare_case
from tests.e2e.artifact_safety import (
    safe_case_artifact_path,
    write_artifact_json,
)
from tests.e2e.reference_loader import (
    GptCaseObservation,
    load_manifest,
    load_reference,
    source_url_for_case,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CURRENT_REFERENCE_PATH = Path(
    os.getenv(
        "GPT_NAVER_REFERENCE_PATH",
        str(
            REPOSITORY_ROOT
            / "temp"
            / "e2e"
            / "reference"
            / "current"
            / "reference.json"
        ),
    )
)
LOCAL_MANIFEST_PATH = Path(
    os.getenv(
        "GPT_NAVER_CASE_MANIFEST_PATH",
        str(
            REPOSITORY_ROOT
            / "temp"
            / "e2e"
            / "reference"
            / "case-manifest.local.json"
        ),
    )
)
DIFF_ROOT = REPOSITORY_ROOT / "temp" / "e2e" / "naver-live"
REFERENCE_MAX_AGE = timedelta(minutes=30)


def _fail_e2e_blocked(exc: BlockedCrawlError) -> None:
    pytest.fail(f"E2E_BLOCKED: {exc.code}", pytrace=False)


@cache
def _load_current_reference():
    return load_reference(
        CURRENT_REFERENCE_PATH,
        now=datetime.now(timezone.utc),
        max_age=REFERENCE_MAX_AGE,
    )


@cache
def _load_local_manifest():
    return load_manifest(LOCAL_MANIFEST_PATH)


def _load_live_case(case_id: str) -> tuple[GptCaseObservation, str]:
    reference = _load_current_reference()
    expected = next(
        (case for case in reference.cases if case.case_id == case_id),
        None,
    )
    assert expected is not None, "requested case ID is absent from reference"
    source_url = source_url_for_case(_load_local_manifest(), case_id)
    return expected, source_url


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
            crawler_cdp_url=cdp_url,
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
                    crawler_cdp_url=cdp_url,
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
    diff_path = safe_case_artifact_path(
        DIFF_ROOT,
        report.case_id,
        "diff.json",
    )
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    write_artifact_json(diff_path, report.model_dump(mode="json"))
    return diff_path


@pytest.mark.live_naver
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_NAVER_E2E") != "1",
    reason="set RUN_LIVE_NAVER_E2E=1 to run sampled Naver live E2E",
)
def test_sampled_naver_live_scrape() -> None:
    from app.crawler.scope import CrawlScope

    case_id = os.getenv("NAVER_E2E_CASE_ID")
    assert case_id, "NAVER_E2E_CASE_ID is required"
    expected, source_url = _load_live_case(case_id)
    assert _load_current_reference().mode == "sample"
    article_ids = {article.article_id for article in expected.articles}
    try:
        actual = asyncio.run(
            _collector().collect(
                source_url,
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

    reference = _load_current_reference()
    assert reference.mode == "full"

    async def collect_and_compare() -> None:
        collector = _collector()
        for expected in reference.cases:
            source_url = source_url_for_case(
                _load_local_manifest(),
                expected.case_id,
            )
            try:
                actual = await collector.collect(
                    source_url,
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

    case_id = os.getenv("NAVER_E2E_CASE_ID")
    assert case_id, "NAVER_E2E_CASE_ID is required"
    _, source_url = _load_live_case(case_id)

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
