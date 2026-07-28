from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import re
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlsplit

from .parsers._html import (
    HtmlNode,
    clean_text,
    first_node_with_attribute,
    iter_nodes,
    parse_html,
    parse_money,
)
from .types import ListingDetail


@dataclass(frozen=True, slots=True)
class ComplexPanelObservation:
    complex_id: str
    name: str
    trade_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "trade_counts", MappingProxyType(dict(self.trade_counts))
        )


@dataclass(frozen=True, slots=True)
class BrokerCardObservation:
    article_href: str
    provider: str
    description: str
    is_npay: bool = False


def _nodes_including(root: HtmlNode) -> list[HtmlNode]:
    return [root, *iter_nodes(root)]


def _path_identifier(href: str, collection: str) -> str | None:
    path = urlsplit(href).path
    match = re.fullmatch(rf"/{collection}/([A-Za-z0-9_-]+)", path)
    return match.group(1) if match is not None else None


def _direct_children(node: HtmlNode) -> list[HtmlNode]:
    return [item for item in node.content if isinstance(item, HtmlNode)]


def _visible_pairs(root: HtmlNode) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for parent in _nodes_including(root):
        children = _direct_children(parent)
        if len(children) != 2:
            continue
        label_node, value_node = children
        if label_node.tag not in {"div", "span", "strong", "p"}:
            continue
        label = clean_text(label_node.text())
        value = clean_text(value_node.text())
        pair = (label, value)
        if label and value and pair not in seen:
            pairs.append(pair)
            seen.add(pair)
    return pairs


def _provider_immediately_before_link(
    root: HtmlNode,
    selected_link: HtmlNode,
) -> str:
    nodes = _nodes_including(root)
    selected_index = next(
        (
            index
            for index, node in enumerate(nodes)
            if node is selected_link
        ),
        None,
    )
    if selected_index is None:
        return ""

    for node in reversed(nodes[:selected_index]):
        if _direct_children(node):
            continue
        text = clean_text(node.text())
        if not text:
            continue
        match = re.fullmatch(r"(?P<provider>.+?)\s+제공", text)
        return clean_text(match.group("provider")) if match is not None else ""
    return ""


def _provider_from_broker_info(root: HtmlNode) -> str:
    for broker_info in _nodes_including(root):
        if (
            broker_info.attrs.get("data-sentry-component")
            != "ArticleBrokerInfo"
        ):
            continue
        values = []
        for node in _nodes_including(broker_info):
            if _direct_children(node):
                continue
            text = clean_text(node.text())
            if text:
                values.append(text)
        if values:
            return values[-1]
    return ""


def parse_complex_panel(html: str, title: str) -> ComplexPanelObservation:
    document = parse_html(html)
    candidates: list[tuple[HtmlNode, str]] = []
    for node in _nodes_including(document):
        href = node.attrs.get("href", "")
        identifier = _path_identifier(href, "complexes") if node.tag == "a" else None
        if identifier is not None:
            candidates.append((node, identifier))
    if not candidates:
        raise ValueError("complex link is missing")

    normalized_title = clean_text(title)
    exact_matches = [
        candidate
        for candidate in candidates
        if clean_text(candidate[0].text()) == normalized_title
    ]
    exact_complex_ids = {complex_id for _, complex_id in exact_matches}
    candidate_complex_ids = {complex_id for _, complex_id in candidates}
    use_title_as_name = False
    if exact_matches and len(exact_complex_ids) == 1:
        complex_link, complex_id = exact_matches[0]
    elif not exact_matches and len(candidate_complex_ids) == 1:
        complex_link, complex_id = candidates[0]
        use_title_as_name = len(candidates) > 1
    else:
        raise ValueError("complex link is ambiguous")

    trade_counts: dict[str, int] = {}
    for node in _nodes_including(document):
        if (
            node.tag != "button"
            or node.attrs.get("data-sentry-component") != "ButtonBoxLink"
        ):
            continue
        match = re.fullmatch(
            r"\s*(매매|전세|월세)\s*([0-9][0-9,]*)\s*", node.text()
        )
        if match is not None:
            trade_counts[match.group(1)] = int(match.group(2).replace(",", ""))
    if not trade_counts:
        raise ValueError("complex trade counts are missing")

    name = (
        normalized_title
        if use_title_as_name
        else clean_text(complex_link.text()) or normalized_title
    )
    return ComplexPanelObservation(
        complex_id=complex_id,
        name=name,
        trade_counts=trade_counts,
    )


_NUMBER = r"\d[\d,]*(?:\.\d+)?"
_MONEY = (
    rf"(?:{_NUMBER}\s*억"
    rf"(?:\s*{_NUMBER}\s*(?:천\s*만|만)?\s*원?)?"
    rf"|{_NUMBER}\s*(?:천\s*만|만)\s*원"
    rf"|{_NUMBER}\s*원)"
)
_SHORT_MONEY = rf"(?:{_MONEY}|{_NUMBER})"
_DISPLAYED_PRICE_LINE = re.compile(
    rf"(?:"
    rf"월세\s*{_SHORT_MONEY}\s*/\s*{_SHORT_MONEY}"
    rf"(?:\s*~\s*{_SHORT_MONEY}\s*/\s*{_SHORT_MONEY})?"
    rf"|"
    rf"(?:매매|전세)\s*{_MONEY}"
    rf"(?:\s*~\s*{_MONEY})?"
    rf")"
)


def _displayed_price_text(root: HtmlNode, fallback: str) -> str:
    for node in _nodes_including(root):
        if _direct_children(node):
            continue
        candidate = clean_text(node.text())
        if _DISPLAYED_PRICE_LINE.fullmatch(candidate):
            return candidate
    return fallback


def _displayed_rent_money(value: str) -> int | None:
    parsed = parse_money(value)
    if parsed is None:
        return None
    if re.fullmatch(_NUMBER, re.sub(r"\s+", "", value)):
        return parsed * 10_000
    return parsed


def _decimal_match(match: re.Match[str] | None, group: str) -> Decimal | None:
    if match is None:
        return None
    return Decimal(match.group(group).replace(",", ""))


def parse_live_displayed_broker_count(html: str) -> int | None:
    document = parse_html(html)
    group_root = first_node_with_attribute(document, "data-group-id") or document
    text = clean_text(group_root.text())
    broker_match = re.search(
        r"중개사\s*(?P<count>\d[\d,]*)\s*곳에서\s*등록했어요",
        text,
    )
    if broker_match is not None:
        return int(broker_match.group("count").replace(",", ""))

    article_hrefs = {
        node.attrs["href"]
        for node in _nodes_including(group_root)
        if node.tag == "a"
        and "href" in node.attrs
        and _path_identifier(node.attrs["href"], "articles") is not None
    }
    return 1 if len(article_hrefs) == 1 else None


def parse_live_listing_group(
    html: str, captured_at: datetime
) -> ListingDetail:
    document = parse_html(html)
    group_root = first_node_with_attribute(document, "data-group-id") or document
    text = clean_text(group_root.text())
    displayed_price_text = _displayed_price_text(group_root, text)

    trade_type = ""
    price: int | None = None
    deposit: int | None = None
    monthly_rent: int | None = None

    displayed_price = re.search(
        rf"(?:"
        rf"(?P<monthly_type>월세)\s*"
        rf"(?P<deposit>{_SHORT_MONEY})\s*/\s*"
        rf"(?P<rent>{_SHORT_MONEY})"
        rf"|"
        rf"(?P<fixed_type>매매|전세)\s*"
        rf"(?P<amount>{_MONEY})"
        rf")",
        displayed_price_text,
    )
    if displayed_price is not None and displayed_price.group(
        "monthly_type"
    ):
        trade_type = "월세"
        deposit = _displayed_rent_money(
            displayed_price.group("deposit")
        )
        monthly_rent = _displayed_rent_money(
            displayed_price.group("rent")
        )
    elif displayed_price is not None:
        trade_type = displayed_price.group("fixed_type")
        amount = parse_money(displayed_price.group("amount"))
        if trade_type == "매매":
            price = amount
        else:
            deposit = amount
    if not trade_type:
        raise ValueError("listing trade type is missing")

    building_match = re.search(r"(?<!\d)(?P<building>\d+[가-힣A-Za-z-]*동)\b", text)
    area_match = re.search(
        rf"(?P<supply>{_NUMBER})\s*[A-Za-z]*\s*㎡\s*"
        rf"\(\s*전용\s*(?P<exclusive>{_NUMBER})\s*[A-Za-z]*\s*(?:㎡)?\s*\)",
        text,
    )
    floor_match = re.search(
        r"(?P<current>\d+|저|중|고)\s*/\s*(?P<total>\d+)\s*층", text
    )
    direction_match = re.search(r"(?:남동|남서|북동|북서|남|북|동|서)향", text)

    source_group_id = clean_text(group_root.attrs.get("data-group-id", "")) or None
    return ListingDetail(
        source_group_id=source_group_id,
        trade_type=trade_type,
        price=price,
        deposit=deposit,
        monthly_rent=monthly_rent,
        building=building_match.group("building") if building_match else None,
        supply_area=_decimal_match(area_match, "supply"),
        exclusive_area=_decimal_match(area_match, "exclusive"),
        floor=(
            f"{floor_match.group('current')}/{floor_match.group('total')}층"
            if floor_match
            else None
        ),
        direction=direction_match.group(0) if direction_match else None,
        displayed_broker_count=parse_live_displayed_broker_count(html),
        captured_at=captured_at,
    )


def parse_live_broker_card(html: str) -> BrokerCardObservation:
    document = parse_html(html)
    article_links = [
        node
        for node in _nodes_including(document)
        if node.tag == "a"
        and _path_identifier(node.attrs.get("href", ""), "articles") is not None
    ]
    selected = next(
        (
            node
            for node in article_links
            if "Npay 부동산에서 보기" in clean_text(node.text())
        ),
        None,
    )
    is_npay = selected is not None
    if selected is None:
        selected = next(
            (
                node
                for node in article_links
                if "매물 보러가기" in clean_text(node.text())
            ),
            None,
        )
    if selected is None:
        raise ValueError("internal broker article link is missing")

    leaf_texts = []
    for node in iter_nodes(document):
        if _direct_children(node):
            continue
        text = clean_text(node.text())
        if text:
            leaf_texts.append(text)
    description = ""
    for text in leaf_texts:
        for opening, closing in (
            ('"', '"'),
            ("'", "'"),
            ("“", "”"),
            ("‘", "’"),
        ):
            if len(text) >= 2 and text.startswith(opening) and text.endswith(closing):
                description = clean_text(text[len(opening) : -len(closing)])
                break
        if description:
            break

    provider = ""
    interest_index = next(
        (
            index
            for index, text in enumerate(leaf_texts)
            if text == "관심매물"
        ),
        None,
    )
    if interest_index is not None:
        confirmation_indexes = [
            index
            for index, text in enumerate(leaf_texts[:interest_index])
            if text.startswith("확인매물")
        ]
        if confirmation_indexes:
            values_before_interest = leaf_texts[
                confirmation_indexes[-1] + 1 : interest_index
            ]
            if len(values_before_interest) >= 2:
                provider = values_before_interest[-1]
    else:
        values = {
            re.sub(r"\s+", "", label): value
            for label, value in _visible_pairs(document)
        }
        provider = values.get("제공처", "")
        if not description:
            description = values.get("매물소개", values.get("매물설명", ""))
    if not provider:
        provider = _provider_from_broker_info(document)
    if not provider:
        provider = _provider_immediately_before_link(document, selected)
    provider = re.sub(r"\s+제공$", "", clean_text(provider))

    return BrokerCardObservation(
        article_href=selected.attrs["href"],
        provider=provider,
        description=description,
        is_npay=is_npay,
    )


_OPTION_PATTERNS = (
    (re.compile(r"시스템\s*에어컨|시에(?=\s*\d|[\s.,]|$)"), "시스템에어컨"),
    (re.compile(r"중문"), "중문"),
    (re.compile(r"식기세척기|식세기"), "식기세척기"),
)


def extract_option_mentions(text: str) -> list[str]:
    mentions: list[tuple[int, str]] = []
    for pattern, canonical in _OPTION_PATTERNS:
        mentions.extend((match.start(), canonical) for match in pattern.finditer(text))
    mentions.sort(key=lambda item: item[0])

    result: list[str] = []
    for _, canonical in mentions:
        if canonical not in result:
            result.append(canonical)
    return result
