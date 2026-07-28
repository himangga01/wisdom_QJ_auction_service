from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import (
    Apartment,
    ApartmentSnapshot,
    BrokerArticle,
    BrokerArticleSnapshot,
    ChangeEvent,
    CrawlRun,
    ListingAggregate as ListingAggregateModel,
    ListingGroup,
    ListingSnapshot,
    MarketDetailSnapshot,
    TrackedSource,
)
from app.schemas.apartment import (
    ApartmentDetail,
    ApartmentHistoryPoint,
    ApartmentPage,
    ApartmentRun,
    ApartmentSummary,
)
from app.schemas.dashboard import DashboardResponse
from app.schemas.listing import (
    BrokerRegistration,
    ListingAggregate,
    ListingAbsence,
    ListingDetail,
    ListingPage,
    ListingSummary,
    MarketDetails,
)

RESULT_STATUSES = ("completed", "partial")
SEOUL = ZoneInfo("Asia/Seoul")


class QueryNotFoundError(LookupError):
    code = "dataset_not_found"


ListingRow = tuple[
    ListingSnapshot,
    ListingGroup,
    ListingAggregateModel | None,
    int | None,
    datetime,
]


@dataclass(frozen=True, slots=True)
class _AbsenceRecord:
    status: str
    detected_at: datetime
    removed_at: datetime | None
    row: ListingRow


def seoul_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(SEOUL).isoformat()


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


def camelize_json(value: Any, *, source_key: str | None = None) -> Any:
    """Convert persisted crawler JSON to the API's camelCase/Seoul contract."""
    if isinstance(value, dict):
        return {
            _camel(str(key)): camelize_json(item, source_key=str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [camelize_json(item, source_key=source_key) for item in value]
    if isinstance(value, datetime):
        return seoul_iso(value)
    if isinstance(value, Decimal):
        return float(value)
    if (
        isinstance(value, str)
        and source_key is not None
        and source_key.endswith("_at")
        and "T" in value
    ):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        return seoul_iso(parsed)
    return value


class QueryService:
    def __init__(self, session: AsyncSession, actor_user_id: UUID) -> None:
        self.session = session
        self.actor_user_id = actor_user_id

    def _ranked_apartment_snapshots(self):
        ordering = (
            func.coalesce(CrawlRun.finished_at, ApartmentSnapshot.captured_at).desc(),
            ApartmentSnapshot.captured_at.desc(),
        )
        return (
            select(
                ApartmentSnapshot.id.label("snapshot_id"),
                func.row_number()
                .over(
                    partition_by=(
                        CrawlRun.source_id,
                        ApartmentSnapshot.apartment_id,
                    ),
                    order_by=ordering,
                )
                .label("snapshot_rank"),
            )
            .join(CrawlRun, CrawlRun.id == ApartmentSnapshot.run_id)
            .join(TrackedSource, TrackedSource.id == CrawlRun.source_id)
            .where(
                CrawlRun.status.in_(RESULT_STATUSES),
                TrackedSource.owner_user_id == self.actor_user_id,
            )
            .subquery()
        )

    def _latest_apartment_statement(self) -> Select:
        ranked = self._ranked_apartment_snapshots()
        return (
            select(Apartment, ApartmentSnapshot, CrawlRun, TrackedSource)
            .select_from(ranked)
            .join(ApartmentSnapshot, ApartmentSnapshot.id == ranked.c.snapshot_id)
            .join(Apartment, Apartment.id == ApartmentSnapshot.apartment_id)
            .join(CrawlRun, CrawlRun.id == ApartmentSnapshot.run_id)
            .join(TrackedSource, TrackedSource.id == CrawlRun.source_id)
            .where(
                ranked.c.snapshot_rank == 1,
                TrackedSource.owner_user_id == self.actor_user_id,
            )
        )

    async def _latest_result(
        self,
        *,
        complex_id: str | None = None,
        source_id: UUID | None = None,
        run_id: UUID | None = None,
    ) -> tuple[Apartment, ApartmentSnapshot, CrawlRun, TrackedSource]:
        statement = (
            select(Apartment, ApartmentSnapshot, CrawlRun, TrackedSource)
            .select_from(ApartmentSnapshot)
            .join(Apartment, Apartment.id == ApartmentSnapshot.apartment_id)
            .join(CrawlRun, CrawlRun.id == ApartmentSnapshot.run_id)
            .join(TrackedSource, TrackedSource.id == CrawlRun.source_id)
            .where(
                CrawlRun.status.in_(RESULT_STATUSES),
                TrackedSource.owner_user_id == self.actor_user_id,
            )
        )
        if complex_id is not None:
            statement = statement.where(Apartment.naver_complex_id == complex_id)
        if source_id is not None:
            statement = statement.where(TrackedSource.id == source_id)
        if run_id is not None:
            statement = statement.where(CrawlRun.id == run_id)
        statement = statement.order_by(
            func.coalesce(CrawlRun.finished_at, ApartmentSnapshot.captured_at).desc(),
            ApartmentSnapshot.captured_at.desc(),
        ).limit(1)
        row = (await self.session.execute(statement)).first()
        if row is None:
            raise QueryNotFoundError("저장된 조사 결과를 찾을 수 없습니다.")
        return row[0], row[1], row[2], row[3]

    async def _listing_counts(self, run_ids: list[UUID]) -> dict[UUID, int]:
        if not run_ids:
            return {}
        rows = (
            await self.session.execute(
                select(ListingSnapshot.run_id, func.count(ListingSnapshot.id))
                .where(ListingSnapshot.run_id.in_(run_ids))
                .group_by(ListingSnapshot.run_id)
            )
        ).all()
        return {run_id: int(count) for run_id, count in rows}

    @staticmethod
    def _apartment_summary(
        row: tuple[Apartment, ApartmentSnapshot, CrawlRun, TrackedSource],
        listing_count: int,
    ) -> ApartmentSummary:
        apartment, snapshot, run, source = row
        captured = snapshot.details_json
        details = captured.get("details", captured)
        return ApartmentSummary(
            apartment_id=apartment.id,
            complex_id=apartment.naver_complex_id,
            complex_name=str(
                (captured.get("name") or "")
                if "name" in captured
                else apartment.name
            ),
            address=str(
                (captured.get("address") or "")
                if "address" in captured
                else ""
            ),
            source_id=source.id,
            source_url=source.normalized_url,
            latest_run_id=run.id,
            latest_status=run.status,
            collected_at=seoul_iso(snapshot.captured_at),
            details=camelize_json(details),
            listing_count=listing_count,
        )

    async def apartments(
        self, *, query: str | None, page: int, page_size: int
    ) -> ApartmentPage:
        statement = self._latest_apartment_statement()
        ranked = self._ranked_apartment_snapshots()
        count_statement = (
            select(func.count(Apartment.id))
            .select_from(ranked)
            .join(ApartmentSnapshot, ApartmentSnapshot.id == ranked.c.snapshot_id)
            .join(Apartment, Apartment.id == ApartmentSnapshot.apartment_id)
            .where(ranked.c.snapshot_rank == 1)
        )
        normalized_query = (query or "").strip()
        if normalized_query:
            pattern = f"%{normalized_query}%"
            snapshot_name = ApartmentSnapshot.details_json["name"].as_string()
            snapshot_address = ApartmentSnapshot.details_json[
                "address"
            ].as_string()
            predicate = or_(
                snapshot_name.ilike(pattern),
                snapshot_address.ilike(pattern),
                Apartment.naver_complex_id.ilike(pattern),
            )
            statement = statement.where(predicate)
            count_statement = count_statement.where(predicate)
        statement = statement.order_by(
            func.coalesce(CrawlRun.finished_at, ApartmentSnapshot.captured_at).desc(),
            ApartmentSnapshot.captured_at.desc(),
            Apartment.naver_complex_id.asc(),
        ).offset((page - 1) * page_size).limit(page_size)
        rows = (await self.session.execute(statement)).all()
        total = int((await self.session.scalar(count_statement)) or 0)
        counts = await self._listing_counts([row[2].id for row in rows])
        return ApartmentPage(
            items=[self._apartment_summary(row, counts.get(row[2].id, 0)) for row in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    async def history(
        self, complex_id: str, *, source_id: UUID
    ) -> list[ApartmentHistoryPoint]:
        await self._latest_result(
            complex_id=complex_id,
            source_id=source_id,
        )
        apartment = await self.session.scalar(
            select(Apartment).where(Apartment.naver_complex_id == complex_id)
        )
        if apartment is None:
            raise QueryNotFoundError("아파트를 찾을 수 없습니다.")
        if source_id is None:
            _, _, _, source = await self._latest_result(complex_id=complex_id)
            source_id = source.id
        run_rows = (
            await self.session.execute(
                select(CrawlRun.id, CrawlRun.status, ApartmentSnapshot.captured_at)
                .join(ApartmentSnapshot, ApartmentSnapshot.run_id == CrawlRun.id)
                .where(
                    ApartmentSnapshot.apartment_id == apartment.id,
                    CrawlRun.source_id == source_id,
                    CrawlRun.status.in_(RESULT_STATUSES),
                )
                .order_by(ApartmentSnapshot.captured_at.asc())
            )
        ).all()
        run_ids = [row[0] for row in run_rows]
        listing_counts: dict[UUID, dict[str, int]] = {run_id: {} for run_id in run_ids}
        if run_ids:
            rows = (
                await self.session.execute(
                    select(
                        ListingSnapshot.run_id,
                        ListingSnapshot.trade_type,
                        func.count(ListingSnapshot.id),
                    )
                    .join(ListingGroup, ListingGroup.id == ListingSnapshot.listing_group_id)
                    .where(
                        ListingSnapshot.run_id.in_(run_ids),
                        ListingGroup.apartment_id == apartment.id,
                    )
                    .group_by(ListingSnapshot.run_id, ListingSnapshot.trade_type)
                )
            ).all()
            for item_run_id, trade_type, count in rows:
                listing_counts[item_run_id][trade_type] = int(count)
        event_counts: dict[UUID, dict[str, int]] = {run_id: {} for run_id in run_ids}
        if run_ids:
            rows = (
                await self.session.execute(
                    select(ChangeEvent.run_id, ChangeEvent.event_type, func.count(ChangeEvent.id))
                    .where(ChangeEvent.run_id.in_(run_ids))
                    .group_by(ChangeEvent.run_id, ChangeEvent.event_type)
                )
            ).all()
            for item_run_id, event_type, count in rows:
                event_counts[item_run_id][event_type] = int(count)
        return [
            ApartmentHistoryPoint(
                run_id=item_run_id,
                status=run_status,
                collected_at=seoul_iso(captured_at),
                sale_count=listing_counts[item_run_id].get("sale", 0),
                jeonse_count=listing_counts[item_run_id].get("jeonse", 0),
                monthly_count=listing_counts[item_run_id].get("monthly", 0),
                added_count=(
                    event_counts[item_run_id].get("new", 0)
                    + event_counts[item_run_id].get("restored", 0)
                ),
                removed_count=event_counts[item_run_id].get("removed", 0),
            )
            for item_run_id, run_status, captured_at in run_rows
        ]

    async def apartment(
        self,
        complex_id: str,
        *,
        run_id: UUID | None = None,
        source_id: UUID,
    ) -> ApartmentDetail:
        row = await self._latest_result(
            complex_id=complex_id,
            run_id=run_id,
            source_id=source_id,
        )
        history = await self.history(complex_id, source_id=row[3].id)
        listing_count = (await self._listing_counts([row[2].id])).get(row[2].id, 0)
        summary = self._apartment_summary(row, listing_count)
        return ApartmentDetail(
            **summary.model_dump(),
            available_runs=[
                ApartmentRun(
                    run_id=point.run_id,
                    status=point.status,
                    collected_at=point.collected_at,
                )
                for point in history
            ],
            history=history,
        )

    async def _source_run_ids_through(self, selected_run: CrawlRun) -> list[UUID]:
        ordered_run_ids = list(
            (
                await self.session.scalars(
                    select(CrawlRun.id)
                    .where(
                        CrawlRun.source_id == selected_run.source_id,
                        CrawlRun.status.in_(RESULT_STATUSES),
                    )
                    .order_by(CrawlRun.created_at.asc(), CrawlRun.id.asc())
                )
            ).all()
        )
        run_ids: list[UUID] = []
        for item_run_id in ordered_run_ids:
            run_ids.append(item_run_id)
            if item_run_id == selected_run.id:
                break
        if selected_run.id not in run_ids:
            run_ids = [selected_run.id]
        return run_ids

    async def _listing_rows_for_run(
        self, *, apartment_id: UUID, selected_run: CrawlRun
    ) -> list[ListingRow]:
        previous = aliased(ListingSnapshot)
        previous_run = aliased(CrawlRun)
        first_seen = aliased(ListingSnapshot)
        first_seen_run = aliased(CrawlRun)
        previous_price = (
            select(previous.price)
            .join(previous_run, previous_run.id == previous.run_id)
            .where(
                previous.listing_group_id == ListingSnapshot.listing_group_id,
                previous_run.source_id == selected_run.source_id,
                previous_run.status.in_(RESULT_STATUSES),
                previous.captured_at < ListingSnapshot.captured_at,
            )
            .order_by(previous.captured_at.desc())
            .limit(1)
            .correlate(ListingSnapshot)
            .scalar_subquery()
        )
        discovered_at = (
            select(func.min(first_seen.captured_at))
            .join(first_seen_run, first_seen_run.id == first_seen.run_id)
            .where(
                first_seen.listing_group_id == ListingSnapshot.listing_group_id,
                first_seen_run.source_id == selected_run.source_id,
                first_seen_run.status.in_(RESULT_STATUSES),
                first_seen.captured_at <= ListingSnapshot.captured_at,
            )
            .correlate(ListingSnapshot)
            .scalar_subquery()
        )
        statement = (
            select(
                ListingSnapshot,
                ListingGroup,
                ListingAggregateModel,
                previous_price.label("previous_price"),
                discovered_at.label("discovered_at"),
            )
            .join(ListingGroup, ListingGroup.id == ListingSnapshot.listing_group_id)
            .outerjoin(
                ListingAggregateModel,
                ListingAggregateModel.listing_snapshot_id == ListingSnapshot.id,
            )
            .where(
                ListingSnapshot.run_id == selected_run.id,
                ListingGroup.apartment_id == apartment_id,
            )
            .order_by(
                ListingSnapshot.trade_type.asc(),
                ListingSnapshot.price.asc().nullslast(),
                ListingSnapshot.building.asc().nullslast(),
            )
        )
        return list((await self.session.execute(statement)).all())

    async def _last_listing_rows_for_groups(
        self,
        *,
        apartment_id: UUID,
        run_ids: list[UUID],
        group_ids: set[UUID],
    ) -> list[ListingRow]:
        if not run_ids or not group_ids:
            return []
        ranked = (
            select(
                ListingSnapshot.id.label("snapshot_id"),
                func.row_number()
                .over(
                    partition_by=ListingSnapshot.listing_group_id,
                    order_by=ListingSnapshot.captured_at.desc(),
                )
                .label("snapshot_rank"),
            )
            .join(ListingGroup, ListingGroup.id == ListingSnapshot.listing_group_id)
            .where(
                ListingSnapshot.run_id.in_(run_ids),
                ListingSnapshot.listing_group_id.in_(group_ids),
                ListingGroup.apartment_id == apartment_id,
            )
            .subquery()
        )
        previous = aliased(ListingSnapshot)
        first_seen = aliased(ListingSnapshot)
        previous_price = (
            select(previous.price)
            .where(
                previous.listing_group_id == ListingSnapshot.listing_group_id,
                previous.run_id.in_(run_ids),
                previous.captured_at < ListingSnapshot.captured_at,
            )
            .order_by(previous.captured_at.desc())
            .limit(1)
            .correlate(ListingSnapshot)
            .scalar_subquery()
        )
        discovered_at = (
            select(func.min(first_seen.captured_at))
            .where(
                first_seen.listing_group_id == ListingSnapshot.listing_group_id,
                first_seen.run_id.in_(run_ids),
                first_seen.captured_at <= ListingSnapshot.captured_at,
            )
            .correlate(ListingSnapshot)
            .scalar_subquery()
        )
        statement = (
            select(
                ListingSnapshot,
                ListingGroup,
                ListingAggregateModel,
                previous_price.label("previous_price"),
                discovered_at.label("discovered_at"),
            )
            .select_from(ranked)
            .join(ListingSnapshot, ListingSnapshot.id == ranked.c.snapshot_id)
            .join(ListingGroup, ListingGroup.id == ListingSnapshot.listing_group_id)
            .outerjoin(
                ListingAggregateModel,
                ListingAggregateModel.listing_snapshot_id == ListingSnapshot.id,
            )
            .where(ranked.c.snapshot_rank == 1)
            .order_by(
                ListingSnapshot.trade_type.asc(),
                ListingSnapshot.price.asc().nullslast(),
                ListingSnapshot.building.asc().nullslast(),
            )
        )
        return list((await self.session.execute(statement)).all())

    async def _absence_states_as_of_run(
        self, *, apartment_id: UUID, selected_run: CrawlRun
    ) -> list[_AbsenceRecord]:
        run_ids = await self._source_run_ids_through(selected_run)
        event_rows = (
            await self.session.execute(
                select(
                    ChangeEvent.listing_group_id,
                    ChangeEvent.event_type,
                    ChangeEvent.detected_at,
                )
                .join(
                    ListingGroup,
                    ListingGroup.id == ChangeEvent.listing_group_id,
                )
                .where(
                    ChangeEvent.run_id.in_(run_ids),
                    ListingGroup.apartment_id == apartment_id,
                )
                .order_by(ChangeEvent.detected_at.asc(), ChangeEvent.id.asc())
            )
        ).all()
        states: dict[UUID, tuple[str, datetime, datetime | None]] = {}
        for group_id, event_type, detected_at in event_rows:
            if event_type == "missing":
                states[group_id] = ("missing", detected_at, None)
            elif event_type == "removed":
                states[group_id] = ("removed", detected_at, detected_at)
            elif event_type in {"new", "changed", "restored"}:
                states.pop(group_id, None)

        actual_group_ids = set(
            (
                await self.session.scalars(
                    select(ListingSnapshot.listing_group_id)
                    .join(
                        ListingGroup,
                        ListingGroup.id == ListingSnapshot.listing_group_id,
                    )
                    .where(
                        ListingSnapshot.run_id == selected_run.id,
                        ListingGroup.apartment_id == apartment_id,
                    )
                )
            ).all()
        )
        for group_id in actual_group_ids:
            states.pop(group_id, None)
        rows = await self._last_listing_rows_for_groups(
            apartment_id=apartment_id,
            run_ids=run_ids,
            group_ids=set(states),
        )
        return [
            _AbsenceRecord(
                status=states[row[1].id][0],
                detected_at=states[row[1].id][1],
                removed_at=states[row[1].id][2],
                row=row,
            )
            for row in rows
            if row[1].id in states
        ]

    async def _event_statuses(self, run_id: UUID) -> dict[UUID, str]:
        rows = (
            await self.session.execute(
                select(ChangeEvent.listing_group_id, ChangeEvent.event_type).where(
                    ChangeEvent.run_id == run_id
                )
            )
        ).all()
        return {group_id: event_type for group_id, event_type in rows}

    @staticmethod
    def _aggregate(value: ListingAggregateModel | None) -> ListingAggregate:
        if value is None:
            return ListingAggregate()
        return ListingAggregate(
            option_tags=value.option_tags_json,
            move_in_summary=value.move_in_summary,
            management_fee_summary=value.management_fee_summary,
            room_bath_summary=value.room_bath_summary,
            loan_summary=value.loan_summary,
            source_count=value.source_count,
            warnings=value.warnings_json,
        )

    @classmethod
    def _listing_summary(
        cls,
        row: ListingRow,
        *,
        selected_run_id: UUID,
        event_status: str | None,
        removed_at: datetime | None = None,
    ) -> ListingSummary:
        snapshot, group, aggregate, previous_price, discovered_at = row
        if event_status == "restored":
            status = "active"
        elif event_status in {"new", "changed", "missing", "removed"}:
            status = event_status
        elif snapshot.run_id == selected_run_id and snapshot.status in {
            "new",
            "changed",
            "removed",
        }:
            status = snapshot.status
        else:
            status = "active"
        return ListingSummary(
            group_id=group.id,
            run_id=selected_run_id,
            trade_type=snapshot.trade_type,
            price=snapshot.price,
            deposit=snapshot.deposit,
            monthly_rent=snapshot.monthly_rent,
            previous_price=previous_price,
            building=snapshot.building,
            floor=snapshot.floor,
            direction=snapshot.direction,
            supply_area_m2=(float(snapshot.supply_area) if snapshot.supply_area is not None else None),
            exclusive_area_m2=(
                float(snapshot.exclusive_area) if snapshot.exclusive_area is not None else None
            ),
            status=status,
            discovered_at=seoul_iso(discovered_at),
            last_seen_at=seoul_iso(snapshot.captured_at),
            removed_at=seoul_iso(removed_at) if removed_at else None,
            captured_at=seoul_iso(snapshot.captured_at),
            aggregate=cls._aggregate(aggregate),
        )

    async def listings(
        self,
        complex_id: str,
        *,
        source_id: UUID,
        run_id: UUID | None,
        trade_type: str | None,
        status: str | None,
    ) -> ListingPage:
        apartment, apartment_snapshot, run, _ = await self._latest_result(
            complex_id=complex_id, source_id=source_id, run_id=run_id
        )
        rows = await self._listing_rows_for_run(
            apartment_id=apartment.id, selected_run=run
        )
        event_statuses = await self._event_statuses(run.id)
        items = [
            self._listing_summary(
                row,
                selected_run_id=run.id,
                event_status=event_statuses.get(row[1].id),
            )
            for row in rows
        ]
        absence_records = await self._absence_states_as_of_run(
            apartment_id=apartment.id,
            selected_run=run,
        )
        absent_items = [
            ListingAbsence(
                group_id=record.row[1].id,
                status=record.status,
                last_snapshot=self._listing_summary(
                    record.row,
                    selected_run_id=record.row[0].run_id,
                    event_status=None,
                ),
                detected_at=seoul_iso(record.detected_at),
                removed_at=(
                    seoul_iso(record.removed_at) if record.removed_at else None
                ),
            )
            for record in absence_records
        ]
        if trade_type:
            items = [item for item in items if item.trade_type == trade_type]
            absent_items = [
                item
                for item in absent_items
                if item.last_snapshot.trade_type == trade_type
            ]
        if status:
            items = [item for item in items if item.status == status]
            absent_items = (
                [item for item in absent_items if item.status == status]
                if status in {"missing", "removed"}
                else []
            )
        return ListingPage(
            complex_id=apartment.naver_complex_id,
            run_id=run.id,
            collected_at=seoul_iso(apartment_snapshot.captured_at),
            items=items,
            absent_items=absent_items,
        )

    async def _broker_registrations_for_run(
        self, *, group_id: UUID, run_id: UUID
    ) -> list[BrokerRegistration]:
        selected_run = await self.session.scalar(
            select(CrawlRun)
            .join(TrackedSource, TrackedSource.id == CrawlRun.source_id)
            .where(
                CrawlRun.id == run_id,
                TrackedSource.owner_user_id == self.actor_user_id,
            )
        )
        if selected_run is None:
            raise QueryNotFoundError("조사 회차를 찾을 수 없습니다.")
        rows = (
            await self.session.execute(
                select(BrokerArticle, BrokerArticleSnapshot)
                .select_from(BrokerArticleSnapshot)
                .join(
                    BrokerArticle,
                    BrokerArticle.id == BrokerArticleSnapshot.broker_article_id,
                )
                .join(CrawlRun, CrawlRun.id == BrokerArticleSnapshot.run_id)
                .where(
                    BrokerArticle.listing_group_id == group_id,
                    BrokerArticleSnapshot.run_id == run_id,
                    CrawlRun.source_id == selected_run.source_id,
                )
                .order_by(BrokerArticle.provider.asc(), BrokerArticle.naver_article_id.asc())
            )
        ).all()
        article_ids = [article.id for article, _ in rows]
        first_seen_by_article: dict[UUID, datetime] = {}
        if article_ids:
            first_seen_rows = (
                await self.session.execute(
                    select(
                        BrokerArticleSnapshot.broker_article_id,
                        func.min(BrokerArticleSnapshot.captured_at),
                    )
                    .join(
                        CrawlRun,
                        CrawlRun.id == BrokerArticleSnapshot.run_id,
                    )
                    .where(
                        BrokerArticleSnapshot.broker_article_id.in_(article_ids),
                        CrawlRun.source_id == selected_run.source_id,
                        CrawlRun.status.in_(RESULT_STATUSES),
                        CrawlRun.created_at <= selected_run.created_at,
                    )
                    .group_by(BrokerArticleSnapshot.broker_article_id)
                )
            ).all()
            first_seen_by_article = {
                article_id: first_seen_at
                for article_id, first_seen_at in first_seen_rows
            }
        result: list[BrokerRegistration] = []
        for article, snapshot in rows:
            details = snapshot.details_json
            detail_collected = details.get("detail_collected", True)
            provider = (
                str(details.get("provider") or "")
                if "provider" in details
                else article.provider
            )
            is_npay = (
                bool(details.get("is_npay"))
                if "is_npay" in details
                else article.is_npay
            )
            snapshot_article_url = (
                details.get("article_url")
                if "article_url" in details
                else article.article_url
            )
            article_url = urljoin(
                "https://fin.land.naver.com",
                str(snapshot_article_url or f"/articles/{article.naver_article_id}"),
            )
            realtor = details.get("realtor") or {}
            realtor_payload = None
            if realtor:
                phone = realtor.get("phone")
                realtor_payload = {
                    "officeName": realtor.get("name"),
                    "representativeName": realtor.get("representative"),
                    "phones": [phone] if phone else [],
                    "address": realtor.get("address"),
                    "registrationNumber": realtor.get("registration_number"),
                }
            result.append(
                BrokerRegistration(
                    article_id=article.naver_article_id,
                    realtor_name=realtor.get("name") or "",
                    provider=provider,
                    is_npay=is_npay,
                    detail_collected=detail_collected,
                    article_url=article_url,
                    advertised_price=details.get("advertised_price"),
                    price_per_3_point_3_m2=details.get("price_per_3_3m2"),
                    management_fee=details.get("management_fee"),
                    loan_description=details.get("loan_description"),
                    supply_area_m2=details.get("supply_area_m2"),
                    exclusive_area_m2=details.get("exclusive_area_m2"),
                    exclusive_rate=details.get("exclusive_rate"),
                    floor=details.get("floor"),
                    room_count=details.get("room_count"),
                    bathroom_count=details.get("bathroom_count"),
                    direction=details.get("direction"),
                    structure=details.get("structure"),
                    move_in_date=details.get("move_in_date"),
                    description=details.get("description") or "",
                    option_tags=details.get("option_tags") or [],
                    first_published_at=details.get("first_published_at"),
                    realtor=realtor_payload,
                    extra_fields=camelize_json(details.get("extra_fields") or {}),
                    data_warnings=details.get("warnings") or [],
                    market_details=(
                        self._snapshot_market_details(details.get("market_details"))
                        if detail_collected
                        else None
                    ),
                    first_seen_at=seoul_iso(
                        first_seen_by_article.get(article.id, snapshot.captured_at)
                    ),
                    last_seen_at=seoul_iso(snapshot.captured_at),
                    captured_at=seoul_iso(snapshot.captured_at),
                    verified_at=(
                        details.get("verified_at")
                        or (seoul_iso(snapshot.verified_at) if snapshot.verified_at else None)
                    ),
                )
            )
        return result

    @staticmethod
    def _snapshot_market_details(
        value: dict[str, Any] | None,
    ) -> MarketDetails | None:
        if not value:
            return None
        return MarketDetails(
            finance=camelize_json(value.get("finance") or {}),
            transactions=camelize_json(value.get("transactions") or {}),
            costs=camelize_json(value.get("costs") or {}),
            maintenance=camelize_json(value.get("maintenance") or {}),
            complex=camelize_json(value.get("complex") or {}),
            location=camelize_json(value.get("location") or {}),
            extra_fields=camelize_json(value.get("extra_fields") or {}),
        )

    @staticmethod
    def _market_details(value: MarketDetailSnapshot | None) -> MarketDetails | None:
        if value is None:
            return None
        location = dict(value.location_json)
        complex_detail = location.pop("_complex", {})
        extra_fields = location.pop("_extra", {})
        return MarketDetails(
            finance=camelize_json(value.finance_json),
            transactions=camelize_json(value.transactions_json),
            costs=camelize_json(value.costs_json),
            maintenance=camelize_json(value.maintenance_json),
            complex=camelize_json(complex_detail),
            location=camelize_json(location),
            extra_fields=camelize_json(extra_fields),
        )

    async def listing(
        self,
        listing_group_id: UUID,
        *,
        source_id: UUID,
        run_id: UUID | None = None,
    ) -> ListingDetail:
        apartment = await self.session.scalar(
            select(Apartment)
            .join(ListingGroup, ListingGroup.apartment_id == Apartment.id)
            .where(ListingGroup.id == listing_group_id)
        )
        if apartment is None:
            raise QueryNotFoundError("매물을 찾을 수 없습니다.")
        _, apartment_snapshot, selected_run, _ = await self._latest_result(
            complex_id=apartment.naver_complex_id,
            source_id=source_id,
            run_id=run_id,
        )
        rows = await self._listing_rows_for_run(
            apartment_id=apartment.id,
            selected_run=selected_run,
        )
        row = next((item for item in rows if item[1].id == listing_group_id), None)
        absence_record: _AbsenceRecord | None = None
        if row is None:
            absence_records = await self._absence_states_as_of_run(
                apartment_id=apartment.id,
                selected_run=selected_run,
            )
            absence_record = next(
                (
                    record
                    for record in absence_records
                    if record.row[1].id == listing_group_id
                ),
                None,
            )
            if absence_record is None:
                raise QueryNotFoundError("선택한 조사 시점에 매물이 없습니다.")
            row = absence_record.row
        event_statuses = await self._event_statuses(selected_run.id)
        summary = self._listing_summary(
            row,
            selected_run_id=selected_run.id,
            event_status=(
                absence_record.status
                if absence_record is not None
                else event_statuses.get(listing_group_id)
            ),
            removed_at=(
                absence_record.removed_at if absence_record is not None else None
            ),
        )
        snapshot = row[0]
        market_detail = await self.session.scalar(
            select(MarketDetailSnapshot).where(
                MarketDetailSnapshot.listing_snapshot_id == snapshot.id
            )
        )
        registrations = await self._broker_registrations_for_run(
            group_id=listing_group_id,
            run_id=snapshot.run_id,
        )
        captured_apartment = apartment_snapshot.details_json
        return ListingDetail(
            **summary.model_dump(),
            apartment_id=apartment.id,
            complex_id=apartment.naver_complex_id,
            complex_name=str(
                (captured_apartment.get("name") or "")
                if "name" in captured_apartment
                else apartment.name
            ),
            absence_detected_at=(
                seoul_iso(absence_record.detected_at)
                if absence_record is not None
                else None
            ),
            registrations=registrations,
            market_details=self._market_details(market_detail),
        )

    async def dashboard(self, source_id: UUID | None) -> DashboardResponse:
        apartment, snapshot, run, source = await self._latest_result(source_id=source_id)
        apartment_detail = await self.apartment(
            apartment.naver_complex_id,
            source_id=source.id,
            run_id=run.id,
        )
        listing_page = await self.listings(
            apartment.naver_complex_id,
            source_id=source.id,
            run_id=run.id,
            trade_type=None,
            status=None,
        )
        ranked_apartments = self._ranked_apartment_snapshots()
        apartment_count = int(
            (
                await self.session.scalar(
                    select(func.count())
                    .select_from(ranked_apartments)
                    .where(ranked_apartments.c.snapshot_rank == 1)
                )
            )
            or 0
        )
        return DashboardResponse(
            source_id=source.id,
            source_url=source.normalized_url,
            run_id=run.id,
            collected_at=seoul_iso(snapshot.captured_at),
            apartment_count=apartment_count,
            apartment=apartment_detail,
            listings=listing_page.items,
        )
