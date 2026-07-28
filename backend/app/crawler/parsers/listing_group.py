from __future__ import annotations

from datetime import datetime
import re

from ..types import ListingDetail
from ._html import (
    clean_text,
    data_fields,
    first_node_with_attribute,
    labeled_values,
    parse_decimal,
    parse_html,
    parse_integer,
    parse_money,
)


_FIELD_ALIASES = {
    "sourcegroupid": "source_group_id",
    "source_group_id": "source_group_id",
    "groupid": "source_group_id",
    "group_id": "source_group_id",
    "tradetype": "trade_type",
    "trade_type": "trade_type",
    "price": "price",
    "deposit": "deposit",
    "monthlyrent": "monthly_rent",
    "monthly_rent": "monthly_rent",
    "building": "building",
    "floor": "floor",
    "direction": "direction",
    "supplyarea": "supply_area",
    "supply_area": "supply_area",
    "exclusivearea": "exclusive_area",
    "exclusive_area": "exclusive_area",
    "displayedbrokercount": "displayed_broker_count",
    "displayed_broker_count": "displayed_broker_count",
    "brokercount": "displayed_broker_count",
    "broker_count": "displayed_broker_count",
}

_LABEL_FIELDS = {
    "거래유형": "trade_type",
    "가격": "price",
    "매매가": "price",
    "보증금": "deposit",
    "월세": "monthly_rent",
    "동": "building",
    "층": "floor",
    "방향": "direction",
    "공급면적": "supply_area",
    "전용면적": "exclusive_area",
    "중개사수": "displayed_broker_count",
}


def _canonical_field(name: str) -> str:
    normalized = re.sub(r"[-\s]", "_", name.strip()).casefold()
    return _FIELD_ALIASES.get(
        normalized, _FIELD_ALIASES.get(normalized.replace("_", ""), normalized)
    )


def _canonical_label(label: str) -> str:
    return re.sub(r"\s+", "", label)


def parse_listing_group(
    html: str, *, captured_at: datetime | None = None
) -> ListingDetail:
    document = parse_html(html)
    group_root = first_node_with_attribute(document, "data-group-id") or document
    values: dict[str, str] = {}
    for item in data_fields(group_root):
        key = _canonical_field(item.name)
        if key not in values or (not values[key] and item.value):
            values[key] = item.value
    for item in labeled_values(group_root):
        key = _LABEL_FIELDS.get(_canonical_label(item.label))
        if key is not None and (key not in values or not values[key]):
            values[key] = item.value

    source_group_id = clean_text(
        group_root.attrs.get("data-group-id", "")
        or values.get("source_group_id", "")
    ) or None
    trade_type = clean_text(values.get("trade_type", ""))
    if not trade_type:
        raise ValueError("listing trade type is missing")

    displayed_broker_count = parse_integer(values.get("displayed_broker_count"))
    if displayed_broker_count is None:
        count_match = re.search(
            r"중개사\s*(?P<count>\d[\d,]*)\s*곳", group_root.text()
        )
        if count_match is not None:
            displayed_broker_count = int(count_match.group("count").replace(",", ""))

    model_values: dict[str, object] = {
        "source_group_id": source_group_id,
        "trade_type": trade_type,
        "price": parse_money(values.get("price")),
        "deposit": parse_money(values.get("deposit")),
        "monthly_rent": parse_money(values.get("monthly_rent")),
        "building": values.get("building") or None,
        "floor": values.get("floor") or None,
        "direction": values.get("direction") or None,
        "supply_area": parse_decimal(values.get("supply_area")),
        "exclusive_area": parse_decimal(values.get("exclusive_area")),
        "displayed_broker_count": displayed_broker_count,
    }
    if captured_at is not None:
        model_values["captured_at"] = captured_at
    return ListingDetail(**model_values)
