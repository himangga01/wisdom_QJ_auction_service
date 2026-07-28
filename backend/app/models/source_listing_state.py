from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SourceListingState(Base):
    __tablename__ = "source_listing_states"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "listing_group_id",
            name="uq_source_listing_states_source_listing_group",
        ),
        CheckConstraint(
            "visibility_state IN ('active','missing','removed')",
            name="visibility_state_values",
        ),
        CheckConstraint(
            "missing_count >= 0",
            name="missing_count_nonnegative",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("tracked_sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    listing_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("listing_groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    visibility_state: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
    )
    missing_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    source: Mapped["TrackedSource"] = relationship(back_populates="listing_states")
    listing_group: Mapped["ListingGroup"] = relationship(
        back_populates="source_states"
    )
