from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.analysis import ApiSchema


class ApartmentRun(ApiSchema):
    run_id: UUID
    status: str
    collected_at: str


class ApartmentHistoryPoint(ApiSchema):
    run_id: UUID
    status: str
    collected_at: str
    sale_count: int = 0
    jeonse_count: int = 0
    monthly_count: int = 0
    added_count: int = 0
    removed_count: int = 0


class ApartmentSummary(ApiSchema):
    apartment_id: UUID
    complex_id: str
    complex_name: str
    address: str
    source_id: UUID
    source_url: str
    latest_run_id: UUID
    latest_status: str
    collected_at: str
    details: dict[str, Any] = Field(default_factory=dict)
    listing_count: int = 0


class ApartmentDetail(ApartmentSummary):
    available_runs: list[ApartmentRun] = Field(default_factory=list)
    history: list[ApartmentHistoryPoint] = Field(default_factory=list)


class ApartmentPage(ApiSchema):
    items: list[ApartmentSummary]
    page: int
    page_size: int
    total: int
