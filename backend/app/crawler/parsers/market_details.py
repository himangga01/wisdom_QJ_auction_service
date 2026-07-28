from __future__ import annotations

from datetime import datetime
import re

from ..types import MarketDetails
from ._html import (
    HtmlNode,
    LabeledValue,
    clean_text,
    data_fields,
    iter_nodes,
    labeled_values,
    parse_html,
)


_CATEGORY_LABELS = {
    "finance": {
        "대출한도",
        "ltv",
        "kb시세",
        "금리",
        "예상월원리금",
        "예상원리금",
    },
    "transactions": {
        "동일면적호가범위",
        "동일면적매물수",
        "동일면적매물",
        "평균매매가",
        "평균전세가",
        "매매전세갭",
        "매매·전세갭",
        "전세가율",
        "2년최고",
        "2년최저",
        "최근실거래",
    },
    "costs": {"중개보수", "취득세", "재산세", "종합부동산세"},
    "maintenance": {
        "관리비기준월",
        "기준월",
        "월평균관리비",
        "여름관리비",
        "겨울관리비",
    },
    "complex": {
        "세대수",
        "동수",
        "사용승인일",
        "승인일",
        "주차",
        "주차대수",
        "난방",
        "난방방식",
        "현관",
        "현관구조",
        "용적률",
        "건폐율",
        "시공사",
        "관리사무소",
    },
    "location": {"개발예정", "배정학교", "지하철", "버스"},
}

_FIELD_CATEGORIES = {
    "loan_limit": "finance",
    "ltv": "finance",
    "kb_price": "finance",
    "interest_rate": "finance",
    "expected_monthly_payment": "finance",
    "asking_price_range": "transactions",
    "listing_count": "transactions",
    "average_sale_price": "transactions",
    "average_lease_price": "transactions",
    "sale_lease_gap": "transactions",
    "two_year_high": "transactions",
    "two_year_low": "transactions",
    "recent_transaction": "transactions",
    "brokerage_fee": "costs",
    "acquisition_tax": "costs",
    "property_tax": "costs",
    "comprehensive_property_tax": "costs",
    "maintenance_base_month": "maintenance",
    "average_maintenance_fee": "maintenance",
    "summer_maintenance_fee": "maintenance",
    "winter_maintenance_fee": "maintenance",
    "household_count": "complex",
    "building_count": "complex",
    "approval_date": "complex",
    "parking": "complex",
    "heating": "complex",
    "entrance": "complex",
    "floor_area_ratio": "complex",
    "building_coverage_ratio": "complex",
    "builder": "complex",
    "management_office": "complex",
    "development_plan": "location",
    "assigned_school": "location",
    "subway": "location",
    "bus": "location",
}


def _normalized_label(label: str) -> str:
    return re.sub(r"\s+", "", label).casefold()


def _label_category(label: str) -> str | None:
    normalized = _normalized_label(label)
    for category, labels in _CATEGORY_LABELS.items():
        if normalized in labels:
            return category
    return None


def _field_category(field_name: str) -> tuple[str | None, str]:
    normalized = re.sub(r"[-\s]", "_", field_name.strip()).casefold()
    for category in _CATEGORY_LABELS:
        prefix = f"{category}."
        if normalized.startswith(prefix):
            return category, field_name[len(prefix) :]
    return _FIELD_CATEGORIES.get(normalized), field_name


def _live_labeled_values(root: HtmlNode) -> list[LabeledValue]:
    result: list[LabeledValue] = []
    seen: set[tuple[str, str]] = set()
    for parent in [root, *iter_nodes(root)]:
        children = [
            item for item in parent.content if isinstance(item, HtmlNode)
        ]
        if len(children) != 2:
            continue
        label_node, value_node = children
        if label_node.tag not in {"div", "span", "strong", "p"}:
            continue
        label = clean_text(label_node.text())
        value = clean_text(value_node.text())
        pair = (label, value)
        if label and value and pair not in seen:
            result.append(LabeledValue(label, value, None, None))
            seen.add(pair)
    return result


def parse_market_details(
    html: str, *, captured_at: datetime | None = None
) -> MarketDetails:
    document = parse_html(html)
    sections: dict[str, dict[str, str]] = {
        "finance": {},
        "transactions": {},
        "costs": {},
        "maintenance": {},
        "complex": {},
        "location": {},
    }
    extras: dict[str, str] = {}
    consumed_field_nodes: set[int] = set()

    for item in [*labeled_values(document), *_live_labeled_values(document)]:
        category = _label_category(item.label)
        if category is None and item.field_name is not None:
            category, _ = _field_category(item.field_name)
        if category is None:
            extras[item.field_name or item.label] = item.value
        else:
            sections[category][item.label] = item.value
        if item.field_node is not None:
            consumed_field_nodes.add(id(item.field_node))

    for item in data_fields(document):
        if id(item.node) in consumed_field_nodes:
            continue
        category, key = _field_category(item.name)
        if category is None:
            extras[item.name] = item.value
        else:
            sections[category][key] = item.value

    model_values: dict[str, object] = {
        **sections,
        "extra_fields": extras,
    }
    if captured_at is not None:
        model_values["captured_at"] = captured_at
    return MarketDetails(**model_values)
