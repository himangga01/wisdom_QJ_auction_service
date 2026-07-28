from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from hashlib import sha256
from urllib.parse import urljoin
from uuid import UUID

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crawler.navigation import validate_internal_article_href
from app.crawler.selectors import SELECTOR_VERSION
from app.crawler.types import CrawlPayload, ListingDetail, MarketDetails
from app.domain.aggregator import AggregatedListingInfo, aggregate_broker_articles
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
    TrackedSource,
)


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
    latest_collect_broker_details: bool = True


TERMINAL_RUN_STATUSES = {"completed", "partial", "failed", "blocked", "cancelled"}


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


def _comparable_json(value: ComparableListing) -> dict[str, object]:
    return {
        "price": value.price,
        "deposit": value.deposit,
        "monthlyRent": value.monthly_rent,
        "managementFee": value.management_fee,
        "moveInDate": value.move_in_date,
        "floor": value.floor,
        "direction": value.direction,
        "optionTags": sorted(value.option_tags),
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
        management_fee=aggregate.management_fee_summary,
        move_in_date=aggregate.move_in_summary,
        floor=listing.floor,
        direction=listing.direction,
        option_tags=tuple(sorted(aggregate.option_tags)),
        article_ids=listing.article_ids,
    )


class PersistenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
            select(distinct(ListingSnapshot.listing_group_id))
            .join(CrawlRun, CrawlRun.id == ListingSnapshot.run_id)
            .where(CrawlRun.source_id == source_id, CrawlRun.status == "completed")
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
            management_fee=(aggregate.management_fee_summary if aggregate else ""),
            move_in_date=(aggregate.move_in_summary if aggregate else ""),
            floor=snapshot.floor,
            direction=snapshot.direction,
            option_tags=tuple(sorted(aggregate.option_tags_json if aggregate else [])),
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
                article = BrokerArticle(
                    listing_group_id=group.id,
                    naver_article_id=detail.article_id,
                    provider=detail.provider,
                    is_npay=detail.is_npay,
                    article_url=safe_url,
                    first_seen_at=captured_at,
                    last_seen_at=captured_at,
                )
                self.session.add(article)
                await self.session.flush()
            elif article.listing_group_id != group.id:
                raise ArticleGroupConflictError(
                    f"article {detail.article_id} belongs to another listing group"
                )
            else:
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

    def _add_event(
        self,
        *,
        run_id: UUID,
        group_id: UUID,
        event_type: str,
        changed_fields: list[str] | tuple[str, ...] = (),
        before: dict[str, object] | None = None,
        after: dict[str, object] | None = None,
        detected_at: datetime,
    ) -> None:
        self.session.add(
            ChangeEvent(
                run_id=run_id,
                listing_group_id=group_id,
                event_type=event_type,
                changed_fields_json=list(changed_fields),
                before_json=before,
                after_json=after,
                detected_at=detected_at,
            )
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
                apartment = Apartment(
                    naver_complex_id=payload.apartment.complex_id,
                    name=payload.apartment.name,
                    address=payload.apartment.address,
                    created_at=captured_at,
                    updated_at=captured_at,
                )
                self.session.add(apartment)
                await self.session.flush()
            else:
                apartment.name = payload.apartment.name
                apartment.address = payload.apartment.address
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
                    group = ListingGroup(
                        apartment_id=apartment.id,
                        identity_key=build_identity_key(incoming_identity),
                        first_seen_at=captured_at,
                        last_seen_at=captured_at,
                        state="active",
                        missing_count=0,
                    )
                    self.session.add(group)
                    await self.session.flush()
                    event_type = "new"
                    previous = None
                else:
                    group = record.group
                    if group.id in matched_group_ids:
                        raise PersistenceError(
                            "한 실행의 여러 매물이 같은 listing_group으로 해석되었습니다."
                        )
                    previous = self._previous_comparable(record)
                    transition = transition_presence(
                        state=group.state, missing_count=group.missing_count
                    )
                    event_type = transition.event_type
                    group.state = transition.state
                    group.missing_count = transition.missing_count
                    group.last_seen_at = captured_at

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
                    self._add_event(
                        run_id=run.id,
                        group_id=group.id,
                        event_type=event_type,
                        before=_comparable_json(previous) if previous else None,
                        after=_comparable_json(current),
                        detected_at=captured_at,
                    )
                    event_count += 1
                elif comparison is not None and comparison.event_type == "changed":
                    self._add_event(
                        run_id=run.id,
                        group_id=group.id,
                        event_type="changed",
                        changed_fields=comparison.changed_fields,
                        before=comparison.before,
                        after=comparison.after,
                        detected_at=captured_at,
                    )
                    event_count += 1

            record_group_by_id = {record.group.id: record.group for record in existing}
            for group_id in sorted(source_group_ids - matched_group_ids, key=str):
                group = record_group_by_id.get(group_id)
                if group is None:
                    continue
                before_state = group.state
                before_count = group.missing_count
                transition = transition_absence(
                    state=group.state,
                    missing_count=group.missing_count,
                    run_status=payload.status,
                )
                group.state = transition.state
                group.missing_count = transition.missing_count
                if transition.event_type:
                    self._add_event(
                        run_id=run.id,
                        group_id=group.id,
                        event_type=transition.event_type,
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
