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
from app.models import CrawlRun, SourceListingState, TrackedSource, User
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
    status: str,
    visible: bool,
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
                    price=700_000_000,
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


async def _persist_run(
    session: AsyncSession,
    source_id: UUID,
    captured_at: datetime,
    *,
    status: str,
    visible: bool,
) -> None:
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
        _payload(captured_at, status=status, visible=visible),
    )


@pytest.mark.asyncio
async def test_listing_lifecycle_is_source_specific_and_partial_absence_is_ignored(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first_user = User(
            email="first@example.com",
            display_name="first",
            password_hash="test-password-hash",
            role="member",
        )
        second_user = User(
            email="second@example.com",
            display_name="second",
            password_hash="test-password-hash",
            role="member",
        )
        session.add_all([first_user, second_user])
        await session.flush()
        first_source = TrackedSource(
            source_url="https://fin.land.naver.com/map?complexId=12345&source=first",
            normalized_url="https://fin.land.naver.com/map?complexId=12345&source=first",
            url_hash="a" * 64,
            owner_user_id=first_user.id,
        )
        second_source = TrackedSource(
            source_url="https://fin.land.naver.com/map?complexId=12345&source=second",
            normalized_url="https://fin.land.naver.com/map?complexId=12345&source=second",
            url_hash="b" * 64,
            owner_user_id=second_user.id,
        )
        session.add_all([first_source, second_source])
        await session.commit()
        first_source_id = first_source.id
        second_source_id = second_source.id

        started_at = datetime(2026, 7, 29, tzinfo=timezone.utc)
        await _persist_run(
            session,
            first_source_id,
            started_at,
            status="completed",
            visible=True,
        )
        await _persist_run(
            session,
            second_source_id,
            started_at + timedelta(minutes=1),
            status="completed",
            visible=True,
        )
        states = list(
            (
                await session.scalars(
                    select(SourceListingState).order_by(SourceListingState.source_id)
                )
            ).all()
        )
        assert len(states) == 2
        assert {(state.visibility_state, state.missing_count) for state in states} == {
            ("active", 0)
        }
        await session.rollback()

        await _persist_run(
            session,
            first_source_id,
            started_at + timedelta(minutes=2),
            status="completed",
            visible=False,
        )
        await _persist_run(
            session,
            first_source_id,
            started_at + timedelta(minutes=3),
            status="partial",
            visible=False,
        )
        first_state = await session.scalar(
            select(SourceListingState).where(
                SourceListingState.source_id == first_source_id
            )
        )
        second_state = await session.scalar(
            select(SourceListingState).where(
                SourceListingState.source_id == second_source_id
            )
        )
        assert first_state is not None
        assert second_state is not None
        assert (first_state.visibility_state, first_state.missing_count) == (
            "missing",
            1,
        )
        assert (second_state.visibility_state, second_state.missing_count) == (
            "active",
            0,
        )
        await session.rollback()

        await _persist_run(
            session,
            first_source_id,
            started_at + timedelta(minutes=4),
            status="completed",
            visible=False,
        )
        removed_state = await session.scalar(
            select(SourceListingState).where(
                SourceListingState.source_id == first_source_id
            )
        )
        assert removed_state is not None
        assert (removed_state.visibility_state, removed_state.missing_count) == (
            "removed",
            2,
        )
        assert removed_state.removed_at == started_at + timedelta(minutes=4)
        await session.rollback()

        await _persist_run(
            session,
            first_source_id,
            started_at + timedelta(minutes=5),
            status="completed",
            visible=True,
        )
        restored_state = await session.scalar(
            select(SourceListingState).where(
                SourceListingState.source_id == first_source_id
            )
        )
        assert restored_state is not None
        assert (restored_state.visibility_state, restored_state.missing_count) == (
            "active",
            0,
        )
        assert restored_state.removed_at is None
