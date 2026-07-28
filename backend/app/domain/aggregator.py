from __future__ import annotations

from collections import Counter, defaultdict

from pydantic import BaseModel, Field

from app.crawler.types import BrokerArticleDetail
from app.domain.normalizer import (
    classify_loan,
    format_won_in_manwon,
    normalize_move_in,
    normalize_option,
)


class AggregatedListingInfo(BaseModel):
    option_tags: list[str] = Field(default_factory=list)
    move_in_summary: str = ""
    management_fee_summary: str = ""
    room_bath_summary: str = ""
    loan_summary: str = ""
    source_count: int = 0
    warnings: list[str] = Field(default_factory=list)


def _unique_articles(
    articles: list[BrokerArticleDetail],
) -> list[BrokerArticleDetail]:
    by_id: dict[str, BrokerArticleDetail] = {}
    for article in sorted(articles, key=lambda item: item.article_id):
        by_id.setdefault(article.article_id, article)
    return list(by_id.values())


def _aggregate_options(
    articles: list[BrokerArticleDetail], warnings: set[str]
) -> list[str]:
    counts: dict[str, set[int]] = defaultdict(set)
    unspecified: set[str] = set()
    for article in articles:
        for raw_option in article.option_tags:
            option, count = normalize_option(raw_option)
            if not option:
                continue
            if count is None:
                unspecified.add(option)
            else:
                counts[option].add(count)

    result: list[str] = []
    for option in sorted(set(counts) | unspecified):
        option_counts = sorted(counts.get(option, set()))
        if len(option_counts) > 1:
            result.append(f"{option} {option_counts[0]}~{option_counts[-1]}대")
            warnings.add(f"option_count_conflict:{option}")
        elif option_counts and option not in unspecified:
            result.append(f"{option} {option_counts[0]}대")
        else:
            result.append(option)
            if option_counts:
                warnings.add(f"option_count_conflict:{option}")
    return result


def _count_summary(values: Counter[str]) -> str:
    return " · ".join(f"{value} {count}곳" for value, count in sorted(values.items()))


def aggregate_broker_articles(
    articles: list[BrokerArticleDetail],
) -> AggregatedListingInfo:
    unique = _unique_articles(articles)
    warnings = {warning for article in unique for warning in article.warnings}

    option_tags = _aggregate_options(unique, warnings)

    move_ins = Counter(
        value
        for article in unique
        if (value := normalize_move_in(article.move_in_date)) is not None
    )
    if len(move_ins) > 1:
        warnings.add("move_in_conflict")

    fees = sorted(
        {article.management_fee for article in unique if article.management_fee is not None}
    )
    if len(fees) > 1:
        warnings.add("management_fee_conflict")
    if not fees:
        fee_summary = ""
    elif len(fees) == 1:
        fee_summary = format_won_in_manwon(fees[0])
    else:
        fee_summary = (
            f"{format_won_in_manwon(fees[0])} ~ {format_won_in_manwon(fees[-1])}"
        )

    room_bath = Counter(
        (article.room_count, article.bathroom_count)
        for article in unique
        if article.room_count is not None or article.bathroom_count is not None
    )
    if len(room_bath) > 1:
        warnings.add("room_bath_conflict")
    room_bath_summary = " · ".join(
        f"방 {rooms if rooms is not None else '-'} · 욕실 {baths if baths is not None else '-'} {count}곳"
        for (rooms, baths), count in sorted(
            room_bath.items(), key=lambda item: ((item[0][0] or -1), (item[0][1] or -1))
        )
    )

    loan_counts = Counter(classify_loan(article.loan_description) for article in unique)
    loan_order = ("융자 없음", "정보 표기", "미표기")
    loan_summary = " · ".join(
        f"{label} {loan_counts[label]}곳" for label in loan_order if loan_counts[label]
    )
    if sum(1 for label in loan_order if loan_counts[label]) > 1:
        warnings.add("loan_conflict")

    return AggregatedListingInfo(
        option_tags=option_tags,
        move_in_summary=_count_summary(move_ins),
        management_fee_summary=fee_summary,
        room_bath_summary=room_bath_summary,
        loan_summary=loan_summary,
        source_count=len(unique),
        warnings=sorted(warnings),
    )

