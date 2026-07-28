from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator


class ReferenceStaleError(RuntimeError):
    code = "reference_stale"


class GptArticleObservation(BaseModel):
    article_id: str
    trade_type: Literal["매매", "전세", "월세"]
    price: int | None
    building: str | None
    floor: str | None
    direction: str | None
    supply_area_m2: Decimal | None
    exclusive_area_m2: Decimal | None
    displayed_broker_count: int
    option_tags: list[str]
    move_in_date: str | None
    required_detail_fields: dict[str, str]


class GptCaseObservation(BaseModel):
    case_id: str
    source_url: str
    complex_id: str
    complex_name: str
    trade_counts: dict[str, int]
    articles: list[GptArticleObservation]


class GptObservationSet(BaseModel):
    schema_version: Literal["1"]
    collector: Literal["gpt_browser_exploration"]
    mode: Literal["sample", "full"]
    captured_at: datetime
    cases: list[GptCaseObservation]

    @field_validator("captured_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        return value.astimezone(timezone.utc)


def load_reference(
    path: Path,
    *,
    now: datetime,
    max_age: timedelta,
) -> GptObservationSet:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    reference = GptObservationSet.model_validate_json(
        path.read_text(encoding="utf-8")
    )
    age = now.astimezone(timezone.utc) - reference.captured_at
    if age > max_age:
        raise ReferenceStaleError(
            "GPT reference is older than the allowed window"
        )
    return reference
