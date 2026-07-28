from __future__ import annotations

from datetime import datetime
import re

from ..types import ComplexDetail
from ._html import (
    clean_text,
    data_fields,
    first_node_with_attribute,
    labeled_values,
    parse_html,
)


_IDENTITY_FIELDS = {
    "complexid": "complex_id",
    "complex_id": "complex_id",
    "complexname": "name",
    "complex_name": "name",
    "name": "name",
    "address": "address",
    "complexaddress": "address",
    "complex_address": "address",
}


def _identity_field(name: str) -> str | None:
    normalized = re.sub(r"[-\s]", "_", name.strip()).casefold()
    return _IDENTITY_FIELDS.get(normalized, _IDENTITY_FIELDS.get(normalized.replace("_", "")))


def parse_complex(
    html: str, *, captured_at: datetime | None = None
) -> ComplexDetail:
    document = parse_html(html)
    complex_root = first_node_with_attribute(document, "data-complex-id") or document
    fields = data_fields(
        complex_root, skip_descendants_with_attribute="data-group-id"
    )
    field_values: dict[str, str] = {}
    for item in fields:
        identity = _identity_field(item.name)
        if identity is not None and (identity not in field_values or not field_values[identity]):
            field_values[identity] = item.value

    complex_id = clean_text(
        complex_root.attrs.get("data-complex-id", "")
        or field_values.get("complex_id", "")
    )
    name = clean_text(
        complex_root.attrs.get("data-complex-name", "")
        or complex_root.attrs.get("data-name", "")
        or field_values.get("name", "")
    )
    address = clean_text(
        complex_root.attrs.get("data-address", "") or field_values.get("address", "")
    )
    if not complex_id:
        raise ValueError("complex id is missing")
    if not name:
        raise ValueError("complex name is missing")
    if not address:
        raise ValueError("complex address is missing")

    details: dict[str, str] = {}
    consumed_nodes: set[int] = set()
    for item in labeled_values(
        complex_root, skip_descendants_with_attribute="data-group-id"
    ):
        if _identity_field(item.field_name or "") is None:
            details[item.field_name or item.label] = item.value
        if item.field_node is not None:
            consumed_nodes.add(id(item.field_node))
    for item in fields:
        if id(item.node) in consumed_nodes or _identity_field(item.name) is not None:
            continue
        details[item.name] = item.value

    model_values: dict[str, object] = {
        "complex_id": complex_id,
        "name": name,
        "address": address,
        "details": details,
    }
    if captured_at is not None:
        model_values["captured_at"] = captured_at
    return ComplexDetail(**model_values)
