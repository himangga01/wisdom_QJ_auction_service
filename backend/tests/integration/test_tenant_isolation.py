from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, time, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.models import (
    Apartment,
    ApartmentSnapshot,
    CrawlRun,
    ListingAggregate,
    ListingGroup,
    ListingSnapshot,
    SourceListingState,
    TrackedSource,
    User,
)
from app.schemas.schedule import ScheduleCreate
from app.services.analysis_service import AnalysisNotFoundError, AnalysisService
from app.services.export_service import ExportNotFoundError, ExportService
from app.services.query_service import QueryNotFoundError, QueryService
from app.services.schedule_service import ScheduleService, ScheduleSourceNotFoundError


class RecordingDispatcher:
    def __init__(self) -> None:
        self.enqueued: list = []

    def enqueue(self, run_id) -> None:
        self.enqueued.append(run_id)

    def cancel(self, _run_id) -> None:
        return None


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


def _user(email: str) -> User:
    return User(
        email=email,
        display_name=email.split("@", 1)[0],
        password_hash="test-password-hash",
        role="member",
    )


@pytest.mark.asyncio
async def test_same_url_is_independent_and_request_services_hide_other_tenant_ids(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        first_user = _user("first@example.com")
        second_user = _user("second@example.com")
        session.add_all([first_user, second_user])
        await session.commit()

        dispatcher = RecordingDispatcher()
        analysis = AnalysisService(session, dispatcher)
        source_url = "https://fin.land.naver.com/map?complexId=12345"
        first_run, first_created = await analysis.create_for_user(
            first_user.id,
            source_url,
            collect_broker_details=True,
            interaction_delay_preset="normal",
        )
        second_run, second_created = await analysis.create_for_user(
            second_user.id,
            source_url,
            collect_broker_details=True,
            interaction_delay_preset="normal",
        )

        sources = list(
            (
                await session.scalars(
                    select(TrackedSource).order_by(TrackedSource.owner_user_id)
                )
            ).all()
        )
        assert first_created is True
        assert second_created is True
        assert len(sources) == 2
        assert sources[0].url_hash == sources[1].url_hash
        assert {source.owner_user_id for source in sources} == {
            first_user.id,
            second_user.id,
        }

        first_source = next(
            source for source in sources if source.owner_user_id == first_user.id
        )
        second_source = next(
            source for source in sources if source.owner_user_id == second_user.id
        )
        first_run.status = "completed"
        first_run.stage = "save"
        first_run.progress = 100
        first_run.finished_at = datetime(2026, 7, 29, tzinfo=timezone.utc)
        second_run.status = "completed"
        second_run.stage = "save"
        second_run.progress = 100
        second_run.finished_at = datetime(2026, 7, 29, 1, tzinfo=timezone.utc)
        apartment = Apartment(
            naver_complex_id="12345",
            name="테스트 아파트",
            address="서울시 테스트구",
        )
        session.add(apartment)
        await session.flush()
        first_source.naver_complex_id = apartment.naver_complex_id
        second_source.naver_complex_id = apartment.naver_complex_id
        first_snapshot = ApartmentSnapshot(
            run_id=first_run.id,
            apartment_id=apartment.id,
            details_json={
                "name": "첫 번째 사용자 아파트",
                "address": "서울시 첫 번째구",
            },
            captured_at=first_run.finished_at,
        )
        second_snapshot = ApartmentSnapshot(
            run_id=second_run.id,
            apartment_id=apartment.id,
            details_json={
                "name": "두 번째 사용자 아파트",
                "address": "서울시 두 번째구",
            },
            captured_at=second_run.finished_at,
        )
        group = ListingGroup(
            apartment_id=apartment.id,
            identity_key="shared-listing",
            first_seen_at=first_run.finished_at,
            last_seen_at=first_run.finished_at,
            state="active",
            missing_count=0,
        )
        session.add_all([first_snapshot, second_snapshot, group])
        await session.flush()
        first_listing = ListingSnapshot(
            run_id=first_run.id,
            listing_group_id=group.id,
            trade_type="sale",
            price=700_000_000,
            status="active",
            captured_at=first_run.finished_at,
        )
        second_listing = ListingSnapshot(
            run_id=second_run.id,
            listing_group_id=group.id,
            trade_type="sale",
            price=710_000_000,
            status="active",
            captured_at=second_run.finished_at,
        )
        session.add_all([first_listing, second_listing])
        await session.flush()
        session.add_all(
            [
                ListingAggregate(listing_snapshot_id=first_listing.id),
                ListingAggregate(listing_snapshot_id=second_listing.id),
                SourceListingState(
                    source_id=first_source.id,
                    listing_group_id=group.id,
                    visibility_state="active",
                    missing_count=0,
                    first_seen_at=first_run.finished_at,
                    last_seen_at=first_run.finished_at,
                    updated_at=first_run.finished_at,
                ),
                SourceListingState(
                    source_id=second_source.id,
                    listing_group_id=group.id,
                    visibility_state="active",
                    missing_count=0,
                    first_seen_at=second_run.finished_at,
                    last_seen_at=second_run.finished_at,
                    updated_at=second_run.finished_at,
                ),
            ]
        )
        await session.commit()

        with pytest.raises(AnalysisNotFoundError) as analysis_error:
            await analysis.get(first_user.id, second_run.id)
        assert analysis_error.value.code == "dataset_not_found"

        first_query = QueryService(session, first_user.id)
        first_page = await first_query.apartments(query=None, page=1, page_size=20)
        assert [item.source_id for item in first_page.items] == [first_source.id]
        assert first_page.items[0].complex_name == "첫 번째 사용자 아파트"
        assert (
            await first_query.apartments(
                query="첫 번째 사용자",
                page=1,
                page_size=20,
            )
        ).total == 1
        assert (
            await first_query.apartments(
                query="두 번째 사용자",
                page=1,
                page_size=20,
            )
        ).total == 0
        with pytest.raises(QueryNotFoundError):
            await first_query.apartment(
                apartment.naver_complex_id,
                source_id=second_source.id,
                run_id=second_run.id,
            )
        with pytest.raises(QueryNotFoundError):
            await first_query.history(
                apartment.naver_complex_id,
                source_id=second_source.id,
            )
        with pytest.raises(QueryNotFoundError):
            await first_query.listings(
                apartment.naver_complex_id,
                source_id=second_source.id,
                run_id=second_run.id,
                trade_type=None,
                status=None,
            )
        with pytest.raises(QueryNotFoundError):
            await first_query.listing(
                group.id,
                source_id=second_source.id,
                run_id=second_run.id,
            )
        with pytest.raises(QueryNotFoundError):
            await first_query.dashboard(second_source.id)

        with pytest.raises(ExportNotFoundError) as export_error:
            await ExportService(session, first_user.id).generate(
                second_source.id,
                from_date=None,
                to_date=None,
            )
        assert export_error.value.code == "dataset_not_found"

        schedules = ScheduleService(session, first_user.id)
        with pytest.raises(ScheduleSourceNotFoundError) as schedule_error:
            await schedules.create(
                ScheduleCreate(
                    sourceId=second_source.id,
                    cadence="daily",
                    time=time(9),
                )
            )
        assert schedule_error.value.code == "dataset_not_found"
