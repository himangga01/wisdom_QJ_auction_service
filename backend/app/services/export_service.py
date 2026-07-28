from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
import json
import re
from typing import Any
from urllib.parse import urljoin
from uuid import UUID
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services.query_service import camelize_json, seoul_iso

SEOUL = ZoneInfo("Asia/Seoul")

SHEET_HEADERS: dict[str, tuple[str, ...]] = {
    "아파트요약": (
        "단지ID",
        "아파트명",
        "주소",
        "조사실행ID",
        "조사일시",
        "조사상태",
        "단지상세JSON",
    ),
    "매물현황": (
        "단지ID",
        "아파트명",
        "조사실행ID",
        "수집일시",
        "매물그룹ID",
        "거래유형",
        "상태",
        "동",
        "가격(원)",
        "가격표시",
        "보증금(원)",
        "보증금표시",
        "월세(원)",
        "월세표시",
        "공급면적㎡",
        "전용면적㎡",
        "층",
        "방향",
    ),
    "중개사등록": (
        "단지ID",
        "아파트명",
        "매물그룹ID",
        "조사실행ID",
        "매물ID",
        "제공업체",
        "Npay",
        "추가상세수집여부",
        "상세URL",
        "광고가격(원)",
        "광고가격표시",
        "3.3㎡당가격(원)",
        "3.3㎡당가격표시",
        "관리비(원)",
        "관리비표시",
        "융자정보",
        "공급면적㎡",
        "전용면적㎡",
        "전용률",
        "층",
        "방수",
        "욕실수",
        "방향",
        "구조",
        "입주가능일",
        "옵션",
        "설명",
        "최초게시일",
        "확인일",
        "중개사명",
        "대표자",
        "연락처",
        "중개사주소",
        "등록번호",
        "추가필드JSON",
        "물건별금융JSON",
        "물건별실거래JSON",
        "물건별비용세금JSON",
        "물건별관리비JSON",
        "물건별단지JSON",
        "물건별입지교통JSON",
        "물건별추가필드JSON",
        "주의사항",
        "수집일시",
    ),
    "추가정보": (
        "단지ID",
        "아파트명",
        "매물그룹ID",
        "조사실행ID",
        "수집일시",
        "옵션",
        "입주요약",
        "관리비요약",
        "방욕실요약",
        "융자요약",
        "중개사등록수",
        "주의사항",
    ),
    "상세지표": (
        "단지ID",
        "아파트명",
        "매물그룹ID",
        "조사실행ID",
        "수집일시",
        "금융JSON",
        "실거래JSON",
        "비용세금JSON",
        "관리비JSON",
        "단지JSON",
        "입지교통JSON",
        "추가필드JSON",
    ),
    "조사이력": (
        "단지ID",
        "조사실행ID",
        "상태",
        "단계",
        "진행률",
        "오류코드",
        "생성일시",
        "시작일시",
        "종료일시",
    ),
    "변경이벤트": (
        "단지ID",
        "아파트명",
        "조사실행ID",
        "매물그룹ID",
        "이벤트유형",
        "변경필드",
        "이전값JSON",
        "이후값JSON",
        "감지일시",
    ),
}

APARTMENT_SUMMARY_SHEET = next(iter(SHEET_HEADERS))
APARTMENT_DETAIL_EXPORT_FIELDS: tuple[tuple[str, str], ...] = (
    ("household_count", "세대수"),
    ("building_count", "동수"),
    ("approval_date", "사용승인일"),
    ("parking_count", "총주차대수"),
    ("parking_per_household", "세대당주차대수"),
    ("heating", "난방"),
    ("entrance_type", "현관구조"),
    ("floor_area_ratio", "용적률"),
    ("building_coverage_ratio", "건폐율"),
    ("management_office_phone", "관리사무소전화번호"),
    ("builders", "시공사"),
)


class ExportNotFoundError(LookupError):
    code = "export_source_not_found"


@dataclass(frozen=True, slots=True)
class ExportFile:
    filename: str
    content: bytes


def format_korean_won(value: int | None) -> str:
    if value is None:
        return ""
    if value == 0:
        return "0원"
    sign = "-" if value < 0 else ""
    remaining = abs(value)
    eok, remaining = divmod(remaining, 100_000_000)
    man, won = divmod(remaining, 10_000)
    parts: list[str] = []
    if eok:
        parts.append(f"{eok:,}억")
    if man:
        parts.append(f"{man:,}만원")
    if won:
        parts.append(f"{won:,}원")
    return sign + " ".join(parts)


def safe_export_filename(complex_id: str, timestamp: str) -> str:
    safe_complex_id = re.sub(r"[^A-Za-z0-9_-]+", "-", complex_id).strip("-_")
    safe_timestamp = re.sub(r"[^0-9-]+", "", timestamp)
    return f"naver-land-{safe_complex_id or 'unknown'}-{safe_timestamp}.xlsx"


def create_export_workbook() -> tuple[Workbook, dict[str, Any]]:
    workbook = Workbook(write_only=True)
    sheets: dict[str, Any] = {}
    for title, headers in SHEET_HEADERS.items():
        if title == APARTMENT_SUMMARY_SHEET:
            headers = (*headers, *(label for _, label in APARTMENT_DETAIL_EXPORT_FIELDS))
        sheet = workbook.create_sheet(title)
        header_cells = []
        for header in headers:
            cell = WriteOnlyCell(sheet, value=header)
            cell.font = Font(bold=True)
            header_cells.append(cell)
        sheet.append(header_cells)
        sheets[title] = sheet
    return workbook, sheets


def _json(value: Any) -> str:
    if value in (None, {}, []):
        return ""
    return json.dumps(
        camelize_json(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _detail(details: Mapping[str, Any], key: str, default: Any = "") -> Any:
    value = details.get(key, default)
    return default if value is None else value


def _detail_cell(details: Mapping[str, Any], key: str) -> Any:
    value = _detail(details, key)
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return _json(value)
    return value


def _snapshot_apartment_name(
    snapshot: ApartmentSnapshot,
    fallback: str,
) -> str:
    captured = snapshot.details_json
    return str(
        (captured.get("name") or "")
        if "name" in captured
        else fallback
    )


def _date_bounds(
    from_date: date | None, to_date: date | None
) -> tuple[datetime | None, datetime | None]:
    start = (
        datetime.combine(from_date, time.min, tzinfo=SEOUL).astimezone(timezone.utc)
        if from_date
        else None
    )
    end = (
        datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=SEOUL).astimezone(
            timezone.utc
        )
        if to_date
        else None
    )
    return start, end


def _within(statement, column, start: datetime | None, end: datetime | None):
    if start is not None:
        statement = statement.where(column >= start)
    if end is not None:
        statement = statement.where(column < end)
    return statement


TRADE_LABELS = {"sale": "매매", "jeonse": "전세", "monthly": "월세"}


class ExportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate(
        self,
        source_id: UUID,
        *,
        from_date: date | None,
        to_date: date | None,
        now: datetime | None = None,
    ) -> ExportFile:
        if from_date and to_date and from_date > to_date:
            raise ValueError("from은 to보다 늦을 수 없습니다.")
        source = await self.session.get(TrackedSource, source_id)
        if source is None or source.naver_complex_id is None:
            raise ExportNotFoundError("내보낼 조사 URL을 찾을 수 없습니다.")
        apartment = await self.session.scalar(
            select(Apartment).where(
                Apartment.naver_complex_id == source.naver_complex_id
            )
        )
        if apartment is None:
            raise ExportNotFoundError("내보낼 아파트 조사 결과가 없습니다.")

        start, end = _date_bounds(from_date, to_date)
        workbook, sheets = create_export_workbook()
        await self._append_apartments(sheets["아파트요약"], source, apartment, start, end)
        await self._append_listings(
            sheets["매물현황"], sheets["추가정보"], source, apartment, start, end
        )
        await self._append_brokers(
            sheets["중개사등록"], source, apartment, start, end
        )
        await self._append_market_details(
            sheets["상세지표"], source, apartment, start, end
        )
        await self._append_runs(sheets["조사이력"], source, start, end)
        await self._append_events(
            sheets["변경이벤트"], source, apartment, start, end
        )

        output = BytesIO()
        workbook.save(output)
        timestamp = (now or datetime.now(timezone.utc)).astimezone(SEOUL).strftime(
            "%Y%m%d-%H%M"
        )
        return ExportFile(
            filename=safe_export_filename(source.naver_complex_id, timestamp),
            content=output.getvalue(),
        )

    async def _append_apartments(
        self,
        sheet,
        source: TrackedSource,
        apartment: Apartment,
        start: datetime | None,
        end: datetime | None,
    ) -> None:
        statement = (
            select(ApartmentSnapshot, CrawlRun)
            .join(CrawlRun, CrawlRun.id == ApartmentSnapshot.run_id)
            .where(
                ApartmentSnapshot.apartment_id == apartment.id,
                CrawlRun.source_id == source.id,
            )
            .order_by(ApartmentSnapshot.captured_at.asc())
        )
        statement = _within(statement, ApartmentSnapshot.captured_at, start, end)
        result = await self.session.stream(statement)
        async for snapshot, run in result:
            captured = snapshot.details_json
            details = captured.get("details", captured)
            sheet.append(
                [
                    apartment.naver_complex_id,
                    captured.get("name") if "name" in captured else apartment.name,
                    captured.get("address") if "address" in captured else "",
                    str(run.id),
                    seoul_iso(snapshot.captured_at),
                    run.status,
                    _json(details),
                    *(_detail_cell(details, key) for key, _ in APARTMENT_DETAIL_EXPORT_FIELDS),
                ]
            )

    async def _append_listings(
        self,
        listing_sheet,
        aggregate_sheet,
        source: TrackedSource,
        apartment: Apartment,
        start: datetime | None,
        end: datetime | None,
    ) -> None:
        statement = (
            select(
                ListingSnapshot,
                ListingGroup,
                ListingAggregate,
                ApartmentSnapshot,
            )
            .join(ListingGroup, ListingGroup.id == ListingSnapshot.listing_group_id)
            .join(CrawlRun, CrawlRun.id == ListingSnapshot.run_id)
            .join(
                ApartmentSnapshot,
                and_(
                    ApartmentSnapshot.run_id == ListingSnapshot.run_id,
                    ApartmentSnapshot.apartment_id == apartment.id,
                ),
            )
            .outerjoin(
                ListingAggregate,
                ListingAggregate.listing_snapshot_id == ListingSnapshot.id,
            )
            .where(
                ListingGroup.apartment_id == apartment.id,
                CrawlRun.source_id == source.id,
            )
            .order_by(ListingSnapshot.captured_at.asc(), ListingGroup.id.asc())
        )
        statement = _within(statement, ListingSnapshot.captured_at, start, end)
        result = await self.session.stream(statement)
        async for snapshot, group, aggregate, apartment_snapshot in result:
            apartment_name = _snapshot_apartment_name(
                apartment_snapshot,
                apartment.name,
            )
            listing_sheet.append(
                [
                    apartment.naver_complex_id,
                    apartment_name,
                    str(snapshot.run_id),
                    seoul_iso(snapshot.captured_at),
                    str(group.id),
                    TRADE_LABELS.get(snapshot.trade_type, snapshot.trade_type),
                    snapshot.status,
                    snapshot.building or "",
                    snapshot.price,
                    format_korean_won(snapshot.price),
                    snapshot.deposit,
                    format_korean_won(snapshot.deposit),
                    snapshot.monthly_rent,
                    format_korean_won(snapshot.monthly_rent),
                    float(snapshot.supply_area) if snapshot.supply_area is not None else None,
                    (
                        float(snapshot.exclusive_area)
                        if snapshot.exclusive_area is not None
                        else None
                    ),
                    snapshot.floor or "",
                    snapshot.direction or "",
                ]
            )
            aggregate_sheet.append(
                [
                    apartment.naver_complex_id,
                    apartment_name,
                    str(group.id),
                    str(snapshot.run_id),
                    seoul_iso(snapshot.captured_at),
                    ", ".join(aggregate.option_tags_json) if aggregate else "",
                    aggregate.move_in_summary if aggregate else "",
                    aggregate.management_fee_summary if aggregate else "",
                    aggregate.room_bath_summary if aggregate else "",
                    aggregate.loan_summary if aggregate else "",
                    aggregate.source_count if aggregate else 0,
                    " / ".join(aggregate.warnings_json) if aggregate else "",
                ]
            )

    async def _append_brokers(
        self,
        sheet,
        source: TrackedSource,
        apartment: Apartment,
        start: datetime | None,
        end: datetime | None,
    ) -> None:
        statement = (
            select(
                BrokerArticleSnapshot,
                BrokerArticle,
                ListingGroup,
                ApartmentSnapshot,
            )
            .join(
                BrokerArticle,
                BrokerArticle.id == BrokerArticleSnapshot.broker_article_id,
            )
            .join(ListingGroup, ListingGroup.id == BrokerArticle.listing_group_id)
            .join(CrawlRun, CrawlRun.id == BrokerArticleSnapshot.run_id)
            .join(
                ApartmentSnapshot,
                and_(
                    ApartmentSnapshot.run_id == BrokerArticleSnapshot.run_id,
                    ApartmentSnapshot.apartment_id == apartment.id,
                ),
            )
            .where(
                ListingGroup.apartment_id == apartment.id,
                CrawlRun.source_id == source.id,
            )
            .order_by(
                BrokerArticleSnapshot.captured_at.asc(),
                BrokerArticle.naver_article_id.asc(),
            )
        )
        statement = _within(statement, BrokerArticleSnapshot.captured_at, start, end)
        result = await self.session.stream(statement)
        async for snapshot, article, group, apartment_snapshot in result:
            details = snapshot.details_json
            detail_collected = details.get("detail_collected", True)
            apartment_name = _snapshot_apartment_name(
                apartment_snapshot,
                apartment.name,
            )
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
            market_details = (
                details.get("market_details") or {} if detail_collected else {}
            )
            advertised_price = _detail(details, "advertised_price", None)
            per_area_price = _detail(details, "price_per_3_3m2", None)
            management_fee = _detail(details, "management_fee", None)
            sheet.append(
                [
                    apartment.naver_complex_id,
                    apartment_name,
                    str(group.id),
                    str(snapshot.run_id),
                    article.naver_article_id,
                    provider,
                    "Y" if is_npay else "N",
                    "Y" if detail_collected else "N",
                    article_url,
                    advertised_price,
                    format_korean_won(advertised_price),
                    per_area_price,
                    format_korean_won(per_area_price),
                    management_fee,
                    format_korean_won(management_fee),
                    _detail(details, "loan_description"),
                    _detail(details, "supply_area_m2"),
                    _detail(details, "exclusive_area_m2"),
                    _detail(details, "exclusive_rate"),
                    _detail(details, "floor"),
                    _detail(details, "room_count"),
                    _detail(details, "bathroom_count"),
                    _detail(details, "direction"),
                    _detail(details, "structure"),
                    _detail(details, "move_in_date"),
                    ", ".join(_detail(details, "option_tags", [])),
                    _detail(details, "description"),
                    _detail(details, "first_published_at"),
                    _detail(details, "verified_at"),
                    realtor.get("name", ""),
                    realtor.get("representative", ""),
                    realtor.get("phone", ""),
                    realtor.get("address", ""),
                    realtor.get("registration_number", ""),
                    _json(_detail(details, "extra_fields", {})),
                    _json(market_details.get("finance")),
                    _json(market_details.get("transactions")),
                    _json(market_details.get("costs")),
                    _json(market_details.get("maintenance")),
                    _json(market_details.get("complex")),
                    _json(market_details.get("location")),
                    _json(market_details.get("extra_fields")),
                    " / ".join(_detail(details, "warnings", [])),
                    seoul_iso(snapshot.captured_at),
                ]
            )

    async def _append_market_details(
        self,
        sheet,
        source: TrackedSource,
        apartment: Apartment,
        start: datetime | None,
        end: datetime | None,
    ) -> None:
        statement = (
            select(
                MarketDetailSnapshot,
                ListingSnapshot,
                ListingGroup,
                ApartmentSnapshot,
            )
            .join(
                ListingSnapshot,
                ListingSnapshot.id == MarketDetailSnapshot.listing_snapshot_id,
            )
            .join(ListingGroup, ListingGroup.id == ListingSnapshot.listing_group_id)
            .join(CrawlRun, CrawlRun.id == ListingSnapshot.run_id)
            .join(
                ApartmentSnapshot,
                and_(
                    ApartmentSnapshot.run_id == ListingSnapshot.run_id,
                    ApartmentSnapshot.apartment_id == apartment.id,
                ),
            )
            .where(
                ListingGroup.apartment_id == apartment.id,
                CrawlRun.source_id == source.id,
            )
            .order_by(ListingSnapshot.captured_at.asc(), ListingGroup.id.asc())
        )
        statement = _within(statement, ListingSnapshot.captured_at, start, end)
        result = await self.session.stream(statement)
        async for detail, snapshot, group, apartment_snapshot in result:
            location = dict(detail.location_json)
            complex_detail = location.pop("_complex", {})
            extra_fields = location.pop("_extra", {})
            apartment_name = _snapshot_apartment_name(
                apartment_snapshot,
                apartment.name,
            )
            sheet.append(
                [
                    apartment.naver_complex_id,
                    apartment_name,
                    str(group.id),
                    str(snapshot.run_id),
                    seoul_iso(snapshot.captured_at),
                    _json(detail.finance_json),
                    _json(detail.transactions_json),
                    _json(detail.costs_json),
                    _json(detail.maintenance_json),
                    _json(complex_detail),
                    _json(location),
                    _json(extra_fields),
                ]
            )

    async def _append_runs(
        self,
        sheet,
        source: TrackedSource,
        start: datetime | None,
        end: datetime | None,
    ) -> None:
        statement = (
            select(CrawlRun)
            .where(CrawlRun.source_id == source.id)
            .order_by(CrawlRun.created_at.asc())
        )
        statement = _within(statement, CrawlRun.created_at, start, end)
        result = await self.session.stream_scalars(statement)
        async for run in result:
            sheet.append(
                [
                    source.naver_complex_id,
                    str(run.id),
                    run.status,
                    run.stage,
                    run.progress,
                    run.error_code or "",
                    seoul_iso(run.created_at),
                    seoul_iso(run.started_at) if run.started_at else "",
                    seoul_iso(run.finished_at) if run.finished_at else "",
                ]
            )

    async def _append_events(
        self,
        sheet,
        source: TrackedSource,
        apartment: Apartment,
        start: datetime | None,
        end: datetime | None,
    ) -> None:
        statement = (
            select(ChangeEvent, ListingGroup, ApartmentSnapshot)
            .join(ListingGroup, ListingGroup.id == ChangeEvent.listing_group_id)
            .join(CrawlRun, CrawlRun.id == ChangeEvent.run_id)
            .join(
                ApartmentSnapshot,
                and_(
                    ApartmentSnapshot.run_id == ChangeEvent.run_id,
                    ApartmentSnapshot.apartment_id == apartment.id,
                ),
            )
            .where(
                ListingGroup.apartment_id == apartment.id,
                CrawlRun.source_id == source.id,
            )
            .order_by(ChangeEvent.detected_at.asc(), ChangeEvent.id.asc())
        )
        statement = _within(statement, ChangeEvent.detected_at, start, end)
        result = await self.session.stream(statement)
        async for event, group, apartment_snapshot in result:
            sheet.append(
                [
                    apartment.naver_complex_id,
                    _snapshot_apartment_name(apartment_snapshot, apartment.name),
                    str(event.run_id),
                    str(group.id),
                    event.event_type,
                    ", ".join(event.changed_fields_json),
                    _json(event.before_json),
                    _json(event.after_json),
                    seoul_iso(event.detected_at),
                ]
            )
