from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.auth_session import AuthSession
    from app.models.entities import TrackedSource


LEGACY_SYSTEM_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
LEGACY_SYSTEM_USER_EMAIL = "legacy-system@wisdom.invalid"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin','member')", name="role_values"),
        CheckConstraint("failed_login_count >= 0", name="failed_login_count_nonnegative"),
        CheckConstraint(
            "is_system OR password_hash IS NOT NULL",
            name="human_password_required",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    sessions: Mapped[list[AuthSession]] = relationship(back_populates="user")
    sources: Mapped[list[TrackedSource]] = relationship(back_populates="owner")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user")


from app.models.notification import Notification  # noqa: E402
