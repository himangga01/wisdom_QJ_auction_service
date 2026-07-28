from __future__ import annotations

from datetime import datetime
import re
from urllib.parse import urlsplit

from ..types import BrokerArticleDetail, RealtorProfile
from ._html import (
    DataField,
    HtmlNode,
    LabeledValue,
    clean_text,
    data_fields,
    first_node_with_attribute,
    iter_nodes,
    labeled_values,
    money_values,
    option_values,
    parse_boolean,
    parse_date,
    parse_decimal,
    parse_html,
    parse_integer,
    parse_money,
)


_FIELD_ALIASES = {
    "articleid": "article_id",
    "article_id": "article_id",
    "provider": "provider",
    "isnpay": "is_npay",
    "is_npay": "is_npay",
    "advertisedprice": "advertised_price",
    "advertised_price": "advertised_price",
    "priceper3_3m2": "price_per_3_3m2",
    "price_per_3_3m2": "price_per_3_3m2",
    "managementfee": "management_fee",
    "management_fee": "management_fee",
    "loandescription": "loan_description",
    "loan_description": "loan_description",
    "supplyarea": "supply_area_m2",
    "supplyaream2": "supply_area_m2",
    "supply_area": "supply_area_m2",
    "supply_area_m2": "supply_area_m2",
    "exclusivearea": "exclusive_area_m2",
    "exclusiveaream2": "exclusive_area_m2",
    "exclusive_area": "exclusive_area_m2",
    "exclusive_area_m2": "exclusive_area_m2",
    "exclusiverate": "exclusive_rate",
    "exclusive_rate": "exclusive_rate",
    "floor": "floor",
    "currentfloor": "current_floor",
    "current_floor": "current_floor",
    "totalfloor": "total_floor",
    "total_floor": "total_floor",
    "roombathcount": "room_bath_count",
    "room_bath_count": "room_bath_count",
    "roomcount": "room_count",
    "room_count": "room_count",
    "bathroomcount": "bathroom_count",
    "bathroom_count": "bathroom_count",
    "direction": "direction",
    "structure": "structure",
    "moveindate": "move_in_date",
    "move_in_date": "move_in_date",
    "description": "description",
    "verifiedat": "verified_at",
    "verified_at": "verified_at",
    "firstpublishedat": "first_published_at",
    "first_published_at": "first_published_at",
    "realtor.name": "realtor.name",
    "realtor.representative": "realtor.representative",
    "realtor.phone": "realtor.phone",
    "realtor.registrationnumber": "realtor.registration_number",
    "realtor.registration_number": "realtor.registration_number",
    "realtor.address": "realtor.address",
}

_LABEL_FIELDS = {
    "매물번호": "article_id",
    "제공처": "provider",
    "네이버페이": "is_npay",
    "표시가격": "advertised_price",
    "매매가": "advertised_price",
    "전세가": "advertised_price",
    "3.3㎡당가격": "price_per_3_3m2",
    "관리비": "management_fee",
    "융자": "loan_description",
    "공급면적": "supply_area_m2",
    "전용면적": "exclusive_area_m2",
    "전용률": "exclusive_rate",
    "층": "floor",
    "해당층/총층": "floor",
    "해당층": "current_floor",
    "총층": "total_floor",
    "방수": "room_count",
    "욕실수": "bathroom_count",
    "방수/욕실수": "room_bath_count",
    "방향": "direction",
    "향": "direction",
    "구조": "structure",
    "복층여부": "structure",
    "입주가능일": "move_in_date",
    "매물설명": "description",
    "매물소개": "description",
    "매물확인일": "verified_at",
    "최초등록일": "first_published_at",
    "중개사명": "realtor.name",
    "대표자": "realtor.representative",
    "전화번호": "realtor.phone",
    "등록번호": "realtor.registration_number",
    "중개사주소": "realtor.address",
}

_REALTOR_FIELDS = (
    "realtor.name",
    "realtor.representative",
    "realtor.phone",
    "realtor.registration_number",
    "realtor.address",
)


def _canonical_field(name: str) -> str:
    normalized = re.sub(r"[-\s]", "_", name.strip()).casefold()
    compact = normalized.replace("_", "")
    return _FIELD_ALIASES.get(normalized, _FIELD_ALIASES.get(compact, normalized))


def _canonical_label(label: str) -> str:
    return re.sub(r"\s+", "", label)


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


def _safe_article_id(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.netloc and not (parsed.hostname or "").endswith(".naver.com"):
        return None
    match = re.fullmatch(r"/articles/([A-Za-z0-9_-]+)", parsed.path)
    return match.group(1) if match is not None else None


def _text_without_data_options(root: HtmlNode) -> str:
    parts: list[str] = []
    for item in root.content:
        if isinstance(item, HtmlNode):
            if "data-option" in item.attrs:
                continue
            value = _text_without_data_options(item)
        else:
            value = clean_text(item)
        if value:
            parts.append(value)
    return clean_text(" ".join(parts))


def _collect_values(
    fields: list[DataField], labels: list[LabeledValue]
) -> tuple[dict[str, str], dict[str, str]]:
    values: dict[str, str] = {}
    original_names: dict[str, str] = {}
    for item in fields:
        key = _canonical_field(item.name)
        if key not in values or (not values[key] and item.value):
            values[key] = item.value
            original_names[key] = item.name

    for item in labels:
        key = _LABEL_FIELDS.get(_canonical_label(item.label))
        if key is not None and (key not in values or not values[key]):
            values[key] = item.value
            original_names[key] = item.field_name or item.label
    return values, original_names


def _extra_fields(
    fields: list[DataField],
    labels: list[LabeledValue],
    values: dict[str, str],
) -> dict[str, str]:
    extras: dict[str, str] = {}
    consumed_nodes = {
        id(item.field_node) for item in labels if item.field_node is not None
    }
    for item in labels:
        label_key = _LABEL_FIELDS.get(_canonical_label(item.label))
        if label_key is None:
            extras[item.field_name or item.label] = item.value

    for item in fields:
        if id(item.node) in consumed_nodes:
            continue
        canonical = _canonical_field(item.name)
        if canonical not in _FIELD_ALIASES.values():
            extras[item.name] = item.value

    typed_parsers = {
        "advertised_price": parse_money,
        "price_per_3_3m2": parse_money,
        "management_fee": parse_money,
        "supply_area_m2": parse_decimal,
        "exclusive_area_m2": parse_decimal,
        "exclusive_rate": parse_integer,
        "room_count": parse_integer,
        "bathroom_count": parse_integer,
        "verified_at": parse_date,
        "first_published_at": parse_date,
    }
    for key, parser in typed_parsers.items():
        raw = values.get(key)
        if raw and parser(raw) is None:
            extras.setdefault(key, raw)
    return extras


def parse_broker_article(
    html: str,
    *,
    article_url: str | None = None,
    provider: str | None = None,
    is_npay: bool | None = None,
    captured_at: datetime | None = None,
) -> BrokerArticleDetail:
    document = parse_html(html)
    article_root = first_node_with_attribute(document, "data-article-id") or document
    fields = data_fields(article_root)
    labels = [*labeled_values(article_root), *_live_labeled_values(article_root)]
    values, _ = _collect_values(fields, labels)

    article_id = clean_text(
        values.get("article_id", "") or article_root.attrs.get("data-article-id", "")
    )
    if not article_id:
        for node in [article_root, *iter_nodes(article_root)]:
            article_id = _safe_article_id(node.attrs.get("href")) or ""
            if article_id:
                break
    if not article_id:
        article_id = _safe_article_id(article_url) or ""

    if provider is not None:
        parsed_provider = clean_text(provider)
    else:
        parsed_provider = clean_text(
            article_root.attrs.get("data-provider", "")
            or values.get("provider", "")
        )
    provider_was_missing = not parsed_provider
    if provider_was_missing:
        parsed_provider = "미표시"
    if is_npay is not None:
        parsed_is_npay = is_npay
    else:
        is_npay_raw = article_root.attrs.get("data-is-npay")
        if is_npay_raw is None:
            is_npay_raw = values.get("is_npay")
        parsed_is_npay = parse_boolean(is_npay_raw)

    if not article_id:
        raise ValueError("broker article id is missing")
    if parsed_is_npay is None:
        raise ValueError("broker article Npay flag is missing or invalid")

    advertised_price = parse_money(values.get("advertised_price"))
    description = values.get("description", "")
    warnings: list[str] = []
    if provider_was_missing:
        warnings.append("provider_missing")
    description_prices = money_values(description)
    if (
        advertised_price is not None
        and description_prices
        and description_prices[0] != advertised_price
    ):
        warnings.append("price_mismatch")

    realtor_values = {
        key.removeprefix("realtor."): values.get(key)
        for key in _REALTOR_FIELDS
        if values.get(key)
    }
    realtor = RealtorProfile(**realtor_values) if realtor_values else None

    room_count = parse_integer(values.get("room_count"))
    bathroom_count = parse_integer(values.get("bathroom_count"))
    room_bath = values.get("room_bath_count", "")
    room_bath_match = re.search(r"(\d+)\s*/\s*(\d+)", room_bath)
    if room_bath_match is not None:
        room_count = int(room_bath_match.group(1))
        bathroom_count = int(room_bath_match.group(2))

    floor = values.get("floor") or None
    if floor is None and (
        values.get("current_floor") or values.get("total_floor")
    ):
        current = re.sub(r"\s*층\s*$", "", values.get("current_floor", ""))
        total = re.sub(r"\s*층\s*$", "", values.get("total_floor", ""))
        floor = f"{current}/{total}층"

    from ..live_dom import extract_option_mentions

    options = option_values(article_root)
    canonical_options = {
        mention
        for option in options
        for mention in extract_option_mentions(option)
    }
    for option in extract_option_mentions(_text_without_data_options(article_root)):
        if option not in canonical_options and option not in options:
            options.append(option)
            canonical_options.add(option)

    model_values: dict[str, object] = {
        "article_id": article_id,
        "article_url": article_url,
        "provider": parsed_provider,
        "is_npay": parsed_is_npay,
        "advertised_price": advertised_price,
        "price_per_3_3m2": parse_money(values.get("price_per_3_3m2")),
        "management_fee": parse_money(values.get("management_fee")),
        "loan_description": values.get("loan_description") or None,
        "supply_area_m2": parse_decimal(values.get("supply_area_m2")),
        "exclusive_area_m2": parse_decimal(values.get("exclusive_area_m2")),
        "exclusive_rate": parse_integer(values.get("exclusive_rate")),
        "floor": floor,
        "room_count": room_count,
        "bathroom_count": bathroom_count,
        "direction": values.get("direction") or None,
        "structure": values.get("structure") or None,
        "move_in_date": values.get("move_in_date") or None,
        "description": description,
        "option_tags": options,
        "verified_at": parse_date(values.get("verified_at")),
        "first_published_at": parse_date(values.get("first_published_at")),
        "realtor": realtor,
        "extra_fields": _extra_fields(fields, labels, values),
        "warnings": warnings,
    }
    if captured_at is not None:
        model_values["captured_at"] = captured_at
    return BrokerArticleDetail(**model_values)
