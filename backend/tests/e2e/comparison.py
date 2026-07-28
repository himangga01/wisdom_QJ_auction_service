from __future__ import annotations

from collections import Counter
from decimal import Decimal
import re
from typing import Any

from pydantic import BaseModel

from app.crawler.types import (
    BrokerArticleDetail,
    CrawlPayload,
    ListingDetail,
)
from tests.e2e.reference_schema import GptCaseObservation


AREA_QUANTUM = Decimal("0.01")
LIVE_COUNT_TOLERANCE = 2
NAVER_URL = re.compile(
    r"https://fin\.land\.naver\.com/[^\s\"'<>]+",
    flags=re.IGNORECASE,
)


class Difference(BaseModel):
    code: str
    path: str
    expected: object
    actual: object


class ComparisonReport(BaseModel):
    case_id: str
    differences: list[Difference]

    @property
    def ok(self) -> bool:
        return not self.differences


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _normalize_optional_text(value: str | None) -> str | None:
    return None if value is None else _normalize_text(value)


def _quantize_area(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(AREA_QUANTUM)


def _normalize_options(values: list[str]) -> set[str]:
    return {_normalize_text(value) for value in values}


def _count_within_live_tolerance(
    expected: int,
    actual: int | None,
) -> bool:
    return (
        actual is not None
        and abs(expected - actual) <= LIVE_COUNT_TOLERANCE
    )


def _sanitize(value: Any, case_id: str) -> Any:
    if isinstance(value, str):
        return NAVER_URL.sub(case_id, value)
    if isinstance(value, dict):
        return {
            _sanitize(key, case_id): _sanitize(item, case_id)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_sanitize(item, case_id) for item in value]
    return value


def _difference(
    *,
    case_id: str,
    code: str,
    path: str,
    expected: object,
    actual: object,
) -> Difference:
    return Difference(
        code=code,
        path=_sanitize(path, case_id),
        expected=_sanitize(expected, case_id),
        actual=_sanitize(actual, case_id),
    )


def _actual_trade_counts(
    expected_counts: dict[str, int],
    actual: CrawlPayload,
) -> dict[str, int]:
    if actual.trade_counts:
        explicit_counts = {
            _normalize_text(trade_type): count
            for trade_type, count in actual.trade_counts.items()
        }
        for trade_type in expected_counts:
            explicit_counts.setdefault(trade_type, 0)
        return explicit_counts

    counts = Counter(
        _normalize_text(listing.trade_type) for listing in actual.listings
    )
    if len(counts) == 1 and actual.displayed_listing_count is not None:
        only_trade_type = next(iter(counts))
        counts[only_trade_type] = actual.displayed_listing_count

    normalized = {
        _normalize_text(trade_type): count
        for trade_type, count in counts.items()
    }
    for trade_type in expected_counts:
        normalized.setdefault(trade_type, 0)
    return normalized


def _find_actual_article(
    actual: CrawlPayload,
    article_id: str,
) -> tuple[ListingDetail, BrokerArticleDetail] | None:
    normalized_id = _normalize_text(article_id)
    for listing in actual.listings:
        for article in listing.broker_articles:
            if _normalize_text(article.article_id) == normalized_id:
                return listing, article
    return None


def _append_field_difference(
    differences: list[Difference],
    *,
    case_id: str,
    path: str,
    expected: object,
    actual: object,
) -> None:
    if expected is None:
        return
    code = "missing_expected_field" if actual is None else "field_mismatch"
    if expected != actual:
        differences.append(
            _difference(
                case_id=case_id,
                code=code,
                path=path,
                expected=expected,
                actual=actual,
            )
        )


def _detail_values(article: BrokerArticleDetail) -> dict[str, str]:
    values: dict[str, str] = {}
    for field_name in (
        "provider",
        "is_npay",
        "advertised_price",
        "price_per_3_3m2",
        "management_fee",
        "loan_description",
        "supply_area_m2",
        "exclusive_area_m2",
        "exclusive_rate",
        "floor",
        "room_count",
        "bathroom_count",
        "direction",
        "structure",
        "verified_at",
        "first_published_at",
    ):
        value = getattr(article, field_name)
        if value is not None:
            values[_normalize_text(field_name)] = _normalize_text(str(value))
    values.update(
        {
            _normalize_text(key): _normalize_text(value)
            for key, value in article.extra_fields.items()
        }
    )
    return values


def _compare_article(
    *,
    case_id: str,
    expected: Any,
    listing: ListingDetail,
    article: BrokerArticleDetail,
    differences: list[Difference],
) -> None:
    base_path = f"articles[{_normalize_text(expected.article_id)}]"
    scalar_fields = (
        (
            "trade_type",
            _normalize_text(expected.trade_type),
            _normalize_text(listing.trade_type),
        ),
        (
            "price",
            expected.price,
            (
                article.advertised_price
                if article.advertised_price is not None
                else listing.price
            ),
        ),
        (
            "building",
            _normalize_optional_text(expected.building),
            _normalize_optional_text(listing.building),
        ),
        (
            "floor",
            _normalize_optional_text(expected.floor),
            _normalize_optional_text(
                article.floor if article.floor is not None else listing.floor
            ),
        ),
        (
            "direction",
            _normalize_optional_text(expected.direction),
            _normalize_optional_text(
                article.direction
                if article.direction is not None
                else listing.direction
            ),
        ),
        (
            "supply_area_m2",
            _quantize_area(expected.supply_area_m2),
            _quantize_area(
                article.supply_area_m2
                if article.supply_area_m2 is not None
                else listing.supply_area
            ),
        ),
        (
            "exclusive_area_m2",
            _quantize_area(expected.exclusive_area_m2),
            _quantize_area(
                article.exclusive_area_m2
                if article.exclusive_area_m2 is not None
                else listing.exclusive_area
            ),
        ),
        (
            "move_in_date",
            _normalize_optional_text(expected.move_in_date),
            _normalize_optional_text(article.move_in_date),
        ),
    )
    for field_name, expected_value, actual_value in scalar_fields:
        _append_field_difference(
            differences,
            case_id=case_id,
            path=f"{base_path}.{field_name}",
            expected=expected_value,
            actual=actual_value,
        )

    if not _count_within_live_tolerance(
        expected.displayed_broker_count,
        listing.displayed_broker_count,
    ):
        _append_field_difference(
            differences,
            case_id=case_id,
            path=f"{base_path}.displayed_broker_count",
            expected=expected.displayed_broker_count,
            actual=listing.displayed_broker_count,
        )

    expected_options = _normalize_options(expected.option_tags)
    actual_options = _normalize_options(article.option_tags)
    if expected_options != actual_options:
        differences.append(
            _difference(
                case_id=case_id,
                code=(
                    "missing_expected_field"
                    if expected_options and not actual_options
                    else "field_mismatch"
                ),
                path=f"{base_path}.option_tags",
                expected=sorted(expected_options),
                actual=sorted(actual_options),
            )
        )

    actual_details = _detail_values(article)
    for raw_key, raw_expected_value in expected.required_detail_fields.items():
        key = _normalize_text(raw_key)
        expected_value = _normalize_text(raw_expected_value)
        actual_value = actual_details.get(key)
        _append_field_difference(
            differences,
            case_id=case_id,
            path=f"{base_path}.required_detail_fields.{key}",
            expected=expected_value,
            actual=actual_value,
        )


def compare_case(
    expected: GptCaseObservation,
    actual: CrawlPayload,
) -> ComparisonReport:
    differences: list[Difference] = []
    case_id = expected.case_id

    expected_complex_id = _normalize_text(expected.complex_id)
    actual_complex_id = _normalize_text(actual.apartment.complex_id)
    if expected_complex_id != actual_complex_id:
        differences.append(
            _difference(
                case_id=case_id,
                code="complex_identity_mismatch",
                path="apartment.complex_id",
                expected=expected_complex_id,
                actual=actual_complex_id,
            )
        )

    expected_name = _normalize_text(expected.complex_name)
    actual_name = _normalize_text(actual.apartment.name)
    if expected_name != actual_name:
        differences.append(
            _difference(
                case_id=case_id,
                code="complex_name_mismatch",
                path="apartment.name",
                expected=expected_name,
                actual=actual_name,
            )
        )

    expected_counts = {
        _normalize_text(trade_type): count
        for trade_type, count in expected.trade_counts.items()
    }
    actual_counts = _actual_trade_counts(expected_counts, actual)
    counts_match = (
        expected_counts.keys() == actual_counts.keys()
        and all(
            _count_within_live_tolerance(
                expected_count,
                actual_counts.get(trade_type),
            )
            for trade_type, expected_count in expected_counts.items()
        )
    )
    if not counts_match:
        differences.append(
            _difference(
                case_id=case_id,
                code="trade_count_mismatch",
                path="trade_counts",
                expected=expected_counts,
                actual=actual_counts,
            )
        )

    for expected_article in expected.articles:
        found = _find_actual_article(actual, expected_article.article_id)
        article_path = (
            f"articles[{_normalize_text(expected_article.article_id)}]"
        )
        if found is None:
            differences.append(
                _difference(
                    case_id=case_id,
                    code="missing_expected_article",
                    path=article_path,
                    expected=expected_article.article_id,
                    actual=None,
                )
            )
            continue
        listing, article = found
        _compare_article(
            case_id=case_id,
            expected=expected_article,
            listing=listing,
            article=article,
            differences=differences,
        )

    return ComparisonReport(case_id=case_id, differences=differences)
