from __future__ import annotations

import re
import unicodedata


OPTION_ALIASES = {
    "시에": "시스템에어컨",
    "에어컨": "시스템에어컨",
    "시스템 에어컨": "시스템에어컨",
    "시스템에어컨": "시스템에어컨",
    "식세기": "식기세척기",
    "미세 방충망": "미세방충망",
    "전자 계약": "전자계약",
    "주인 거주": "주인거주",
}

_SPACE = re.compile(r"\s+")
_OPTION_COUNT = re.compile(r"(?P<count>\d+)\s*대")


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _SPACE.sub(" ", unicodedata.normalize("NFKC", value)).strip()
    return normalized or None


def normalize_option(value: str) -> tuple[str, int | None]:
    normalized = normalize_text(value) or ""
    match = _OPTION_COUNT.search(normalized)
    count = int(match.group("count")) if match else None
    base = _OPTION_COUNT.sub("", normalized).strip(" ,-·()")
    base = OPTION_ALIASES.get(base, base)
    return base, count


def normalize_move_in(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if normalized is None:
        return None
    aliases = {
        "즉시 입주": "즉시입주",
        "즉시 입주 협의": "즉시입주 협의",
        "협의 가능": "협의",
    }
    return aliases.get(normalized, normalized)


def classify_loan(value: str | None) -> str:
    normalized = normalize_text(value)
    if normalized is None or normalized in {"-", "미표기", "정보없음", "정보 없음"}:
        return "미표기"
    compact = normalized.replace(" ", "")
    if "융자없" in compact or "무융자" in compact or "대출없" in compact:
        return "융자 없음"
    return "정보 표기"


def format_won_in_manwon(value: int) -> str:
    if value % 10_000 == 0:
        amount = value // 10_000
        return f"{amount:,}만원"
    return f"{value:,}원"

