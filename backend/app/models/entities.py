from __future__ import annotations

from datetime import datetime, time, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TrackedSource(Base):
    __tablename__ = "tracked_sources"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "url_hash",
            name="uq_tracked_sources_owner_url_hash",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    naver_complex_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    runs: Mapped[list[CrawlRun]] = relationship(back_populates="source")
    schedules: Mapped[list[CrawlSchedule]] = relationship(back_populates="source")
    listing_states: Mapped[list["SourceListingState"]] = relationship(
        back_populates="source"
    )
    notification_preference: Mapped["SourceNotificationPreference | None"] = relationship(
        back_populates="source", uselist=False
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="source"
    )
    owner: Mapped["User"] = relationship(back_populates="sources")


class CrawlRun(Base):
    __tablename__ = "crawl_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','completed','partial','failed','blocked','cancelled')",
            name="status_values",
        ),
        CheckConstraint(
            "stage IN ('url','complex','listings','brokers','details','compare','save')",
            name="stage_values",
        ),
        CheckConstraint(
            "interaction_delay_preset IN "
            "('very_fast','fast','normal','careful','very_careful')",
            name="interaction_delay_preset_values",
        ),
        CheckConstraint("progress BETWEEN 0 AND 100", name="progress_range"),
        Index(
            "uq_crawl_runs_active_source",
            "source_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("tracked_sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    stage: Mapped[str] = mapped_column(String(20), default="url", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    selector_version: Mapped[str | None] = mapped_column(String(80))
    collect_broker_details: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    interaction_delay_preset: Mapped[str] = mapped_column(
        String(20),
        default="normal",
        server_default=text("'normal'"),
        nullable=False,
    )

    source: Mapped[TrackedSource] = relationship(back_populates="runs")
    apartment_snapshots: Mapped[list[ApartmentSnapshot]] = relationship(
        back_populates="run"
    )
    listing_snapshots: Mapped[list[ListingSnapshot]] = relationship(back_populates="run")
    broker_snapshots: Mapped[list[BrokerArticleSnapshot]] = relationship(
        back_populates="run"
    )
    change_events: Mapped[list[ChangeEvent]] = relationship(back_populates="run")
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="run", foreign_keys="Notification.run_id"
    )


class Apartment(Base):
    __tablename__ = "apartments"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    naver_complex_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    details_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    snapshots: Mapped[list[ApartmentSnapshot]] = relationship(back_populates="apartment")
    listing_groups: Mapped[list[ListingGroup]] = relationship(back_populates="apartment")


class ApartmentSnapshot(Base):
    __tablename__ = "apartment_snapshots"
    __table_args__ = (UniqueConstraint("run_id", "apartment_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("crawl_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    apartment_id: Mapped[UUID] = mapped_column(
        ForeignKey("apartments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    run: Mapped[CrawlRun] = relationship(back_populates="apartment_snapshots")
    apartment: Mapped[Apartment] = relationship(back_populates="snapshots")


class ListingGroup(Base):
    __tablename__ = "listing_groups"
    __table_args__ = (UniqueConstraint("apartment_id", "identity_key"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    apartment_id: Mapped[UUID] = mapped_column(
        ForeignKey("apartments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    identity_key: Mapped[str] = mapped_column(String(128), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="new", nullable=False)
    missing_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    apartment: Mapped[Apartment] = relationship(back_populates="listing_groups")
    snapshots: Mapped[list[ListingSnapshot]] = relationship(back_populates="listing_group")
    broker_articles: Mapped[list[BrokerArticle]] = relationship(
        back_populates="listing_group"
    )
    change_events: Mapped[list[ChangeEvent]] = relationship(
        back_populates="listing_group"
    )
    source_states: Mapped[list["SourceListingState"]] = relationship(
        back_populates="listing_group"
    )


class ListingSnapshot(Base):
    __tablename__ = "listing_snapshots"
    __table_args__ = (UniqueConstraint("run_id", "listing_group_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("crawl_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    listing_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("listing_groups.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    trade_type: Mapped[str] = mapped_column(String(30), nullable=False)
    price: Mapped[int | None] = mapped_column(BigInteger)
    deposit: Mapped[int | None] = mapped_column(BigInteger)
    monthly_rent: Mapped[int | None] = mapped_column(BigInteger)
    building: Mapped[str | None] = mapped_column(String(80))
    floor: Mapped[str | None] = mapped_column(String(80))
    direction: Mapped[str | None] = mapped_column(String(80))
    supply_area: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    exclusive_area: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    run: Mapped[CrawlRun] = relationship(back_populates="listing_snapshots")
    listing_group: Mapped[ListingGroup] = relationship(back_populates="snapshots")
    aggregate: Mapped[ListingAggregate | None] = relationship(
        back_populates="listing_snapshot", uselist=False
    )
    market_detail: Mapped[MarketDetailSnapshot | None] = relationship(
        back_populates="listing_snapshot", uselist=False
    )


class BrokerArticle(Base):
    __tablename__ = "broker_articles"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    listing_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("listing_groups.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    naver_article_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    is_npay: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    article_url: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    listing_group: Mapped[ListingGroup] = relationship(back_populates="broker_articles")
    snapshots: Mapped[list[BrokerArticleSnapshot]] = relationship(
        back_populates="broker_article"
    )


class BrokerArticleSnapshot(Base):
    __tablename__ = "broker_article_snapshots"
    __table_args__ = (UniqueConstraint("run_id", "broker_article_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("crawl_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    broker_article_id: Mapped[UUID] = mapped_column(
        ForeignKey("broker_articles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    description_hash: Mapped[str | None] = mapped_column(String(64))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    run: Mapped[CrawlRun] = relationship(back_populates="broker_snapshots")
    broker_article: Mapped[BrokerArticle] = relationship(back_populates="snapshots")


class ListingAggregate(Base):
    __tablename__ = "listing_aggregates"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    listing_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("listing_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    option_tags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    move_in_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    management_fee_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    room_bath_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    loan_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    warnings_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    listing_snapshot: Mapped[ListingSnapshot] = relationship(back_populates="aggregate")


class MarketDetailSnapshot(Base):
    __tablename__ = "market_detail_snapshots"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    listing_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("listing_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    finance_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    transactions_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    costs_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    maintenance_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    location_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    listing_snapshot: Mapped[ListingSnapshot] = relationship(
        back_populates="market_detail"
    )


class ChangeEvent(Base):
    __tablename__ = "change_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("crawl_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    listing_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("listing_groups.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_fields_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    run: Mapped[CrawlRun] = relationship(back_populates="change_events")
    listing_group: Mapped[ListingGroup] = relationship(back_populates="change_events")
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="change_event"
    )


class CrawlSchedule(Base):
    __tablename__ = "crawl_schedules"
    __table_args__ = (
        CheckConstraint("cadence IN ('daily','weekdays','weekly')", name="cadence_values"),
        CheckConstraint("weekday IS NULL OR weekday BETWEEN 0 AND 6", name="weekday_range"),
        CheckConstraint(
            "interaction_delay_preset IN "
            "('very_fast','fast','normal','careful','very_careful')",
            name="interaction_delay_preset_values",
        ),
        UniqueConstraint("source_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("tracked_sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    cadence: Mapped[str] = mapped_column(String(20), nullable=False)
    time_of_day: Mapped[time] = mapped_column(Time, nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Seoul", nullable=False)
    weekday: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    collect_broker_details: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    interaction_delay_preset: Mapped[str] = mapped_column(
        String(20),
        default="normal",
        server_default=text("'normal'"),
        nullable=False,
    )
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    source: Mapped[TrackedSource] = relationship(back_populates="schedules")
