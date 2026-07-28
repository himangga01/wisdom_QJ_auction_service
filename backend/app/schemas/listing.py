from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from app.schemas.analysis import ApiSchema


class ListingAggregate(ApiSchema):
    option_tags: list[str] = Field(default_factory=list)
    move_in_summary: str = ""
    management_fee_summary: str = ""
    room_bath_summary: str = ""
    loan_summary: str = ""
    source_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class ListingSummary(ApiSchema):
    group_id: UUID
    run_id: UUID
    trade_type: str
    price: int | None = None
    deposit: int | None = None
    monthly_rent: int | None = None
    previous_price: int | None = None
    building: str | None = None
    floor: str | None = None
    direction: str | None = None
    supply_area_m2: float | None = None
    exclusive_area_m2: float | None = None
    status: str
    discovered_at: str
    last_seen_at: str
    captured_at: str
    aggregate: ListingAggregate


class ListingPage(ApiSchema):
    complex_id: str
    run_id: UUID
    collected_at: str
    items: list[ListingSummary]


class MarketDetails(ApiSchema):
    finance: dict[str, Any] = Field(default_factory=dict)
    transactions: dict[str, Any] = Field(default_factory=dict)
    costs: dict[str, Any] = Field(default_factory=dict)
    maintenance: dict[str, Any] = Field(default_factory=dict)
    complex: dict[str, Any] = Field(default_factory=dict)
    location: dict[str, Any] = Field(default_factory=dict)
    extra_fields: dict[str, Any] = Field(default_factory=dict)


class BrokerRegistration(ApiSchema):
    article_id: str
    realtor_name: str = ""
    provider: str
    is_npay: bool
    detail_collected: bool = True
    article_url: str
    advertised_price: int | None = None
    price_per_3_point_3_m2: int | None = None
    management_fee: int | None = None
    loan_description: str | None = None
    supply_area_m2: float | None = None
    exclusive_area_m2: float | None = None
    exclusive_rate: int | None = None
    floor: str | None = None
    room_count: int | None = None
    bathroom_count: int | None = None
    direction: str | None = None
    structure: str | None = None
    move_in_date: str | None = None
    description: str = ""
    option_tags: list[str] = Field(default_factory=list)
    first_published_at: str | None = None
    realtor: dict[str, Any] | None = None
    extra_fields: dict[str, Any] = Field(default_factory=dict)
    data_warnings: list[str] = Field(default_factory=list)
    market_details: MarketDetails | None = None
    first_seen_at: str
    last_seen_at: str
    captured_at: str
    verified_at: str | None = None


class ListingDetail(ListingSummary):
    apartment_id: UUID
    complex_id: str
    complex_name: str
    registrations: list[BrokerRegistration] = Field(default_factory=list)
    market_details: MarketDetails | None = None
