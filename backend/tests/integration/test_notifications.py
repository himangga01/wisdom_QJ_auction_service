from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.crawler.types import CrawlPayload, ComplexDetail, ListingDetail
from app.models import (
    Apartment,
    CrawlRun,
    Notification,
    SourceNotificationPreference,
    TrackedSource,
    User,
)
from app.services.notification_service import (
    NotificationNotFoundError,
    NotificationService,
)
from app.services.persistence_service import PersistenceService


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


def _payload(
    captured_at: datetime,
    *,
    status: str = "completed",
    visible: bool = True,
    price: int = 700_000_000,
) -> CrawlPayload:
    return CrawlPayload(
        status=status,
        apartment=ComplexDetail(
            complex_id="12345",
            name="테스트 아파트",
            address="서울시 테스트구",
            captured_at=captured_at,
        ),
        listings=(
            [
                ListingDetail(
                    trade_type="sale",
                    price=price,
                    building="101동",
                    floor="10/20층",
                    direction="남향",
                    captured_at=captured_at,
                )
            ]
            if visible
            else []
        ),
        captured_at=captured_at,
    )


async def _persist(
    session: AsyncSession,
    source_id: UUID,
    captured_at: datetime,
    **payload_options: object,
) -> UUID:
    run = CrawlRun(
        source_id=source_id,
        status="running",
        stage="details",
        progress=70,
        created_at=captured_at,
    )
    session.add(run)
    await session.commit()
    await PersistenceService(session).persist(
        run.id,
        _payload(captured_at, **payload_options),
    )
    return run.id


async def _owner_source(
    session: AsyncSession,
    *,
    email: str = "owner@example.com",
) -> tuple[User, TrackedSource]:
    owner = User(
        email=email,
        display_name="owner",
        password_hash="test-password-hash",
        role="member",
    )
    session.add(owner)
    await session.flush()
    source = TrackedSource(
        source_url="https://fin.land.naver.com/map?complexId=12345",
        normalized_url="https://fin.land.naver.com/map?complexId=12345",
        url_hash=("a" if email.startswith("owner") else "b") * 64,
        owner_user_id=owner.id,
    )
    session.add(source)
    await session.flush()
    return owner, source


@pytest.mark.asyncio
async def test_notifications_are_baseline_and_partial_safe(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        owner, source = await _owner_source(session)
        session.add(
            SourceNotificationPreference(
                source_id=source.id,
                enabled=True,
                notify_new=True,
                notify_changed=True,
                notify_removed=True,
                notify_restored=True,
            )
        )
        await session.commit()

        started_at = datetime(2026, 7, 29, tzinfo=timezone.utc)
        await _persist(session, source.id, started_at)
        assert list((await session.scalars(select(Notification))).all()) == []

        await _persist(
            session,
            source.id,
            started_at + timedelta(minutes=1),
            price=710_000_000,
        )
        await _persist(
            session,
            source.id,
            started_at + timedelta(minutes=2),
            status="partial",
            visible=False,
        )
        await _persist(
            session,
            source.id,
            started_at + timedelta(minutes=3),
            visible=False,
        )
        await _persist(
            session,
            source.id,
            started_at + timedelta(minutes=4),
            visible=False,
        )
        await _persist(
            session,
            source.id,
            started_at + timedelta(minutes=5),
            visible=True,
            price=710_000_000,
        )

        notifications = list(
            (
                await session.scalars(
                    select(Notification).order_by(Notification.created_at)
                )
            ).all()
        )
        assert [item.event_type for item in notifications] == [
            "changed",
            "removed",
            "restored",
        ]
        assert all(item.user_id == owner.id for item in notifications)
        assert all("description" not in item.summary_json for item in notifications)


@pytest.mark.asyncio
async def test_notification_compare_run_ignores_intervening_partial_run(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        owner, source = await _owner_source(session)
        session.add(SourceNotificationPreference(source_id=source.id, enabled=True))
        await session.commit()

        started_at = datetime(2026, 7, 29, tzinfo=timezone.utc)
        completed_baseline_id = await _persist(session, source.id, started_at)
        partial_id = await _persist(
            session,
            source.id,
            started_at + timedelta(minutes=1),
            status="partial",
        )
        changed_run_id = await _persist(
            session,
            source.id,
            started_at + timedelta(minutes=2),
            price=710_000_000,
        )

        notification = await session.scalar(
            select(Notification).where(Notification.run_id == changed_run_id)
        )
        assert notification is not None
        assert notification.compare_run_id == completed_baseline_id
        assert notification.compare_run_id != partial_id


@pytest.mark.asyncio
async def test_catalog_insert_conflict_requeries_inside_outer_transaction(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        existing = Apartment(
            naver_complex_id="catalog-race",
            name="기존 단지",
            address="서울",
        )
        session.add(existing)
        await session.commit()

        candidate = Apartment(
            naver_complex_id="catalog-race",
            name="경합 단지",
            address="부산",
        )
        async with session.begin():
            recovered, created = await PersistenceService(
                session
            )._insert_or_requery(
                candidate,
                select(Apartment).where(
                    Apartment.naver_complex_id == "catalog-race"
                ),
            )

            assert created is False
            assert recovered.id == existing.id
            assert session.in_transaction()


@pytest.mark.asyncio
async def test_notification_reads_and_preferences_are_owner_scoped(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        owner, source = await _owner_source(session)
        other, _ = await _owner_source(session, email="other@example.com")
        await session.commit()

        owner_service = NotificationService(session, owner.id)
        preference = await owner_service.update_preference(
            source.id,
            enabled=True,
            notify_new=False,
            notify_changed=True,
            notify_removed=True,
            notify_restored=False,
        )
        assert preference.enabled is True
        assert preference.notify_new is False

        with pytest.raises(NotificationNotFoundError):
            await NotificationService(session, other.id).get_preference(source.id)
