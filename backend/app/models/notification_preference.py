from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SourceNotificationPreference(Base):
    __tablename__ = "source_notification_preferences"

    source_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("tracked_sources.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_new: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_changed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_removed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_restored: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    source: Mapped["TrackedSource"] = relationship(
        back_populates="notification_preference"
    )


from app.models.entities import TrackedSource  # noqa: E402

__all__ = ["SourceNotificationPreference"]
