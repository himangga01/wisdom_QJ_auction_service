from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ComparableListing:
    price: int | None
    deposit: int | None
    monthly_rent: int | None
    building: str | None
    floor: str | None
    direction: str | None
    supply_area_m2: float | None
    exclusive_area_m2: float | None
    management_fee: str
    move_in_date: str
    room_bathroom: str
    loan: str
    option_tags: tuple[str, ...]
    registration_count: int
    article_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class ListingChange:
    event_type: Literal["changed"] | None
    changed_fields: tuple[str, ...]
    before: dict[str, object]
    after: dict[str, object]


@dataclass(frozen=True, slots=True)
class StateTransition:
    state: Literal["active", "missing", "removed"]
    missing_count: int
    event_type: Literal["missing", "removed", "restored"] | None


_FIELDS = (
    ("price", "price"),
    ("deposit", "deposit"),
    ("monthly_rent", "monthlyRent"),
    ("building", "building"),
    ("floor", "floor"),
    ("direction", "direction"),
    ("supply_area_m2", "supplyAreaM2"),
    ("exclusive_area_m2", "exclusiveAreaM2"),
    ("management_fee", "managementFee"),
    ("move_in_date", "moveInDate"),
    ("room_bathroom", "roomBathroom"),
    ("loan", "loan"),
    ("option_tags", "optionTags"),
    ("registration_count", "registrationCount"),
    ("article_ids", "articleIds"),
)

_DETAIL_FIELDS = frozenset(
    {
        "management_fee",
        "move_in_date",
        "room_bathroom",
        "loan",
        "option_tags",
    }
)


def _json_value(value: object) -> object:
    if isinstance(value, str):
        normalized = " ".join(value.split())
        return normalized or None
    if isinstance(value, (tuple, frozenset)):
        return sorted(
            {
                normalized
                for item in value
                if (normalized := " ".join(str(item).split()))
            }
        )
    return value


def compare_listings(
    before_listing: ComparableListing,
    after_listing: ComparableListing,
    *,
    compare_detail_fields: bool = True,
) -> ListingChange:
    changed: list[str] = []
    before: dict[str, object] = {}
    after: dict[str, object] = {}
    for attribute, public_name in _FIELDS:
        if not compare_detail_fields and attribute in _DETAIL_FIELDS:
            continue
        old_value = _json_value(getattr(before_listing, attribute))
        new_value = _json_value(getattr(after_listing, attribute))
        if old_value != new_value:
            changed.append(public_name)
            before[public_name] = old_value
            after[public_name] = new_value
    return ListingChange(
        event_type="changed" if changed else None,
        changed_fields=tuple(changed),
        before=before,
        after=after,
    )


def transition_absence(
    *, state: str, missing_count: int, run_status: str
) -> StateTransition:
    if run_status != "completed" or state == "removed":
        return StateTransition(
            state=state if state in {"active", "missing", "removed"} else "active",
            missing_count=missing_count,
            event_type=None,
        )
    next_count = missing_count + 1
    if next_count >= 2:
        return StateTransition("removed", 2, "removed")
    return StateTransition("missing", 1, "missing")


def transition_presence(*, state: str, missing_count: int) -> StateTransition:
    event_type = "restored" if state in {"missing", "removed"} else None
    return StateTransition("active", 0, event_type)
