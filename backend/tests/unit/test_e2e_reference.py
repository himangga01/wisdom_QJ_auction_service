from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest

from app.crawler.types import (
    BrokerArticleDetail,
    ComplexDetail,
    CrawlPayload,
    ListingDetail,
)
from tests.e2e.comparison import compare_case
from tests.e2e.reference_schema import (
    GptArticleObservation,
    GptCaseObservation,
    ReferenceStaleError,
    load_reference,
)


CAPTURED_AT = datetime(2026, 7, 24, tzinfo=timezone.utc)


def expected_article(**overrides: object) -> GptArticleObservation:
    values: dict[str, object] = {
        "article_id": "article-1",
        "trade_type": "매매",
        "price": 720_000_000,
        "building": "107동",
        "floor": "12 / 25층",
        "direction": "남향",
        "supply_area_m2": Decimal("84.12"),
        "exclusive_area_m2": Decimal("59.99"),
        "displayed_broker_count": 2,
        "option_tags": ["시스템에어컨 2대", "중문"],
        "move_in_date": "2026년 8월 협의",
        "required_detail_fields": {"관리 방식": "위탁 관리"},
    }
    values.update(overrides)
    return GptArticleObservation(**values)


def expected_case(
    *,
    article: GptArticleObservation | None = None,
    **overrides: object,
) -> GptCaseObservation:
    values: dict[str, object] = {
        "case_id": "case-131197",
        "source_url_sha256": "0" * 64,
        "complex_id": "131197",
        "complex_name": "샘플 아파트",
        "trade_counts": {"매매": 1},
        "articles": [article or expected_article()],
    }
    values.update(overrides)
    return GptCaseObservation(**values)


def actual_payload(
    *,
    article_id: str = "article-1",
    price: int | None = 720_000_000,
    building: str | None = "107동",
    floor: str | None = "12 / 25층",
    direction: str | None = "남향",
    supply_area: Decimal | None = Decimal("84.12"),
    exclusive_area: Decimal | None = Decimal("59.99"),
    displayed_broker_count: int | None = 2,
    option_tags: list[str] | None = None,
    move_in_date: str | None = "2026년 8월 협의",
    extra_fields: dict[str, str] | None = None,
    article_price: int | None = None,
    article_floor: str | None = None,
    article_direction: str | None = None,
    article_supply_area: Decimal | None = None,
    article_exclusive_area: Decimal | None = None,
    trade_counts: dict[str, int] | None = None,
    complex_id: str = "131197",
    complex_name: str = "샘플 아파트",
) -> CrawlPayload:
    article = BrokerArticleDetail(
        article_id=article_id,
        provider="네이버부동산",
        is_npay=True,
        advertised_price=article_price,
        floor=article_floor,
        direction=article_direction,
        supply_area_m2=article_supply_area,
        exclusive_area_m2=article_exclusive_area,
        option_tags=option_tags
        if option_tags is not None
        else ["시스템에어컨 2대", "중문"],
        move_in_date=move_in_date,
        extra_fields=extra_fields
        if extra_fields is not None
        else {"관리 방식": "위탁 관리"},
        captured_at=CAPTURED_AT,
    )
    listing = ListingDetail(
        trade_type="매매",
        price=price,
        building=building,
        floor=floor,
        direction=direction,
        supply_area=supply_area,
        exclusive_area=exclusive_area,
        displayed_broker_count=displayed_broker_count,
        broker_articles=[article],
        captured_at=CAPTURED_AT,
    )
    return CrawlPayload(
        status="completed",
        apartment=ComplexDetail(
            complex_id=complex_id,
            name=complex_name,
            address="서울시 샘플구",
            captured_at=CAPTURED_AT,
        ),
        listings=[listing],
        trade_counts={} if trade_counts is None else trade_counts,
        displayed_listing_count=1,
        captured_at=CAPTURED_AT,
    )


class ReferenceText:
    def __init__(self, text: str) -> None:
        self.text = text

    def read_text(self, *, encoding: str) -> str:
        assert encoding == "utf-8"
        return self.text


def reference_text(*, captured_at: str) -> ReferenceText:
    document = {
        "schemaVersion": "2",
        "captureTool": "gpt_browser_manual",
        "mode": "sample",
        "capturedAt": captured_at,
        "normalizationVersion": "2",
        "cases": [
            {
                "caseId": "case-131197",
                "sourceUrlSha256": "0" * 64,
                "complexId": "131197",
                "complexName": "샘플 아파트",
                "tradeCounts": {"매매": 1},
                "articles": [
                    {
                        "articleId": "article-1",
                        "tradeType": "매매",
                        "price": 720_000_000,
                        "building": "107동",
                        "floor": "12 / 25층",
                        "direction": "남향",
                        "supplyAreaM2": "84.12",
                        "exclusiveAreaM2": "59.99",
                        "displayedBrokerCount": 2,
                        "optionTags": ["중문"],
                        "moveInDate": "2026년 8월 협의",
                        "requiredDetailFields": {"관리 방식": "위탁 관리"},
                    }
                ],
            }
        ],
    }
    return ReferenceText(json.dumps(document, ensure_ascii=False))


def test_reference_at_thirty_minutes_is_valid_with_timezone_aware_utc_comparison() -> None:
    path = reference_text(captured_at="2026-07-24T09:00:00+09:00")
    reference = load_reference(
        path,
        now=datetime(2026, 7, 24, 0, 30, tzinfo=timezone.utc),
        max_age=timedelta(minutes=30),
    )

    assert reference.captured_at == datetime(2026, 7, 24, tzinfo=timezone.utc)


def test_reference_older_than_thirty_minutes_is_rejected() -> None:
    path = reference_text(captured_at="2026-07-24T00:00:00Z")
    with pytest.raises(ReferenceStaleError) as raised:
        load_reference(
            path,
            now=datetime(
                2026,
                7,
                24,
                0,
                30,
                0,
                1,
                tzinfo=timezone.utc,
            ),
            max_age=timedelta(minutes=30),
        )

    assert raised.value.code == "reference_stale"


def test_comparison_normalizes_whitespace_area_options_and_detail_fields() -> None:
    expected = expected_case(
        complex_name="  샘플   아파트 ",
        article=expected_article(
            building=" 107동   A라인 ",
            floor=" 12  /  25층 ",
            direction=" 남향 ",
            supply_area_m2=Decimal("84.124"),
            exclusive_area_m2=Decimal("59.997"),
            option_tags=[" 중문 ", "시스템에어컨  2대", "중문"],
            move_in_date=" 2026년   8월 협의 ",
            required_detail_fields={" 관리   방식 ": " 위탁   관리 "},
        ),
    )
    actual = actual_payload(
        building="107동 A라인",
        floor="12 / 25층",
        supply_area=Decimal("84.123"),
        exclusive_area=Decimal("60.001"),
        option_tags=["시스템에어컨 2대", "중문", "중문"],
        extra_fields={"관리 방식": "위탁 관리"},
    )

    report = compare_case(expected, actual)

    assert report.ok is True
    assert report.differences == []


def test_article_detail_values_take_precedence_over_group_listing_values() -> None:
    expected = expected_case(
        article=expected_article(
            price=730_000_000,
            floor="저/27층",
            direction="동향",
            supply_area_m2=Decimal("85.13"),
            exclusive_area_m2=Decimal("60.01"),
        )
    )
    actual = actual_payload(
        price=720_000_000,
        floor="9/27층",
        direction="남향",
        supply_area=Decimal("84.12"),
        exclusive_area=Decimal("59.99"),
        article_price=730_000_000,
        article_floor="저/27층",
        article_direction="동향",
        article_supply_area=Decimal("85.13"),
        article_exclusive_area=Decimal("60.01"),
    )

    report = compare_case(expected, actual)

    assert report.ok is True
    assert report.differences == []


def test_price_is_compared_as_integer_won() -> None:
    report = compare_case(expected_case(), actual_payload(price=720_000_001))

    assert [
        (difference.code, difference.path)
        for difference in report.differences
    ] == [("field_mismatch", "articles[article-1].price")]
    assert report.differences[0].expected == 720_000_000
    assert report.differences[0].actual == 720_000_001


def test_area_is_compared_at_decimal_point_zero_one() -> None:
    expected = expected_case(
        article=expected_article(supply_area_m2=Decimal("84.124"))
    )

    report = compare_case(
        expected,
        actual_payload(supply_area=Decimal("84.126")),
    )

    assert [
        (difference.code, difference.path)
        for difference in report.differences
    ] == [("field_mismatch", "articles[article-1].supply_area_m2")]
    assert report.differences[0].expected == Decimal("84.12")
    assert report.differences[0].actual == Decimal("84.13")


def test_missing_expected_options_are_reported_as_a_structured_difference() -> None:
    report = compare_case(expected_case(), actual_payload(option_tags=[]))

    assert [
        (difference.code, difference.path)
        for difference in report.differences
    ] == [("missing_expected_field", "articles[article-1].option_tags")]


def test_missing_required_detail_field_is_reported() -> None:
    report = compare_case(expected_case(), actual_payload(extra_fields={}))

    assert [
        (difference.code, difference.path)
        for difference in report.differences
    ] == [
        (
            "missing_expected_field",
            "articles[article-1].required_detail_fields.관리 방식",
        )
    ]
    assert report.differences[0].actual is None


def test_missing_expected_article_is_reported() -> None:
    report = compare_case(expected_case(), actual_payload(article_id="article-2"))

    assert [
        (difference.code, difference.path)
        for difference in report.differences
    ] == [("missing_expected_article", "articles[article-1]")]


def test_complex_identity_name_and_trade_count_mismatches_are_reported() -> None:
    expected = expected_case(trade_counts={"매매": 4})

    report = compare_case(
        expected,
        actual_payload(complex_id="999999", complex_name="다른 아파트"),
    )

    assert {
        (difference.code, difference.path)
        for difference in report.differences
    } >= {
        ("complex_identity_mismatch", "apartment.complex_id"),
        ("complex_name_mismatch", "apartment.name"),
        ("trade_count_mismatch", "trade_counts"),
    }


def test_live_count_drift_within_two_is_tolerated() -> None:
    expected = expected_case(trade_counts={"매매": 100})
    actual = actual_payload(
        trade_counts={"매매": 102},
        displayed_broker_count=4,
    )

    report = compare_case(expected, actual)

    assert report.ok is True
    assert report.differences == []


def test_live_count_drift_over_two_is_reported() -> None:
    expected = expected_case(trade_counts={"매매": 100})
    actual = actual_payload(
        trade_counts={"매매": 103},
        displayed_broker_count=5,
    )

    report = compare_case(expected, actual)

    assert {
        (difference.code, difference.path)
        for difference in report.differences
    } == {
        ("trade_count_mismatch", "trade_counts"),
        (
            "field_mismatch",
            "articles[article-1].displayed_broker_count",
        ),
    }


def test_explicit_payload_trade_counts_take_precedence_and_fill_expected_zero() -> None:
    expected = expected_case(
        trade_counts={"매매": 53, "전세": 2, "월세": 0}
    )
    actual = actual_payload(trade_counts={" 매매 ": 53, "전세": 2})

    report = compare_case(expected, actual)

    assert report.ok is True
    assert report.differences == []


def test_serialized_diff_does_not_contain_a_full_naver_url() -> None:
    expected = expected_case(
        article=expected_article(
            required_detail_fields={
                "관련 링크": "https://fin.land.naver.com/articles/article-1?token=secret"
            }
        )
    )

    report = compare_case(expected, actual_payload(extra_fields={}))
    serialized = report.model_dump_json()

    assert "https://fin.land.naver.com/" not in serialized
    assert "case-131197" in serialized
