from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import re
from typing import Iterator


_VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


def clean_text(value: str) -> str:
    return " ".join(value.split())


@dataclass(slots=True)
class HtmlNode:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    content: list[str | HtmlNode] = field(default_factory=list)

    def text(self) -> str:
        parts: list[str] = []
        for item in self.content:
            if isinstance(item, HtmlNode):
                value = item.text()
            else:
                value = clean_text(item)
            if value:
                parts.append(value)
        return clean_text(" ".join(parts))


class _TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = HtmlNode("[document]")
        self._stack = [self.root]

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        node = HtmlNode(
            tag.lower(),
            {name.lower(): value or "" for name, value in attrs},
        )
        self._stack[-1].content.append(node)
        if node.tag not in _VOID_ELEMENTS:
            self._stack.append(node)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        node = HtmlNode(
            tag.lower(),
            {name.lower(): value or "" for name, value in attrs},
        )
        self._stack[-1].content.append(node)

    def handle_endtag(self, tag: str) -> None:
        wanted = tag.lower()
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == wanted:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].content.append(data)


def parse_html(html: str) -> HtmlNode:
    parser = _TreeParser()
    parser.feed(html)
    parser.close()
    return parser.root


def iter_nodes(
    root: HtmlNode, *, skip_descendants_with_attribute: str | None = None
) -> Iterator[HtmlNode]:
    for item in root.content:
        if not isinstance(item, HtmlNode):
            continue
        if (
            skip_descendants_with_attribute is not None
            and skip_descendants_with_attribute in item.attrs
        ):
            continue
        yield item
        yield from iter_nodes(
            item,
            skip_descendants_with_attribute=skip_descendants_with_attribute,
        )


def first_node_with_attribute(root: HtmlNode, attribute: str) -> HtmlNode | None:
    attribute = attribute.lower()
    if attribute in root.attrs:
        return root
    return next(
        (node for node in iter_nodes(root) if attribute in node.attrs),
        None,
    )


@dataclass(frozen=True, slots=True)
class DataField:
    name: str
    value: str
    node: HtmlNode


@dataclass(frozen=True, slots=True)
class LabeledValue:
    label: str
    value: str
    field_name: str | None
    field_node: HtmlNode | None


def data_fields(
    root: HtmlNode, *, skip_descendants_with_attribute: str | None = None
) -> list[DataField]:
    result: list[DataField] = []
    candidates: Iterator[HtmlNode]
    candidates = iter_nodes(
        root,
        skip_descendants_with_attribute=skip_descendants_with_attribute,
    )
    if "data-field" in root.attrs:
        result.append(DataField(root.attrs["data-field"], root.text(), root))
    for node in candidates:
        name = node.attrs.get("data-field")
        if name is not None:
            result.append(DataField(name, node.text(), node))
    return result


def _first_data_field_node(root: HtmlNode) -> HtmlNode | None:
    if "data-field" in root.attrs:
        return root
    return next(
        (node for node in iter_nodes(root) if "data-field" in node.attrs),
        None,
    )


def labeled_values(
    root: HtmlNode, *, skip_descendants_with_attribute: str | None = None
) -> list[LabeledValue]:
    result: list[LabeledValue] = []
    pending_label: str | None = None
    for node in iter_nodes(
        root,
        skip_descendants_with_attribute=skip_descendants_with_attribute,
    ):
        if node.tag == "dt":
            pending_label = node.text()
        elif node.tag == "dd" and pending_label is not None:
            field_node = _first_data_field_node(node)
            result.append(
                LabeledValue(
                    label=pending_label,
                    value=node.text(),
                    field_name=(
                        field_node.attrs["data-field"] if field_node is not None else None
                    ),
                    field_node=field_node,
                )
            )
            pending_label = None
    return result


def option_values(root: HtmlNode) -> list[str]:
    result: list[str] = []
    if "data-option" in root.attrs:
        result.append(root.attrs["data-option"] or root.text())
    for node in iter_nodes(root):
        if "data-option" in node.attrs:
            result.append(node.attrs["data-option"] or node.text())
    return result


_NUMBER = re.compile(r"[+-]?\d[\d,]*(?:\.\d+)?")


def parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    match = _NUMBER.search(value)
    if match is None:
        return None
    try:
        return Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return None


def parse_integer(value: str | None) -> int | None:
    number = parse_decimal(value)
    if number is None or number != number.to_integral_value():
        return None
    return int(number)


def _number_decimal(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


def parse_money(value: str | None) -> int | None:
    if value is None:
        return None
    compact = re.sub(r"\s+", "", value).replace(",", "")
    number = r"[+-]?\d+(?:\.\d+)?"

    eok = re.search(rf"(?P<value>{number})억", compact)
    if eok is not None:
        total = _number_decimal(eok.group("value")) * Decimal(100_000_000)
        remainder = compact[eok.end() :]
        cheon_man = re.match(rf"(?P<value>{number})천만(?:원)?", remainder)
        man_won = re.match(
            rf"(?P<man>{number})만(?P<won>\d+)원",
            remainder,
        )
        man = re.match(rf"(?P<value>{number})만(?:원)?", remainder)
        bare = re.match(rf"(?P<value>{number})(?P<unit>원)?", remainder)
        if cheon_man is not None:
            total += _number_decimal(cheon_man.group("value")) * Decimal(10_000_000)
        elif man_won is not None:
            total += (
                _number_decimal(man_won.group("man")) * Decimal(10_000)
                + _number_decimal(man_won.group("won"))
            )
        elif man is not None:
            total += _number_decimal(man.group("value")) * Decimal(10_000)
        elif bare is not None and bare.group("value"):
            multiplier = Decimal(1) if bare.group("unit") else Decimal(10_000)
            total += _number_decimal(bare.group("value")) * multiplier
        return int(total)

    cheon_man = re.search(rf"(?P<value>{number})천만(?:원)?", compact)
    if cheon_man is not None:
        return int(_number_decimal(cheon_man.group("value")) * Decimal(10_000_000))

    man_won = re.search(
        rf"(?P<man>{number})만(?P<won>\d+)원",
        compact,
    )
    if man_won is not None:
        return int(
            _number_decimal(man_won.group("man")) * Decimal(10_000)
            + _number_decimal(man_won.group("won"))
        )

    man = re.search(rf"(?P<value>{number})만(?:원)?", compact)
    if man is not None:
        return int(_number_decimal(man.group("value")) * Decimal(10_000))

    won = re.search(rf"(?P<value>{number})원", compact)
    if won is not None:
        return int(_number_decimal(won.group("value")))

    plain = re.fullmatch(number, compact)
    if plain is not None:
        return int(_number_decimal(plain.group(0)))
    return None


_MONEY_TOKEN = re.compile(
    r"[+-]?\d[\d,]*(?:\.\d+)?\s*억"
    r"(?:\s*[+-]?\d[\d,]*(?:\.\d+)?\s*(?:천\s*만|만)?\s*원?)?"
    r"|[+-]?\d[\d,]*(?:\.\d+)?\s*천\s*만\s*원?"
    r"|[+-]?\d[\d,]*(?:\.\d+)?\s*만\s*원"
    r"|[+-]?\d[\d,]*(?:\.\d+)?\s*원"
)


def money_values(value: str) -> list[int]:
    result: list[int] = []
    for match in _MONEY_TOKEN.finditer(value):
        parsed = parse_money(match.group(0))
        if parsed is not None:
            result.append(parsed)
    return result


def parse_boolean(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = clean_text(value).casefold()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    return None


_DATE = re.compile(
    r"^\s*(?P<year>\d{4})\s*[./-]\s*(?P<month>\d{1,2})\s*[./-]\s*"
    r"(?P<day>\d{1,2})\s*\.?\s*$"
)


def parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    match = _DATE.fullmatch(value)
    if match is None:
        return None
    try:
        return date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
    except ValueError:
        return None
