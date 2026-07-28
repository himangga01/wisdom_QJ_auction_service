from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from app.schemas.analysis import ApiSchema

NotificationEventType = Literal["new", "changed", "removed", "restored"]


class NotificationLink(ApiSchema):
    source_id: UUID
    complex_id: str
    run_id: UUID
    compare_run_id: UUID | None = None
    focus_listing_id: UUID


class NotificationItem(ApiSchema):
    id: UUID
    event_type: NotificationEventType
    title: str
    summary: dict[str, Any]
    read_at: datetime | None = None
    created_at: datetime
    link: NotificationLink


class NotificationPage(ApiSchema):
    items: list[NotificationItem]
    next_cursor: str | None = None


class NotificationUnreadCount(ApiSchema):
    count: int


class NotificationReadPatch(ApiSchema):
    read: bool = True


class NotificationReadAll(ApiSchema):
    updated_count: int


class NotificationPreferencePatch(ApiSchema):
    enabled: bool
    notify_new: bool
    notify_changed: bool
    notify_removed: bool
    notify_restored: bool


class NotificationPreference(NotificationPreferencePatch):
    source_id: UUID
