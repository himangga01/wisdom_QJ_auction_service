from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import AliasChoices, AnyHttpUrl, BaseModel, ConfigDict, Field, field_serializer

from app.crawler.delay import (
    DEFAULT_INTERACTION_DELAY_PRESET,
    InteractionDelayPreset,
)

RunStatus = Literal[
    "queued", "running", "completed", "partial", "failed", "blocked", "cancelled"
]
RunStage = Literal["url", "complex", "listings", "brokers", "details", "compare", "save"]


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=to_camel,
    )


class AnalysisCreate(ApiSchema):
    source_url: AnyHttpUrl = Field(
        validation_alias=AliasChoices("source_url", "sourceUrl")
    )
    collect_broker_details: bool = True
    interaction_delay_preset: InteractionDelayPreset = (
        DEFAULT_INTERACTION_DELAY_PRESET
    )


class AnalysisAccepted(ApiSchema):
    run_id: UUID
    source_id: UUID
    status: RunStatus
    collect_broker_details: bool
    interaction_delay_preset: InteractionDelayPreset


class AnalysisStatus(AnalysisAccepted):
    stage: RunStage
    progress: int = Field(ge=0, le=100)
    error_code: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @field_serializer("started_at", "finished_at")
    def serialize_korean_time(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(ZoneInfo("Asia/Seoul")).isoformat()


class AnalysisResult(ApiSchema):
    run_id: UUID
    status: RunStatus
    apartment_id: UUID
    naver_complex_id: str
    name: str
    summary: dict[str, Any]


class AnalysisCancel(ApiSchema):
    run_id: UUID
    status: Literal["cancelled"]
