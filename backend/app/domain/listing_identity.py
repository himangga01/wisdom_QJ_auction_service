from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json

from pydantic import BaseModel, Field

from app.domain.normalizer import normalize_text


class ListingIdentityInput(BaseModel):
    complex_id: str
    trade_type: str
    building: str | None = None
    exclusive_area: Decimal | None = None
    floor: str | None = None
    direction: str | None = None
    normalized_price: int | None = None
    article_ids: frozenset[str] = Field(default_factory=frozenset)


class ExistingListingIdentity(BaseModel):
    listing_group_id: str
    identity_key: str
    input: ListingIdentityInput


def _area(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _parts(value: ListingIdentityInput, *, include_price: bool) -> list[object]:
    parts: list[object] = [
        normalize_text(value.complex_id),
        normalize_text(value.trade_type),
        normalize_text(value.building),
        _area(value.exclusive_area),
        normalize_text(value.floor),
        normalize_text(value.direction),
    ]
    if include_price:
        parts.append(value.normalized_price)
    return parts


def _digest(parts: list[object]) -> str:
    encoded = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def build_identity_key(value: ListingIdentityInput) -> str:
    return _digest(
        [
            *_parts(value, include_price=True),
            sorted(value.article_ids),
        ]
    )


def build_auxiliary_key(value: ListingIdentityInput) -> str:
    return _digest(_parts(value, include_price=False))


def choose_existing_listing(
    incoming: ListingIdentityInput,
    candidates: list[ExistingListingIdentity],
) -> ExistingListingIdentity | None:
    overlaps = [
        (len(incoming.article_ids & candidate.input.article_ids), candidate)
        for candidate in candidates
        if incoming.article_ids & candidate.input.article_ids
    ]
    if overlaps:
        return sorted(overlaps, key=lambda item: (-item[0], item[1].identity_key))[0][1]

    identity_key = build_identity_key(incoming)
    exact = [candidate for candidate in candidates if candidate.identity_key == identity_key]
    if exact:
        return sorted(exact, key=lambda item: item.identity_key)[0]

    auxiliary_key = build_auxiliary_key(incoming)
    auxiliary = [
        candidate
        for candidate in candidates
        if build_auxiliary_key(candidate.input) == auxiliary_key
    ]
    return auxiliary[0] if len(auxiliary) == 1 else None
