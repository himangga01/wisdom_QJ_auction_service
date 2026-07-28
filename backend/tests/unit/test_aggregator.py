from datetime import datetime, timezone
from decimal import Decimal

from app.crawler.types import BrokerArticleDetail
from app.domain.aggregator import aggregate_broker_articles
from app.domain.listing_identity import (
    ExistingListingIdentity,
    ListingIdentityInput,
    build_identity_key,
    choose_existing_listing,
)


NOW = datetime(2026, 7, 22, tzinfo=timezone.utc)


def article(article_id: str, **values) -> BrokerArticleDetail:
    return BrokerArticleDetail(
        article_id=article_id,
        provider="네이버부동산",
        is_npay=True,
        description="",
        captured_at=NOW,
        **values,
    )


def test_aggregate_is_deterministic_and_keeps_conflicts_visible() -> None:
    first = article(
        "1",
        management_fee=250_000,
        loan_description="융자 없음",
        move_in_date="즉시입주 협의",
        room_count=3,
        bathroom_count=2,
        option_tags=["에어컨 3대", "식세기", "전자 계약"],
    )
    second = article(
        "2",
        management_fee=330_000,
        move_in_date="즉시입주",
        room_count=4,
        bathroom_count=2,
        option_tags=["시에 4대", "식기세척기", "전자계약"],
    )

    forward = aggregate_broker_articles([first, second])
    reverse = aggregate_broker_articles([second, first])

    assert forward == reverse
    assert forward.option_tags == ["시스템에어컨 3~4대", "식기세척기", "전자계약"]
    assert forward.move_in_summary == "즉시입주 1곳 · 즉시입주 협의 1곳"
    assert forward.management_fee_summary == "25만원 ~ 33만원"
    assert forward.loan_summary == "융자 없음 1곳 · 미표기 1곳"
    assert forward.source_count == 2
    assert "management_fee_conflict" in forward.warnings


def test_article_overlap_preserves_group_when_price_changes() -> None:
    before = ListingIdentityInput(
        complex_id="12345",
        trade_type="매매",
        building="107동",
        exclusive_area=Decimal("84.99"),
        floor="12/25층",
        direction="남향",
        normalized_price=720_000_000,
        article_ids=frozenset({"1", "2"}),
    )
    after = before.model_copy(
        update={"normalized_price": 698_000_000, "article_ids": frozenset({"2", "3"})}
    )
    existing = ExistingListingIdentity(
        listing_group_id="group-id",
        identity_key=build_identity_key(before),
        input=before,
    )

    assert build_identity_key(before) != build_identity_key(after)
    assert choose_existing_listing(after, [existing]) == existing
