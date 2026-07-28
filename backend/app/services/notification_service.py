from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Apartment,
    ChangeEvent,
    CrawlRun,
    Notification,
    SourceNotificationPreference,
    TrackedSource,
)
from app.schemas.notification import (
    NotificationItem,
    NotificationLink,
    NotificationPage,
    NotificationPreference,
)

EVENT_LABELS = {
    "new": "신규 매물",
    "changed": "매물 정보 변경",
    "removed": "매물 삭제 확인",
    "restored": "매물 재노출",
}
PREFERENCE_FIELDS = {
    "new": "notify_new",
    "changed": "notify_changed",
    "removed": "notify_removed",
    "restored": "notify_restored",
}
SAFE_SUMMARY_FIELDS = {
    "price",
    "deposit",
    "monthlyRent",
    "building",
    "floor",
    "direction",
    "supplyAreaM2",
    "exclusiveAreaM2",
    "managementFee",
    "moveInDate",
    "roomBathroom",
    "optionTags",
    "registrationCount",
    "state",
    "missingCount",
}


class NotificationError(RuntimeError):
    code = "notification_error"


class NotificationNotFoundError(NotificationError):
    code = "dataset_not_found"


class InvalidNotificationCursorError(NotificationError):
    code = "invalid_cursor"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _safe_value(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:200]
    if isinstance(value, list):
        return [_safe_value(item) for item in value[:20]]
    return str(value)[:200]


def _safe_snapshot(value: dict[str, Any] | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        key: _safe_value(item)
        for key, item in value.items()
        if key in SAFE_SUMMARY_FIELDS
    }


def _encode_cursor(created_at: datetime, notification_id: UUID) -> str:
    payload = json.dumps(
        [_aware(created_at).isoformat(), str(notification_id)],
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        created_at_raw, notification_id_raw = json.loads(
            base64.urlsafe_b64decode(padded).decode("utf-8")
        )
        created_at = datetime.fromisoformat(created_at_raw)
        return _aware(created_at), UUID(notification_id_raw)
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise InvalidNotificationCursorError(
            "유효하지 않은 알림 cursor입니다."
        ) from error


class NotificationService:
    def __init__(self, session: AsyncSession, actor_user_id: UUID) -> None:
        self.session = session
        self.actor_user_id = actor_user_id

    async def has_completed_baseline(self, source_id: UUID) -> bool:
        count = await self.session.scalar(
            select(func.count(CrawlRun.id)).where(
                CrawlRun.source_id == source_id,
                CrawlRun.status == "completed",
            )
        )
        return bool(count)

    async def previous_successful_run_id(
        self, source_id: UUID, current_run_id: UUID
    ) -> UUID | None:
        return await self.session.scalar(
            select(CrawlRun.id)
            .where(
                CrawlRun.source_id == source_id,
                CrawlRun.id != current_run_id,
                CrawlRun.status == "completed",
            )
            .order_by(
                CrawlRun.finished_at.desc().nullslast(),
                CrawlRun.created_at.desc(),
                CrawlRun.id.desc(),
            )
            .limit(1)
        )

    async def create_from_change_event(
        self,
        *,
        event: ChangeEvent,
        source: TrackedSource,
        apartment: Apartment,
        baseline: bool,
        compare_run_id: UUID | None,
    ) -> Notification | None:
        if baseline or source.owner_user_id != self.actor_user_id:
            return None
        preference = await self.session.get(
            SourceNotificationPreference, source.id
        )
        preference_field = PREFERENCE_FIELDS.get(event.event_type)
        if (
            preference is None
            or not preference.enabled
            or preference_field is None
            or not bool(getattr(preference, preference_field))
        ):
            return None
        existing = await self.session.scalar(
            select(Notification).where(
                Notification.user_id == source.owner_user_id,
                Notification.change_event_id == event.id,
            )
        )
        if existing is not None:
            return existing
        summary = {
            "changedFields": [
                field
                for field in event.changed_fields_json
                if field in SAFE_SUMMARY_FIELDS
            ],
            "before": _safe_snapshot(event.before_json),
            "after": _safe_snapshot(event.after_json),
        }
        notification = Notification(
            user_id=source.owner_user_id,
            source_id=source.id,
            run_id=event.run_id,
            change_event_id=event.id,
            apartment_id=apartment.id,
            listing_group_id=event.listing_group_id,
            event_type=event.event_type,
            title=f"{apartment.name} · {EVENT_LABELS[event.event_type]}",
            summary_json=summary,
            compare_run_id=compare_run_id,
            created_at=event.detected_at,
        )
        self.session.add(notification)
        return notification

    async def list(
        self,
        *,
        cursor: str | None,
        limit: int,
        unread_only: bool,
    ) -> NotificationPage:
        query = (
            select(Notification, TrackedSource.naver_complex_id)
            .join(TrackedSource, TrackedSource.id == Notification.source_id)
            .where(Notification.user_id == self.actor_user_id)
        )
        if unread_only:
            query = query.where(Notification.read_at.is_(None))
        if cursor:
            created_at, notification_id = _decode_cursor(cursor)
            query = query.where(
                or_(
                    Notification.created_at < created_at,
                    and_(
                        Notification.created_at == created_at,
                        Notification.id < notification_id,
                    ),
                )
            )
        rows = list(
            (
                await self.session.execute(
                    query.order_by(
                        Notification.created_at.desc(), Notification.id.desc()
                    ).limit(limit + 1)
                )
            ).all()
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [
            NotificationItem(
                id=notification.id,
                event_type=notification.event_type,
                title=notification.title,
                summary=notification.summary_json,
                read_at=notification.read_at,
                created_at=notification.created_at,
                link=NotificationLink(
                    source_id=notification.source_id,
                    complex_id=complex_id or "",
                    run_id=notification.run_id,
                    compare_run_id=notification.compare_run_id,
                    focus_listing_id=notification.listing_group_id,
                ),
            )
            for notification, complex_id in rows
        ]
        next_cursor = None
        if has_more and rows:
            last = rows[-1][0]
            next_cursor = _encode_cursor(last.created_at, last.id)
        return NotificationPage(items=items, next_cursor=next_cursor)

    async def unread_count(self) -> int:
        return int(
            await self.session.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == self.actor_user_id,
                    Notification.read_at.is_(None),
                )
            )
            or 0
        )

    async def mark_read(
        self, notification_id: UUID, *, read: bool
    ) -> Notification:
        notification = await self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == self.actor_user_id,
            )
        )
        if notification is None:
            raise NotificationNotFoundError("알림을 찾을 수 없습니다.")
        notification.read_at = datetime.now(timezone.utc) if read else None
        await self.session.commit()
        return notification

    async def read_all(self) -> int:
        result = await self.session.execute(
            update(Notification)
            .where(
                Notification.user_id == self.actor_user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=datetime.now(timezone.utc))
        )
        await self.session.commit()
        return int(result.rowcount or 0)

    async def _owned_source(self, source_id: UUID) -> TrackedSource:
        source = await self.session.scalar(
            select(TrackedSource).where(
                TrackedSource.id == source_id,
                TrackedSource.owner_user_id == self.actor_user_id,
            )
        )
        if source is None:
            raise NotificationNotFoundError("조사 출처를 찾을 수 없습니다.")
        return source

    async def get_preference(
        self, source_id: UUID
    ) -> NotificationPreference:
        await self._owned_source(source_id)
        preference = await self.session.get(
            SourceNotificationPreference, source_id
        )
        if preference is None:
            return NotificationPreference(
                source_id=source_id,
                enabled=False,
                notify_new=True,
                notify_changed=True,
                notify_removed=True,
                notify_restored=True,
            )
        return NotificationPreference.model_validate(preference)

    async def update_preference(
        self,
        source_id: UUID,
        *,
        enabled: bool,
        notify_new: bool,
        notify_changed: bool,
        notify_removed: bool,
        notify_restored: bool,
    ) -> NotificationPreference:
        await self._owned_source(source_id)
        preference = await self.session.get(
            SourceNotificationPreference, source_id
        )
        if preference is None:
            preference = SourceNotificationPreference(source_id=source_id)
            self.session.add(preference)
        preference.enabled = enabled
        preference.notify_new = notify_new
        preference.notify_changed = notify_changed
        preference.notify_removed = notify_removed
        preference.notify_restored = notify_restored
        await self.session.commit()
        return NotificationPreference.model_validate(preference)
