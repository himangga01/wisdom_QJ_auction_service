from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('new','changed','removed','restored')",
            name="event_type_values",
        ),
        UniqueConstraint(
            "user_id",
            "change_event_id",
            name="uq_notifications_user_change_event",
        ),
        Index(
            "ix_notifications_user_read_created",
            "user_id",
            "read_at",
            "created_at",
        ),
        Index("ix_notifications_source_created", "source_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("tracked_sources.id", ondelete="RESTRICT"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("crawl_runs.id", ondelete="RESTRICT"), nullable=False
    )
    change_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("change_events.id", ondelete="RESTRICT"), nullable=False
    )
    apartment_id: Mapped[UUID] = mapped_column(
        ForeignKey("apartments.id", ondelete="RESTRICT"), nullable=False
    )
    listing_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("listing_groups.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    compare_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("crawl_runs.id", ondelete="RESTRICT")
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="notifications")
    source: Mapped["TrackedSource"] = relationship(
        back_populates="notifications"
    )
    run: Mapped["CrawlRun"] = relationship(
        back_populates="notifications",
        foreign_keys=[run_id],
    )
    change_event: Mapped["ChangeEvent"] = relationship(
        back_populates="notifications"
    )
    apartment: Mapped["Apartment"] = relationship()
    listing_group: Mapped["ListingGroup"] = relationship()


from app.models.entities import (  # noqa: E402
    Apartment,
    ChangeEvent,
    CrawlRun,
    ListingGroup,
    TrackedSource,
)
from app.models.user import User  # noqa: E402

__all__ = ["Notification"]
