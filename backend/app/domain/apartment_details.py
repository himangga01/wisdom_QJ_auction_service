from __future__ import annotations

from collections.abc import Mapping, Sequence
import re


CANONICAL_APARTMENT_DETAIL_KEYS = (
    "household_count",
    "building_count",
    "approval_date",
    "parking_count",
    "parking_per_household",
    "heating",
    "entrance_type",
    "floor_area_ratio",
    "building_coverage_ratio",
    "management_office_phone",
    "builders",
)


# The crawler can expose either a displayed Korean label or the page's
# data-field name. Keep aliases in priority order for deterministic handling
# when one detail panel happens to expose both forms.
APARTMENT_DETAIL_ALIASES: dict[str, tuple[str, ...]] = {
    "household_count": ("세대수", "총세대수", "household_count", "householdCount"),
    "building_count": ("동수", "총동수", "building_count", "buildingCount"),
    "approval_date": ("사용승인일", "승인일", "approval_date", "approvalDate"),
    "parking_count": ("주차대수", "주차", "parking_count", "parking"),
    "parking_per_household": (
        "세대당주차대수",
        "세대당 주차대수",
        "세대당주차",
        "세대당 주차",
        "주차대수(세대당)",
        "parking_per_household",
        "parkingPerHousehold",
    ),
    "heating": ("난방방식", "난방", "heating"),
    "entrance_type": ("현관구조", "현관", "entrance_type", "entrance"),
    "floor_area_ratio": ("용적률", "floor_area_ratio", "floorAreaRatio"),
    "building_coverage_ratio": (
        "건폐율",
        "building_coverage_ratio",
        "buildingCoverageRatio",
    ),
    "management_office_phone": (
        "관리사무소전화번호",
        "관리사무소 전화번호",
        "관리사무소",
        "management_office_phone",
        "management_office",
        "managementOfficePhone",
    ),
    "builders": ("건설사", "시공사", "건설회사", "builders", "builder"),
}


def _alias_token(value: str) -> str:
    return re.sub(r"[\s_.-]+", "", value).casefold()


_ALIASES_TO_CANONICAL: dict[str, tuple[str, int]] = {}
for canonical_key, aliases in APARTMENT_DETAIL_ALIASES.items():
    for priority, alias in enumerate((canonical_key, *aliases)):
        _ALIASES_TO_CANONICAL.setdefault(
            _alias_token(alias),
            (canonical_key, priority),
        )


_INTEGER_KEYS = frozenset({"household_count", "building_count", "parking_count"})
_DECIMAL_KEYS = frozenset(
    {"parking_per_household", "floor_area_ratio", "building_coverage_ratio"}
)


def _nonempty(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or None
    text = str(value).strip()
    return text or None


def _first_number(value: str) -> float | None:
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", value)
    if match is None:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _normalize_value(canonical_key: str, raw_value: object) -> object | None:
    value = _nonempty(raw_value)
    if value is None:
        return None
    if canonical_key == "builders":
        if isinstance(value, list):
            candidates = value
        else:
            candidates = re.split(r"\s*[,/·]\s*", str(value))
        builders: list[str] = []
        for candidate in candidates:
            normalized = " ".join(str(candidate).split())
            if normalized and normalized not in builders:
                builders.append(normalized)
        return sorted(builders) or None
    if canonical_key in _INTEGER_KEYS:
        number = (
            float(value)
            if isinstance(value, (int, float))
            else _first_number(str(value))
        )
        return int(number) if number is not None else None
    if canonical_key in _DECIMAL_KEYS:
        number = (
            float(value)
            if isinstance(value, (int, float))
            else _first_number(str(value))
        )
        if number is None:
            return None
        return int(number) if number.is_integer() else number
    return " ".join(str(value).split())


def _comparison_key(value: object) -> str:
    if isinstance(value, list):
        return "\x1f".join(str(item) for item in value)
    return str(value)


def _append_warning_once(warnings: list[str], warning: str) -> None:
    if warning not in warnings:
        warnings.append(warning)


def normalize_apartment_details(
    values: Mapping[str, object],
) -> tuple[dict[str, object], list[str]]:
    """Map one detail panel's labels/data fields to canonical apartment keys."""
    candidates: dict[str, list[tuple[int, str, object]]] = {}
    for raw_key, raw_value in values.items():
        alias = _ALIASES_TO_CANONICAL.get(_alias_token(str(raw_key)))
        if alias is None:
            continue
        canonical_key, priority = alias
        raw_text = str(raw_value)
        value = _normalize_value(canonical_key, raw_value)
        if canonical_key == "parking_count" and "세대당" in raw_text:
            per_household_match = re.search(
                r"세대당\s*(\d[\d,]*(?:\.\d+)?)",
                raw_text,
            )
            if per_household_match:
                per_household = _normalize_value(
                    "parking_per_household",
                    per_household_match.group(1),
                )
                if per_household is not None:
                    candidates.setdefault("parking_per_household", []).append(
                        (priority, _alias_token(str(raw_key)), per_household)
                    )
            if _first_number(raw_text.split("세대당", 1)[0]) is None:
                value = None
        if value is None:
            continue
        candidates.setdefault(canonical_key, []).append(
            (priority, _alias_token(str(raw_key)), value)
        )

    normalized: dict[str, object] = {}
    warnings: list[str] = []
    for canonical_key in CANONICAL_APARTMENT_DETAIL_KEYS:
        values_for_key = candidates.get(canonical_key, [])
        if not values_for_key:
            continue
        values_for_key.sort(key=lambda item: (item[0], item[1]))
        normalized[canonical_key] = values_for_key[0][2]
        if len({_comparison_key(value) for _, _, value in values_for_key}) > 1:
            _append_warning_once(warnings, f"apartment_detail_conflict:{canonical_key}")
    return normalized, warnings


def merge_apartment_details(
    observations: Sequence[tuple[str, Mapping[str, object]]],
) -> tuple[dict[str, object], list[str]]:
    """Merge broker observations by article ID, retaining the first non-empty value."""
    normalized_observations: list[tuple[str, int, dict[str, object]]] = []
    warnings: list[str] = []
    for index, (article_id, values) in enumerate(observations):
        normalized, observation_warnings = normalize_apartment_details(values)
        normalized_observations.append((str(article_id), index, normalized))
        for warning in observation_warnings:
            _append_warning_once(warnings, warning)

    normalized_observations.sort(key=lambda item: (item[0], item[1]))
    merged: dict[str, object] = {}
    for canonical_key in CANONICAL_APARTMENT_DETAIL_KEYS:
        nonempty_values: list[object] = []
        for _, _, observation in normalized_observations:
            value = observation.get(canonical_key)
            if _nonempty(value) is not None:
                nonempty_values.append(value)
        if not nonempty_values:
            continue
        merged[canonical_key] = nonempty_values[0]
        if len({_comparison_key(value) for value in nonempty_values}) > 1:
            _append_warning_once(warnings, f"apartment_detail_conflict:{canonical_key}")
    return merged, warnings
