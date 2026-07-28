from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from hashlib import sha256
from typing import TypeVar
from urllib.parse import urljoin
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crawler.navigation import validate_internal_article_href
from app.crawler.selectors import SELECTOR_VERSION
from app.crawler.types import CrawlPayload, ListingDetail, MarketDetails
from app.domain.aggregator import AggregatedListingInfo, aggregate_broker_articles
from app.domain.apartment_details import normalize_apartment_details
from app.domain.comparator import (
    ComparableListing,
    compare_listings,
    transition_absence,
    transition_presence,
)
from app.domain.listing_identity import (
    ExistingListingIdentity,
    ListingIdentityInput,
    build_identity_key,
    choose_existing_listing,
)
from app.models import (
    Apartment,
    ApartmentSnapshot,
    BrokerArticle,
    BrokerArticleSnapshot,
    ChangeEvent,
    CrawlRun,
    ListingAggregate,
    ListingGroup,
    ListingSnapshot,
    MarketDetailSnapshot,
    SourceListingState,
    TrackedSource,
)
from app.services.notification_service import NotificationService


class PersistenceError(RuntimeError):
    code = "persistence_failed"


class RunNotFoundError(PersistenceError):
    code = "analysis_not_found"


class SourceComplexMismatchError(PersistenceError):
    code = "ambiguous_source"


class ArticleGroupConflictError(PersistenceError):
    code = "article_group_conflict"


@dataclass(frozen=True, slots=True)
class PersistenceOutcome:
    run_id: UUID
    status: str
    apartment_id: UUID | None
    listing_count: int
    event_count: int
    already_terminal: bool = False


@dataclass(slots=True)
class _ExistingRecord:
    identity: ExistingListingIdentity
    group: ListingGroup
    latest_snapshot: ListingSnapshot | None
    latest_aggregate: ListingAggregate | None
    latest_article_ids: frozenset[str]
    source_listing_state: SourceListingState | None = None
    source_seen: bool = False
    source_state: str = "active"
    source_missing_count: int = 0
    latest_collect_broker_details: bool = True


TERMINAL_RUN_STATUSES = {"completed", "partial", "failed", "blocked", "cancelled"}
CatalogEntity = TypeVar("CatalogEntity")


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PersistenceError("수집 시각은 timezone-aware 값이어야 합니다.")
    return value.astimezone(timezone.utc)


def _date_as_datetime(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _collect_broker_details_enabled(run: object) -> bool:
    value = getattr(run, "collect_broker_details", True)
    return True if value is None else bool(value)


def _merge_current_apartment_details(
    current: dict[str, object], incoming: dict[str, object]
) -> dict[str, object]:
    merged, _ = normalize_apartment_details(current)  # type: ignore[arg-type]
    normalized_incoming, _ = normalize_apartment_details(incoming)  # type: ignore[arg-type]
    merged.update(normalized_incoming)
    return merged


def _comparable_json(value: ComparableListing) -> dict[str, object]:
    return {
        "price": value.price,
        "deposit": value.deposit,
        "monthlyRent": value.monthly_rent,
        "building": value.building,
        "floor": value.floor,
        "direction": value.direction,
        "supplyAreaM2": value.supply_area_m2,
        "exclusiveAreaM2": value.exclusive_area_m2,
        "managementFee": value.management_fee,
        "moveInDate": value.move_in_date,
        "roomBathroom": value.room_bathroom,
        "loan": value.loan,
        "optionTags": sorted(value.option_tags),
        "registrationCount": value.registration_count,
        "articleIds": sorted(value.article_ids),
    }


def _identity_input(
    complex_id: str, listing: ListingDetail
) -> ListingIdentityInput:
    return ListingIdentityInput(
        complex_id=complex_id,
        trade_type=listing.trade_type,
        building=listing.building,
        exclusive_area=listing.exclusive_area,
        floor=listing.floor,
        direction=listing.direction,
        normalized_price=listing.price,
        article_ids=listing.article_ids,
    )


def _incoming_comparable(
    listing: ListingDetail, aggregate: AggregatedListingInfo
) -> ComparableListing:
    return ComparableListing(
        price=listing.price,
        deposit=listing.deposit,
        monthly_rent=listing.monthly_rent,
        building=listing.building,
        floor=listing.floor,
        direction=listing.direction,
        supply_area_m2=(
            float(listing.supply_area) if listing.supply_area is not None else None
        ),
        exclusive_area_m2=(
            float(listing.exclusive_area)
            if listing.exclusive_area is not None
            else None
        ),
        management_fee=aggregate.management_fee_summary,
        move_in_date=aggregate.move_in_summary,
        room_bathroom=aggregate.room_bath_summary,
        loan=aggregate.loan_summary,
        option_tags=tuple(sorted(aggregate.option_tags)),
        registration_count=aggregate.source_count,
        article_ids=listing.article_ids,
    )


class PersistenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _insert_or_requery(
        self,
        candidate: CatalogEntity,
        lookup: Select,
    ) -> tuple[CatalogEntity, bool]:
        try:
            async with self.session.begin_nested():
                self.session.add(candidate)
                await self.session.flush()
            return candidate, True
        except IntegrityError:
            existing = await self.session.scalar(lookup)
            if existing is None:
                raise
            return existing, False

    async def _latest_complete_snapshot(
        self, *, group_id: UUID, source_id: UUID, current_run_id: UUID
    ) -> ListingSnapshot | None:
        return (
            await self.session.scalars(
                select(ListingSnapshot)
                .join(CrawlRun, CrawlRun.id == ListingSnapshot.run_id)
                .where(
                    ListingSnapshot.listing_group_id == group_id,
                    CrawlRun.source_id == source_id,
                    CrawlRun.status == "completed",
                    CrawlRun.id != current_run_id,
                )
                .order_by(ListingSnapshot.captured_at.desc())
                .limit(1)
            )
        ).first()

    async def _run_article_ids(
        self, *, run_id: UUID, group_id: UUID
    ) -> frozenset[str]:
        result = await self.session.scalars(
            select(BrokerArticle.naver_article_id)
            .join(
                BrokerArticleSnapshot,
                BrokerArticleSnapshot.broker_article_id == BrokerArticle.id,
            )
            .where(
                BrokerArticleSnapshot.run_id == run_id,
                BrokerArticle.listing_group_id == group_id,
            )
        )
        return frozenset(result.all())

    async def _all_article_ids(self, group_id: UUID) -> frozenset[str]:
        result = await self.session.scalars(
            select(BrokerArticle.naver_article_id).where(
                BrokerArticle.listing_group_id == group_id
            )
        )
        return frozenset(result.all())

    async def _aggregate_for(
        self, snapshot: ListingSnapshot | None
    ) -> ListingAggregate | None:
        if snapshot is None:
            return None
        return await self.session.scalar(
            select(ListingAggregate).where(
                ListingAggregate.listing_snapshot_id == snapshot.id
            )
        )

    async def _existing_records(
        self,
        *,
        apartment_id: UUID,
        complex_id: str,
        source_id: UUID,
        current_run_id: UUID,
    ) -> list[_ExistingRecord]:
        groups = list(
            (
                await self.session.scalars(
                    select(ListingGroup).where(
                        ListingGroup.apartment_id == apartment_id
                    )
                )
            ).all()
        )
        group_ids = {group.id for group in groups}
        source_states = {
            state.listing_group_id: state
            for state in (
                await self.session.scalars(
                    select(SourceListingState).where(
                        SourceListingState.source_id == source_id,
                        SourceListingState.listing_group_id.in_(group_ids),
                    )
                )
            ).all()
        }
        records: list[_ExistingRecord] = []
        for group in groups:
            complete_snapshot = await self._latest_complete_snapshot(
                group_id=group.id,
                source_id=source_id,
                current_run_id=current_run_id,
            )
            identity_snapshot = complete_snapshot
            if identity_snapshot is None:
                identity_snapshot = (
                    await self.session.scalars(
                        select(ListingSnapshot)
                        .where(ListingSnapshot.listing_group_id == group.id)
                        .order_by(ListingSnapshot.captured_at.desc())
                        .limit(1)
                    )
                ).first()
            if identity_snapshot is None:
                continue
            article_ids = await self._all_article_ids(group.id)
            identity_input = ListingIdentityInput(
                complex_id=complex_id,
                trade_type=identity_snapshot.trade_type,
                building=identity_snapshot.building,
                exclusive_area=identity_snapshot.exclusive_area,
                floor=identity_snapshot.floor,
                direction=identity_snapshot.direction,
                normalized_price=identity_snapshot.price,
                article_ids=article_ids,
            )
            source_state = source_states.get(group.id)
            records.append(
                _ExistingRecord(
                    identity=ExistingListingIdentity(
                        listing_group_id=str(group.id),
                        identity_key=group.identity_key,
                        input=identity_input,
                    ),
                    group=group,
                    latest_snapshot=complete_snapshot,
                    latest_aggregate=await self._aggregate_for(complete_snapshot),
                    latest_article_ids=(
                        await self._run_article_ids(
                            run_id=complete_snapshot.run_id, group_id=group.id
                        )
                        if complete_snapshot is not None
                        else frozenset()
                    ),
                    source_listing_state=source_state,
                    source_seen=source_state is not None,
                    source_state=(
                        source_state.visibility_state
                        if source_state is not None
                        else "active"
                    ),
                    source_missing_count=(
                        source_state.missing_count
                        if source_state is not None
                        else 0
                    ),
                    latest_collect_broker_details=(
                        _collect_broker_details_enabled(
                            await self.session.get(CrawlRun, complete_snapshot.run_id)
                        )
                        if complete_snapshot is not None
                        else True
                    ),
                )
            )
        return records

    async def _source_group_ids(self, source_id: UUID) -> set[UUID]:
        result = await self.session.scalars(
            select(SourceListingState.listing_group_id).where(
                SourceListingState.source_id == source_id
            )
        )
        return set(result.all())

    def _previous_comparable(self, record: _ExistingRecord) -> ComparableListing | None:
        snapshot = record.latest_snapshot
        if snapshot is None:
            return None
        aggregate = record.latest_aggregate
        return ComparableListing(
            price=snapshot.price,
            deposit=snapshot.deposit,
            monthly_rent=snapshot.monthly_rent,
            building=snapshot.building,
            floor=snapshot.floor,
            direction=snapshot.direction,
            supply_area_m2=(
                float(snapshot.supply_area)
                if snapshot.supply_area is not None
                else None
            ),
            exclusive_area_m2=(
                float(snapshot.exclusive_area)
                if snapshot.exclusive_area is not None
                else None
            ),
            management_fee=(aggregate.management_fee_summary if aggregate else ""),
            move_in_date=(aggregate.move_in_summary if aggregate else ""),
            room_bathroom=(aggregate.room_bath_summary if aggregate else ""),
            loan=(aggregate.loan_summary if aggregate else ""),
            option_tags=tuple(sorted(aggregate.option_tags_json if aggregate else [])),
            registration_count=(aggregate.source_count if aggregate else 0),
            article_ids=record.latest_article_ids,
        )

    async def _store_brokers(
        self,
        *,
        run: CrawlRun,
        group: ListingGroup,
        listing: ListingDetail,
        captured_at: datetime,
    ) -> None:
        for detail in sorted(listing.broker_articles, key=lambda item: item.article_id):
            article = await self.session.scalar(
                select(BrokerArticle).where(
                    BrokerArticle.naver_article_id == detail.article_id
                )
            )
            target = validate_internal_article_href(
                detail.article_url or f"/articles/{detail.article_id}"
            )
            safe_url = urljoin("https://fin.land.naver.com", target)
            if article is None:
                candidate = BrokerArticle(
                    listing_group_id=group.id,
                    naver_article_id=detail.article_id,
                    provider=detail.provider,
                    is_npay=detail.is_npay,
                    article_url=safe_url,
                    first_seen_at=captured_at,
                    last_seen_at=captured_at,
                )
                article, _ = await self._insert_or_requery(
                    candidate,
                    select(BrokerArticle).where(
                        BrokerArticle.naver_article_id == detail.article_id
                    ),
                )
            if article.listing_group_id != group.id:
                raise ArticleGroupConflictError(
                    f"article {detail.article_id} belongs to another listing group"
                )
            article.provider = detail.provider
            article.is_npay = detail.is_npay
            article.article_url = safe_url
            article.last_seen_at = captured_at

            details_json = detail.model_dump(mode="json")
            self.session.add(
                BrokerArticleSnapshot(
                    run_id=run.id,
                    broker_article_id=article.id,
                    details_json=details_json,
                    description_hash=(
                        sha256(detail.description.encode("utf-8")).hexdigest()
                        if detail.description
                        else None
                    ),
                    verified_at=_date_as_datetime(detail.verified_at),
                    captured_at=_aware(detail.captured_at),
                )
            )

    def _store_market_details(
        self, snapshot: ListingSnapshot, details: MarketDetails | None
    ) -> None:
        if details is None:
            return
        serialized = details.model_dump(mode="json")
        location = dict(serialized["location"])
        if serialized["complex"]:
            location["_complex"] = serialized["complex"]
        if serialized["extra_fields"]:
            location["_extra"] = serialized["extra_fields"]
        self.session.add(
            MarketDetailSnapshot(
                listing_snapshot_id=snapshot.id,
                finance_json=serialized["finance"],
                transactions_json=serialized["transactions"],
                costs_json=serialized["costs"],
                maintenance_json=serialized["maintenance"],
                location_json=location,
            )
        )

    async def _add_event(
        self,
        *,
        run: CrawlRun,
        source: TrackedSource,
        apartment: Apartment,
        group_id: UUID,
        event_type: str,
        notification_baseline: bool,
        compare_run_id: UUID | None,
        changed_fields: list[str] | tuple[str, ...] = (),
        before: dict[str, object] | None = None,
        after: dict[str, object] | None = None,
        detected_at: datetime,
    ) -> None:
        event = ChangeEvent(
            run_id=run.id,
            listing_group_id=group_id,
            event_type=event_type,
            changed_fields_json=list(changed_fields),
            before_json=before,
            after_json=after,
            detected_at=detected_at,
        )
        self.session.add(event)
        await self.session.flush()
        await NotificationService(
            self.session, source.owner_user_id
        ).create_from_change_event(
            event=event,
            source=source,
            apartment=apartment,
            baseline=notification_baseline,
            compare_run_id=compare_run_id,
        )

    async def persist(self, run_id: UUID, payload: CrawlPayload) -> PersistenceOutcome:
        captured_at = _aware(payload.captured_at)
        event_count = 0
        async with self.session.begin():
            run = await self.session.get(CrawlRun, run_id, with_for_update=True)
            if run is None:
                raise RunNotFoundError(f"run {run_id} not found")
            if run.status in TERMINAL_RUN_STATUSES:
                return PersistenceOutcome(
                    run_id=run.id,
                    status=run.status,
                    apartment_id=None,
                    listing_count=0,
                    event_count=0,
                    already_terminal=True,
                )
            source = await self.session.get(TrackedSource, run.source_id)
            if source is None:
                raise RunNotFoundError(f"source {run.source_id} not found")
            notification_service = NotificationService(
                self.session, source.owner_user_id
            )
            notification_baseline = not (
                await notification_service.has_completed_baseline(source.id)
            )
            compare_run_id = await notification_service.previous_successful_run_id(
                source.id, run.id
            )
            if (
                source.naver_complex_id is not None
                and source.naver_complex_id != payload.apartment.complex_id
            ):
                raise SourceComplexMismatchError(
                    "하나의 출처 URL이 서로 다른 단지로 해석되었습니다."
                )

            apartment = await self.session.scalar(
                select(Apartment).where(
                    Apartment.naver_complex_id == payload.apartment.complex_id
                )
            )
            if apartment is None:
                incoming_details, _ = normalize_apartment_details(
                    payload.apartment.details  # type: ignore[arg-type]
                )
                candidate = Apartment(
                    naver_complex_id=payload.apartment.complex_id,
                    name=payload.apartment.name,
                    address=payload.apartment.address,
                    details_json=incoming_details,
                    details_updated_at=captured_at if incoming_details else None,
                    created_at=captured_at,
                    updated_at=captured_at,
                )
                apartment, created = await self._insert_or_requery(
                    candidate,
                    select(Apartment).where(
                        Apartment.naver_complex_id
                        == payload.apartment.complex_id
                    ),
                )
            else:
                created = False
                incoming_details, _ = normalize_apartment_details(
                    payload.apartment.details  # type: ignore[arg-type]
                )
            if not created:
                apartment.name = payload.apartment.name
                if payload.apartment.address.strip():
                    apartment.address = payload.apartment.address
                merged_details = _merge_current_apartment_details(
                    apartment.details_json, incoming_details
                )
                if merged_details != apartment.details_json:
                    apartment.details_json = merged_details
                    apartment.details_updated_at = captured_at
                apartment.updated_at = captured_at
            source.naver_complex_id = apartment.naver_complex_id

            existing = await self._existing_records(
                apartment_id=apartment.id,
                complex_id=apartment.naver_complex_id,
                source_id=source.id,
                current_run_id=run.id,
            )
            source_group_ids = await self._source_group_ids(source.id)
            record_by_id = {
                record.identity.listing_group_id: record for record in existing
            }
            candidate_identities = [record.identity for record in existing]

            apartment_json = payload.apartment.model_dump(mode="json")
            apartment_json["name"] = payload.apartment.name
            apartment_json["address"] = payload.apartment.address
            apartment_json["details"] = dict(incoming_details)
            self.session.add(
                ApartmentSnapshot(
                    run_id=run.id,
                    apartment_id=apartment.id,
                    details_json=apartment_json,
                    captured_at=_aware(payload.apartment.captured_at),
                )
            )

            matched_group_ids: set[UUID] = set()
            for listing in payload.listings:
                incoming_identity = _identity_input(apartment.naver_complex_id, listing)
                match = choose_existing_listing(incoming_identity, candidate_identities)
                record = record_by_id.get(match.listing_group_id) if match else None
                if record is None:
                    identity_key = build_identity_key(incoming_identity)
                    candidate = ListingGroup(
                        apartment_id=apartment.id,
                        identity_key=identity_key,
                        first_seen_at=captured_at,
                        last_seen_at=captured_at,
                        state="active",
                        missing_count=0,
                    )
                    group, _ = await self._insert_or_requery(
                        candidate,
                        select(ListingGroup).where(
                            ListingGroup.apartment_id == apartment.id,
                            ListingGroup.identity_key == identity_key,
                        ),
                    )
                    if group.id in matched_group_ids:
                        raise PersistenceError(
                            "한 실행의 여러 매물이 같은 listing_group으로 해석되었습니다."
                        )
                    self.session.add(
                        SourceListingState(
                            source_id=source.id,
                            listing_group_id=group.id,
                            visibility_state="active",
                            missing_count=0,
                            first_seen_at=captured_at,
                            last_seen_at=captured_at,
                            removed_at=None,
                            updated_at=captured_at,
                        )
                    )
                    event_type = "new"
                    previous = None
                else:
                    group = record.group
                    if group.id in matched_group_ids:
                        raise PersistenceError(
                            "한 실행의 여러 매물이 같은 listing_group으로 해석되었습니다."
                        )
                    previous = self._previous_comparable(record)
                    if not record.source_seen:
                        event_type = "new"
                        record.source_seen = True
                        record.source_state = "active"
                        record.source_missing_count = 0
                        record.source_listing_state = SourceListingState(
                            source_id=source.id,
                            listing_group_id=group.id,
                            visibility_state="active",
                            missing_count=0,
                            first_seen_at=captured_at,
                            last_seen_at=captured_at,
                            removed_at=None,
                            updated_at=captured_at,
                        )
                        self.session.add(record.source_listing_state)
                    else:
                        transition = transition_presence(
                            state=record.source_state,
                            missing_count=record.source_missing_count,
                        )
                        event_type = transition.event_type
                        record.source_state = transition.state
                        record.source_missing_count = transition.missing_count
                        state = record.source_listing_state
                        if state is not None:
                            state.visibility_state = transition.state
                            state.missing_count = transition.missing_count
                            state.last_seen_at = captured_at
                            state.removed_at = None
                            state.updated_at = captured_at

                matched_group_ids.add(group.id)
                aggregate = aggregate_broker_articles(listing.broker_articles)
                aggregate = aggregate.model_copy(
                    update={
                        "warnings": sorted(
                            set(aggregate.warnings)
                            | set(listing.warnings)
                            | set(payload.warnings)
                        )
                    }
                )
                current = _incoming_comparable(listing, aggregate)
                if event_type is None and previous is not None:
                    comparison = compare_listings(
                        previous,
                        current,
                        compare_detail_fields=(
                            getattr(record, "latest_collect_broker_details", True)
                            and _collect_broker_details_enabled(run)
                        ),
                    )
                    event_type = comparison.event_type
                else:
                    comparison = None

                snapshot = ListingSnapshot(
                    run_id=run.id,
                    listing_group_id=group.id,
                    trade_type=listing.trade_type,
                    price=listing.price,
                    deposit=listing.deposit,
                    monthly_rent=listing.monthly_rent,
                    building=listing.building,
                    floor=listing.floor,
                    direction=listing.direction,
                    supply_area=listing.supply_area,
                    exclusive_area=listing.exclusive_area,
                    status=event_type or "active",
                    captured_at=_aware(listing.captured_at),
                )
                self.session.add(snapshot)
                await self.session.flush()
                self.session.add(
                    ListingAggregate(
                        listing_snapshot_id=snapshot.id,
                        option_tags_json=aggregate.option_tags,
                        move_in_summary=aggregate.move_in_summary,
                        management_fee_summary=aggregate.management_fee_summary,
                        room_bath_summary=aggregate.room_bath_summary,
                        loan_summary=aggregate.loan_summary,
                        source_count=aggregate.source_count,
                        warnings_json=aggregate.warnings,
                    )
                )
                await self._store_brokers(
                    run=run,
                    group=group,
                    listing=listing,
                    captured_at=captured_at,
                )
                self._store_market_details(snapshot, listing.market_details)

                if event_type in {"new", "restored"}:
                    await self._add_event(
                        run=run,
                        source=source,
                        apartment=apartment,
                        group_id=group.id,
                        event_type=event_type,
                        notification_baseline=notification_baseline,
                        compare_run_id=compare_run_id,
                        before=_comparable_json(previous) if previous else None,
                        after=_comparable_json(current),
                        detected_at=captured_at,
                    )
                    event_count += 1
                elif comparison is not None and comparison.event_type == "changed":
                    await self._add_event(
                        run=run,
                        source=source,
                        apartment=apartment,
                        group_id=group.id,
                        event_type="changed",
                        notification_baseline=notification_baseline,
                        compare_run_id=compare_run_id,
                        changed_fields=comparison.changed_fields,
                        before=comparison.before,
                        after=comparison.after,
                        detected_at=captured_at,
                    )
                    event_count += 1

            record_by_group_id = {record.group.id: record for record in existing}
            for group_id in sorted(source_group_ids - matched_group_ids, key=str):
                record = record_by_group_id.get(group_id)
                if record is None:
                    continue
                group = record.group
                before_state = record.source_state
                before_count = record.source_missing_count
                transition = transition_absence(
                    state=record.source_state,
                    missing_count=record.source_missing_count,
                    run_status=payload.status,
                )
                if (
                    transition.state == before_state
                    and transition.missing_count == before_count
                ):
                    continue
                record.source_state = transition.state
                record.source_missing_count = transition.missing_count
                state = record.source_listing_state
                if state is None:
                    continue
                state.visibility_state = transition.state
                state.missing_count = transition.missing_count
                state.removed_at = (
                    captured_at if transition.state == "removed" else None
                )
                state.updated_at = captured_at
                if transition.event_type:
                    await self._add_event(
                        run=run,
                        source=source,
                        apartment=apartment,
                        group_id=group.id,
                        event_type=transition.event_type,
                        notification_baseline=notification_baseline,
                        compare_run_id=compare_run_id,
                        before={"state": before_state, "missingCount": before_count},
                        after={
                            "state": transition.state,
                            "missingCount": transition.missing_count,
                        },
                        detected_at=captured_at,
                    )
                    event_count += 1

            run.status = payload.status
            run.stage = "save"
            run.progress = 100
            run.finished_at = captured_at
            run.error_code = None
            run.selector_version = SELECTOR_VERSION

        return PersistenceOutcome(
            run_id=run.id,
            status=run.status,
            apartment_id=apartment.id,
            listing_count=len(payload.listings),
            event_count=event_count,
        )


async def mark_run_terminal(
    session: AsyncSession,
    *,
    run_id: UUID,
    status: str,
    error_code: str,
    stage: str,
) -> None:
    if status not in {"failed", "blocked"}:
        raise ValueError("terminal failure status must be failed or blocked")
    async with session.begin():
        run = await session.get(CrawlRun, run_id, with_for_update=True)
        if run is None or run.status in TERMINAL_RUN_STATUSES:
            return
        run.status = status
        run.stage = stage
        run.error_code = error_code
        run.finished_at = datetime.now(timezone.utc)
        run.selector_version = SELECTOR_VERSION
