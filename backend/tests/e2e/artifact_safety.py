from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any


SAFE_CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:(?:\+?82)[ -]?)?"
    r"(?:0?1[016789]|0[2-9]\d?)[ -]?\d{3,4}[ -]?\d{4}(?!\d)"
)
SECRET_PATTERN = re.compile(
    r"(?:set-cookie|cookie\s*:|session(?:id|token)?\s*[:=]|"
    r"authorization\s*:|bearer\s+[a-z0-9._~-]+|"
    r"\b(?:nid_aut|nid_ses|nid_jkl|nnb)\s*=)",
    re.IGNORECASE,
)
HTML_PATTERN = re.compile(
    r"<!doctype|</?[a-z][a-z0-9-]*(?:\s[^<>]*)?>",
    re.IGNORECASE,
)
BROKER_IDENTITY_KEY_PATTERN = re.compile(
    r"(?:"
    r"^realtor(?:$|[_.-]?(?:name|office|address|registration|license|phone|contact))|"
    r"^broker[_.-]?(?:name|office|address|registration|license|phone|contact)|"
    r"registration[_.-]?number|"
    r"(?:공인)?중개사\s*(?:명|이름|상호|주소|등록|전화|연락)"
    r")",
    re.IGNORECASE,
)
MAX_ARTIFACT_TEXT_LENGTH = 500


def artifact_safe(value: Any) -> Any:
    if isinstance(value, str):
        if (
            len(value) > MAX_ARTIFACT_TEXT_LENGTH
            or HTML_PATTERN.search(value)
            or SECRET_PATTERN.search(value)
        ):
            return "[redacted]"
        value = URL_PATTERN.sub("[redacted-url]", value)
        return PHONE_PATTERN.sub("[redacted-phone]", value)
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = str(artifact_safe(key))
            safe[safe_key] = (
                "[redacted]"
                if BROKER_IDENTITY_KEY_PATTERN.search(str(key))
                else artifact_safe(item)
            )
        return safe
    if isinstance(value, (list, tuple, set, frozenset)):
        return [artifact_safe(item) for item in value]
    return value


def write_artifact_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(
            artifact_safe(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def safe_case_artifact_path(root: Path, case_id: str, filename: str) -> Path:
    if SAFE_CASE_ID_PATTERN.fullmatch(case_id) is None:
        raise ValueError("case_id_invalid")
    resolved_root = root.resolve()
    resolved_path = (resolved_root / case_id / filename).resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError("artifact_path_outside_root") from exc
    return resolved_path
