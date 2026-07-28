from pathlib import Path

import pytest

from app.crawler.navigation import (
    UnsafeArticleTarget,
    choose_article_target,
    extract_article_candidates,
    reconcile_broker_count,
)


FIXTURE = Path(__file__).parents[1] / "fixtures" / "complex_page.html"


def test_npay_internal_article_is_selected_and_bridge_is_ignored() -> None:
    candidates = extract_article_candidates(FIXTURE.read_text(encoding="utf-8"))

    assert candidates[0].npay_href == "/articles/2407000001"
    assert choose_article_target(
        npay_href=candidates[0].npay_href,
        internal_href=candidates[0].internal_href,
    ) == "/articles/2407000001"


def test_invalid_npay_never_falls_back_to_another_link() -> None:
    with pytest.raises(UnsafeArticleTarget):
        choose_article_target(
            npay_href="/out-link-bridge?articleId=1",
            internal_href="/articles/1",
        )


@pytest.mark.parametrize(
    "href",
    [
        "https://example.com/articles/1",
        "https://fin.land.naver.com.evil.example/articles/1",
        "/out-link-bridge?articleId=1",
    ],
)
def test_external_or_bridge_targets_are_rejected(href: str) -> None:
    with pytest.raises(UnsafeArticleTarget):
        choose_article_target(npay_href=href, internal_href=None)


def test_broker_count_mismatch_is_partial() -> None:
    assert reconcile_broker_count(displayed_count=3, collected_count=2) == "partial"
    assert reconcile_broker_count(displayed_count=2, collected_count=2) == "completed"
