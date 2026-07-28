from __future__ import annotations

from datetime import time
from typing import Literal
from uuid import UUID

from pydantic import AliasChoices, Field, model_validator

from app.crawler.delay import (
    DEFAULT_INTERACTION_DELAY_PRESET,
    InteractionDelayPreset,
)
from app.schemas.analysis import ApiSchema, RunStage, RunStatus

Cadence = Literal["daily", "weekdays", "weekly"]


class ScheduleCreate(ApiSchema):
    source_id: UUID | None = None
    source_url: str | None = None
    cadence: Cadence
    time_of_day: time = Field(
        validation_alias=AliasChoices("timeOfDay", "time_of_day", "time")
    )
    timezone: Literal["Asia/Seoul"] = "Asia/Seoul"
    weekday: int | None = Field(default=None, ge=0, le=6)
    enabled: bool = True
    collect_broker_details: bool = True
    interaction_delay_preset: InteractionDelayPreset = (
        DEFAULT_INTERACTION_DELAY_PRESET
    )

    @model_validator(mode="after")
    def validate_source_and_weekday(self) -> "ScheduleCreate":
        if self.source_id is None and not self.source_url:
            raise ValueError("sourceId 또는 sourceUrl이 필요합니다.")
        if self.cadence == "weekly" and self.weekday is None:
            raise ValueError("weekly 스케줄에는 weekday가 필요합니다.")
        return self


class SchedulePatch(ApiSchema):
    cadence: Cadence | None = None
    time_of_day: time | None = Field(
        default=None,
        validation_alias=AliasChoices("timeOfDay", "time_of_day", "time"),
    )
    timezone: Literal["Asia/Seoul"] | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)
    enabled: bool | None = None
    collect_broker_details: bool | None = None
    interaction_delay_preset: InteractionDelayPreset | None = None


class ScheduleResponse(ApiSchema):
    id: UUID
    source_id: UUID
    source_url: str
    cadence: Cadence
    time_of_day: time
    timezone: str
    weekday: int | None = None
    enabled: bool
    collect_broker_details: bool
    interaction_delay_preset: InteractionDelayPreset
    next_run_at: str


class ScheduleRun(ApiSchema):
    run_id: UUID
    status: RunStatus
    stage: RunStage
    progress: int
    error_code: str | None = None
    collect_broker_details: bool
    interaction_delay_preset: InteractionDelayPreset
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None


class ScheduleRuns(ApiSchema):
    schedule_id: UUID
    items: list[ScheduleRun]


class ScheduleDelete(ApiSchema):
    id: UUID
    action: Literal["disabled", "deleted"]
