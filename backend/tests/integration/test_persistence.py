import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
import app.services.persistence_service as persistence_module
from app.crawler.types import (
    BrokerArticleDetail,
    ComplexDetail,
    CrawlPayload,
    ListingDetail,
)
from app.models import (
    Apartment,
    ApartmentSnapshot,
    BrokerArticleSnapshot,
    ChangeEvent,
    CrawlRun,
    ListingAggregate,
    ListingGroup,
    ListingSnapshot,
    TrackedSource,
)
from app.services.persistence_service import PersistenceService


class ScalarRows:
    def __init__(self, values=()) -> None:
        self.values = list(values)

    def all(self):
        return list(self.values)

    def first(self):
        return self.values[0] if self.values else None


class Transaction:
    def __init__(self, session) -> None:
        self.session = session

    async def __aenter__(self):
        self.session.begin_count += 1

    async def __aexit__(self, exc_type, _exc, _traceback):
        if exc_type is None:
            self.session.commit_count += 1
        else:
            self.session.rollback_count += 1


class NestedTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return None


class RecordingSession:
    def __init__(self, run: CrawlRun, source: TrackedSource) -> None:
        self.run = run
        self.source = source
        self.added = []
        self.begin_count = 0
        self.commit_count = 0
        self.rollback_count = 0

    def begin(self):
        return Transaction(self)

    def begin_nested(self):
        return NestedTransaction()

    async def get(self, model, identity, **_kwargs):
        if model is CrawlRun and identity == self.run.id:
            return self.run
        if model is TrackedSource and identity == self.source.id:
            return self.source
        return None

    async def scalar(self, _statement):
        return None

    async def scalars(self, _statement):
        return ScalarRows()

    def add(self, value) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        for value in self.added:
            if hasattr(value, "id") and value.id is None:
                value.id = uuid4()


class ExistingApartmentSession(RecordingSession):
    def __init__(
        self, run: CrawlRun, source: TrackedSource, apartment: Apartment
    ) -> None:
        super().__init__(run, source)
        self.apartment = apartment

    async def scalar(self, _statement):
        return self.apartment


class ExistingRecordPersistenceService(PersistenceService):
    def __init__(self, session, record) -> None:
        super().__init__(session)
        self.record = record

    async def _existing_records(self, **_kwargs):
        return [self.record]

    async def _source_group_ids(self, _source_id):
        return {self.record.group.id}

    async def _store_brokers(self, **_kwargs) -> None:
        return None


def test_new_listing_snapshot_aggregate_and_event_share_one_transaction() -> None:
    now = datetime(2026, 7, 22, tzinfo=timezone.utc)
    source = TrackedSource(
        id=uuid4(),
        source_url="https://fin.land.naver.com/map?complexId=12345",
        normalized_url="https://fin.land.naver.com/map?complexId=12345",
        url_hash="a" * 64,
    )
    run = CrawlRun(
        id=uuid4(),
        source_id=source.id,
        status="running",
        stage="details",
        progress=70,
    )
    payload = CrawlPayload(
        status="completed",
        apartment=ComplexDetail(
            complex_id="12345",
            name="샘플아파트",
            address="서울시 샘플구",
            captured_at=now,
        ),
        listings=[
            ListingDetail(
                trade_type="매매",
                price=720_000_000,
                building="107동",
                floor="12/25층",
                direction="남향",
                broker_articles=[
                    BrokerArticleDetail(
                        article_id="2407000001",
                        article_url="/articles/2407000001",
                        provider="네이버부동산",
                        is_npay=True,
                        description="",
                        captured_at=now,
                    )
                ],
                captured_at=now,
            )
        ],
        captured_at=now,
    )
    session = RecordingSession(run, source)

    outcome = asyncio.run(PersistenceService(session).persist(run.id, payload))

    assert (session.begin_count, session.commit_count, session.rollback_count) == (1, 1, 0)
    assert run.status == "completed"
    assert outcome.listing_count == 1
    assert any(isinstance(value, ApartmentSnapshot) for value in session.added)
    assert any(isinstance(value, ListingSnapshot) for value in session.added)
    assert any(isinstance(value, ListingAggregate) for value in session.added)
    assert any(isinstance(value, BrokerArticleSnapshot) for value in session.added)
    assert any(isinstance(value, ChangeEvent) for value in session.added)


@pytest.mark.parametrize(
    ("previous_enabled", "current_enabled", "expected"),
    [
        (True, True, True),
        (True, False, False),
        (False, True, False),
        (False, False, False),
    ],
)
def test_detail_comparison_requires_both_runs_enabled(
    monkeypatch, previous_enabled: bool, current_enabled: bool, expected: bool
) -> None:
    now = datetime(2026, 7, 28, tzinfo=timezone.utc)
    source = TrackedSource(
        id=uuid4(),
        source_url="https://fin.land.naver.com/map?complexId=12345",
        normalized_url="https://fin.land.naver.com/map?complexId=12345",
        url_hash="a" * 64,
    )
    run = CrawlRun(
        id=uuid4(),
        source_id=source.id,
        status="running",
        stage="details",
        progress=70,
        collect_broker_details=current_enabled,
    )
    apartment = Apartment(
        id=uuid4(),
        naver_complex_id="12345",
        name="샘플아파트",
        address="서울시 샘플구",
        details_json={},
        created_at=now,
        updated_at=now,
    )
    group = ListingGroup(
        id=uuid4(),
        apartment_id=apartment.id,
        identity_key="existing",
        first_seen_at=now,
        last_seen_at=now,
        state="active",
        missing_count=0,
    )
    snapshot = ListingSnapshot(
        id=uuid4(),
        run_id=uuid4(),
        listing_group_id=group.id,
        trade_type="매매",
        price=720_000_000,
        building="107동",
        floor="12/25층",
        direction="남향",
        status="active",
        captured_at=now,
    )
    record = persistence_module._ExistingRecord(
        identity=SimpleNamespace(listing_group_id=str(group.id)),
        group=group,
        latest_snapshot=snapshot,
        latest_aggregate=None,
        latest_article_ids=frozenset(),
        source_seen=True,
        source_state="active",
        source_missing_count=0,
        latest_collect_broker_details=previous_enabled,
    )
    payload = CrawlPayload(
        status="completed",
        apartment=ComplexDetail(
            complex_id="12345",
            name="샘플아파트",
            address="서울시 샘플구",
            captured_at=now,
        ),
        listings=[
            ListingDetail(
                trade_type="매매",
                price=720_000_000,
                building="107동",
                floor="12/25층",
                direction="남향",
                captured_at=now,
            )
        ],
        captured_at=now,
    )
    observed: list[bool] = []
    real_compare = persistence_module.compare_listings

    def recording_compare(before, after, *, compare_detail_fields=True):
        observed.append(compare_detail_fields)
        return real_compare(
            before,
            after,
            compare_detail_fields=compare_detail_fields,
        )

    monkeypatch.setattr(
        persistence_module,
        "choose_existing_listing",
        lambda _incoming, _candidates: SimpleNamespace(
            listing_group_id=str(group.id)
        ),
    )
    monkeypatch.setattr(persistence_module, "compare_listings", recording_compare)
    session = ExistingApartmentSession(run, source, apartment)

    asyncio.run(
        ExistingRecordPersistenceService(session, record).persist(run.id, payload)
    )

    assert observed == [expected]


def test_apartment_snapshot_uses_only_details_observed_by_the_current_source() -> None:
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    source = TrackedSource(
        id=uuid4(),
        source_url="https://fin.land.naver.com/map?complexId=12345&source=two",
        normalized_url="https://fin.land.naver.com/map?complexId=12345&source=two",
        url_hash="b" * 64,
    )
    run = CrawlRun(
        id=uuid4(),
        source_id=source.id,
        status="running",
        stage="details",
        progress=70,
    )
    apartment = Apartment(
        id=uuid4(),
        naver_complex_id="12345",
        name="다른 출처가 마지막으로 관찰한 이름",
        address="다른 출처가 마지막으로 관찰한 주소",
        details_json={
            "householdCount": 999,
            "managementOfficePhone": "02-0000-0000",
        },
        created_at=now,
        updated_at=now,
    )
    payload = CrawlPayload(
        status="completed",
        apartment=ComplexDetail(
            complex_id="12345",
            name="현재 출처가 관찰한 이름",
            address="",
            details={"householdCount": 120},
            captured_at=now,
        ),
        listings=[],
        captured_at=now,
    )
    session = ExistingApartmentSession(run, source, apartment)

    asyncio.run(PersistenceService(session).persist(run.id, payload))

    snapshot = next(
        value
        for value in session.added
        if isinstance(value, ApartmentSnapshot)
    )
    assert snapshot.details_json["details"] == {"household_count": 120}
    assert snapshot.details_json["name"] == "현재 출처가 관찰한 이름"
    assert snapshot.details_json["address"] == ""
