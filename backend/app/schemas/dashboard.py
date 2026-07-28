from __future__ import annotations

from uuid import UUID

from pydantic import Field

from app.schemas.analysis import ApiSchema
from app.schemas.apartment import ApartmentDetail, ApartmentSummary
from app.schemas.listing import ListingSummary


class DashboardResponse(ApiSchema):
    source_id: UUID
    source_url: str
    run_id: UUID
    collected_at: str
    apartment: ApartmentDetail
    listings: list[ListingSummary] = Field(default_factory=list)
    recent_apartments: list[ApartmentSummary] = Field(default_factory=list)

