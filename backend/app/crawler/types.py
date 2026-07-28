from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CapturedModel(BaseModel):
    captured_at: datetime = Field(default_factory=utc_now)

    @field_validator("captured_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        return value.astimezone(timezone.utc)


class RealtorProfile(BaseModel):
    name: str | None = None
    representative: str | None = None
    phone: str | None = None
    registration_number: str | None = None
    address: str | None = None


class MarketDetails(CapturedModel):
    finance: dict[str, str] = Field(default_factory=dict)
    transactions: dict[str, str] = Field(default_factory=dict)
    costs: dict[str, str] = Field(default_factory=dict)
    maintenance: dict[str, str] = Field(default_factory=dict)
    complex: dict[str, str] = Field(default_factory=dict)
    location: dict[str, str] = Field(default_factory=dict)
    extra_fields: dict[str, str] = Field(default_factory=dict)


class BrokerArticleDetail(CapturedModel):
    article_id: str
    article_url: str | None = None
    provider: str
    is_npay: bool
    detail_collected: bool = True
    advertised_price: int | None = None
    price_per_3_3m2: int | None = None
    management_fee: int | None = None
    loan_description: str | None = None
    supply_area_m2: Decimal | None = None
    exclusive_area_m2: Decimal | None = None
    exclusive_rate: int | None = None
    floor: str | None = None
    room_count: int | None = None
    bathroom_count: int | None = None
    direction: str | None = None
    structure: str | None = None
    move_in_date: str | None = None
    description: str = ""
    option_tags: list[str] = Field(default_factory=list)
    verified_at: date | None = None
    first_published_at: date | None = None
    realtor: RealtorProfile | None = None
    market_details: MarketDetails | None = None
    extra_fields: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ComplexDetail(CapturedModel):
    complex_id: str
    name: str
    address: str
    details: dict[str, str] = Field(default_factory=dict)


class ListingDetail(CapturedModel):
    source_group_id: str | None = None
    trade_type: str
    price: int | None = None
    deposit: int | None = None
    monthly_rent: int | None = None
    building: str | None = None
    floor: str | None = None
    direction: str | None = None
    supply_area: Decimal | None = None
    exclusive_area: Decimal | None = None
    broker_articles: list[BrokerArticleDetail] = Field(default_factory=list)
    market_details: MarketDetails | None = None
    displayed_broker_count: int | None = None
    warnings: list[str] = Field(default_factory=list)

    @property
    def article_ids(self) -> frozenset[str]:
        return frozenset(article.article_id for article in self.broker_articles)


class CrawlPayload(CapturedModel):
    status: Literal["completed", "partial"]
    apartment: ComplexDetail
    listings: list[ListingDetail]
    trade_counts: dict[str, int] = Field(default_factory=dict)
    displayed_listing_count: int | None = None
    warnings: list[str] = Field(default_factory=list)
