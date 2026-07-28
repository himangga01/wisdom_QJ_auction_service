from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError


REFERENCE_MAX_AGE = timedelta(minutes=30)
REFERENCE_FUTURE_SKEW = timedelta(minutes=2)
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SAFE_CASE_ID = r"^[A-Za-z0-9._-]{1,100}$"
PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:(?:\+?82)[ -]?)?"
    r"(?:0?1[016789]|0[2-9]\d?)[ -]?\d{3,4}[ -]?\d{4}(?!\d)"
)
HTML_PATTERN = re.compile(
    r"<!doctype|</?[a-z][a-z0-9-]*(?:\s[^<>]*)?>",
    re.IGNORECASE,
)
SECRET_PATTERN = re.compile(
    r"(?:set-cookie|cookie\s*:|session(?:id|token)?\s*[:=]|"
    r"authorization\s*:|bearer\s+[a-z0-9._~-]+|"
    r"\b(?:nid_aut|nid_ses|nid_jkl|nnb)\s*=)",
    re.IGNORECASE,
)
SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:phone|telephone|mobile|cookie|session|authorization|raw.?html|"
    r"원본.?html|전화번호|휴대폰)",
    re.IGNORECASE,
)
MAX_FREE_TEXT_LENGTH = 500
ALLOWED_REQUIRED_DETAIL_FIELDS = frozenset(
    {
        "provider",
        "is_npay",
        "advertised_price",
        "price_per_3_3m2",
        "management_fee",
        "loan_description",
        "supply_area_m2",
        "exclusive_area_m2",
        "exclusive_rate",
        "floor",
        "room_count",
        "bathroom_count",
        "direction",
        "structure",
        "verified_at",
        "first_published_at",
        "관리 방식",
        "관리비",
        "융자",
        "방수",
        "욕실수",
        "구조",
        "매물 확인일",
        "최초 등록일",
    }
)


class ReferenceImportError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ReferenceStaleError(ReferenceImportError):
    def __init__(self) -> None:
        super().__init__("reference_stale")


class ReferenceModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=False,
    )


class GptArticleObservation(ReferenceModel):
    article_id: str = Field(alias="articleId", min_length=1, max_length=100)
    trade_type: Literal["매매", "전세", "월세"] = Field(alias="tradeType")
    price: int | str | None
    building: str | None
    floor: str | None
    direction: str | None
    supply_area_m2: Decimal | None = Field(alias="supplyAreaM2")
    exclusive_area_m2: Decimal | None = Field(alias="exclusiveAreaM2")
    displayed_broker_count: int = Field(
        alias="displayedBrokerCount",
        ge=0,
    )
    option_tags: list[str] = Field(alias="optionTags")
    move_in_date: str | None = Field(alias="moveInDate")
    required_detail_fields: dict[str, str] = Field(
        alias="requiredDetailFields"
    )


class GptCaseObservation(ReferenceModel):
    case_id: str = Field(
        alias="caseId",
        min_length=1,
        max_length=100,
        pattern=SAFE_CASE_ID,
    )
    source_url_sha256: str = Field(
        alias="sourceUrlSha256",
        pattern=r"^[0-9a-f]{64}$",
    )
    complex_id: str = Field(alias="complexId", min_length=1, max_length=100)
    complex_name: str = Field(
        alias="complexName",
        min_length=1,
        max_length=200,
    )
    trade_counts: dict[str, int] = Field(alias="tradeCounts")
    articles: list[GptArticleObservation]


class GptObservationSet(ReferenceModel):
    schema_version: Literal["2"] = Field(alias="schemaVersion")
    capture_tool: Literal["gpt_browser_manual"] = Field(alias="captureTool")
    mode: Literal["sample", "full"]
    captured_at: datetime = Field(alias="capturedAt")
    normalization_version: Literal["2"] = Field(
        alias="normalizationVersion"
    )
    cases: list[GptCaseObservation] = Field(min_length=1)
    payload_sha256: str | None = Field(
        default=None,
        alias="payloadSha256",
        pattern=r"^[0-9a-f]{64}$",
    )


class ManifestCase(ReferenceModel):
    case_id: str = Field(
        alias="caseId",
        min_length=1,
        max_length=100,
        pattern=SAFE_CASE_ID,
    )
    source_url: str = Field(alias="sourceUrl", min_length=1)


class LocalCaseManifest(ReferenceModel):
    schema_version: Literal["1"] = Field(alias="schemaVersion")
    cases: list[ManifestCase] = Field(min_length=1)


@dataclass(frozen=True)
class ImportedReference:
    path: Path
    payload_sha256: str
    case_count: int


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = _normalize_text(value)
    return normalized or None


def _normalize_decimal(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if not value.is_finite() or value < 0:
        raise ReferenceImportError("schema_invalid")
    return Decimal(format(value.normalize(), "f"))


def _normalize_price(value: int | str | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        if value < 0:
            raise ReferenceImportError("schema_invalid")
        return value
    normalized = re.sub(r"[\s,₩원]", "", value)
    if not normalized.isdecimal():
        raise ReferenceImportError("schema_invalid")
    return int(normalized)


def _contains_sensitive_text(value: str) -> bool:
    return (
        len(value) > MAX_FREE_TEXT_LENGTH
        or PHONE_PATTERN.search(value) is not None
        or HTML_PATTERN.search(value) is not None
        or SECRET_PATTERN.search(value) is not None
    )


def _reject_sensitive_input(value: Any) -> None:
    if isinstance(value, str):
        if _contains_sensitive_text(value):
            raise ReferenceImportError("sensitive_data")
        return
    if isinstance(value, list):
        for item in value:
            _reject_sensitive_input(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if SENSITIVE_KEY_PATTERN.search(str(key)):
                raise ReferenceImportError("sensitive_data")
            _reject_sensitive_input(str(key))
            _reject_sensitive_input(item)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReferenceImportError("json_invalid") from exc


def _validate_capture_time(
    captured_at: datetime,
    *,
    now: datetime,
    max_age: timedelta,
) -> datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ReferenceImportError("timezone_required")
    captured_utc = captured_at.astimezone(timezone.utc)
    now_utc = now.astimezone(timezone.utc)
    if captured_utc - now_utc > REFERENCE_FUTURE_SKEW:
        raise ReferenceImportError("reference_future")
    if now_utc - captured_utc > max_age:
        raise ReferenceStaleError()
    return captured_at


def _validate_unique_ids(reference: GptObservationSet) -> None:
    case_ids: set[str] = set()
    for case in reference.cases:
        case_id = _normalize_text(case.case_id)
        if case_id in case_ids:
            raise ReferenceImportError("duplicate_case_id")
        case_ids.add(case_id)

        article_ids: set[str] = set()
        for article in case.articles:
            article_id = _normalize_text(article.article_id)
            if article_id in article_ids:
                raise ReferenceImportError("duplicate_article_id")
            article_ids.add(article_id)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _payload_dict(reference: GptObservationSet) -> dict[str, object]:
    return reference.model_dump(
        mode="json",
        by_alias=True,
        exclude={"payload_sha256"},
    )


def _payload_hash(reference: GptObservationSet) -> str:
    return hashlib.sha256(_canonical_bytes(_payload_dict(reference))).hexdigest()


def load_reference(
    path: Path,
    *,
    now: datetime,
    max_age: timedelta = REFERENCE_MAX_AGE,
    require_payload_hash: bool = True,
) -> GptObservationSet:
    raw = _read_json(path)
    _reject_sensitive_input(raw)
    try:
        reference = GptObservationSet.model_validate(raw)
    except ValidationError as exc:
        timezone_error = any(
            error["loc"] == ("capturedAt",)
            and error["type"] == "datetime_from_date_parsing"
            for error in exc.errors()
        )
        if timezone_error:
            raise ReferenceImportError("timezone_required") from exc
        raise ReferenceImportError("schema_invalid") from exc

    captured_at = _validate_capture_time(
        reference.captured_at,
        now=now,
        max_age=max_age,
    )
    reference = reference.model_copy(
        update={"captured_at": captured_at.astimezone(timezone.utc)}
    )
    _validate_unique_ids(reference)
    if require_payload_hash:
        if reference.payload_sha256 is None:
            raise ReferenceImportError("payload_hash_missing")
        if reference.payload_sha256 != _payload_hash(reference):
            raise ReferenceImportError("payload_hash_mismatch")
    return reference


def _is_valid_naver_map_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname == "fin.land.naver.com"
        and parsed.port is None
        and parsed.username is None
        and parsed.password is None
        and parsed.path == "/map"
        and bool(parsed.query)
        and not parsed.fragment
    )


def load_manifest(path: Path) -> LocalCaseManifest:
    raw = _read_json(path)
    try:
        manifest = LocalCaseManifest.model_validate(raw)
    except ValidationError as exc:
        raise ReferenceImportError("manifest_schema_invalid") from exc

    case_ids: set[str] = set()
    for case in manifest.cases:
        case_id = _normalize_text(case.case_id)
        if case_id in case_ids:
            raise ReferenceImportError("manifest_duplicate_case_id")
        case_ids.add(case_id)
        if not _is_valid_naver_map_url(case.source_url):
            raise ReferenceImportError("manifest_url_invalid")
    return manifest


def source_url_for_case(
    manifest: LocalCaseManifest,
    case_id: str,
) -> str:
    normalized_id = _normalize_text(case_id)
    for case in manifest.cases:
        if _normalize_text(case.case_id) == normalized_id:
            return case.source_url
    raise ReferenceImportError("manifest_case_missing")


def _normalize_details(values: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_key, raw_value in values.items():
        key = _normalize_text(raw_key)
        value = _normalize_text(raw_value)
        if not key or not value:
            raise ReferenceImportError("schema_invalid")
        if key not in ALLOWED_REQUIRED_DETAIL_FIELDS:
            raise ReferenceImportError("detail_key_not_allowed")
        previous = normalized.get(key)
        if previous is not None and previous != value:
            raise ReferenceImportError("duplicate_detail_key")
        normalized[key] = value
    return dict(sorted(normalized.items()))


def _normalize_article(
    article: GptArticleObservation,
) -> GptArticleObservation:
    return GptArticleObservation(
        article_id=_normalize_text(article.article_id),
        trade_type=article.trade_type,
        price=_normalize_price(article.price),
        building=_normalize_optional_text(article.building),
        floor=_normalize_optional_text(article.floor),
        direction=_normalize_optional_text(article.direction),
        supply_area_m2=_normalize_decimal(article.supply_area_m2),
        exclusive_area_m2=_normalize_decimal(article.exclusive_area_m2),
        displayed_broker_count=article.displayed_broker_count,
        option_tags=sorted(
            {
                normalized
                for value in article.option_tags
                if (normalized := _normalize_text(value))
            }
        ),
        move_in_date=_normalize_optional_text(article.move_in_date),
        required_detail_fields=_normalize_details(
            article.required_detail_fields
        ),
    )


def _normalize_case(case: GptCaseObservation) -> GptCaseObservation:
    trade_counts: dict[str, int] = {}
    for raw_trade_type, count in case.trade_counts.items():
        trade_type = _normalize_text(raw_trade_type)
        if not trade_type or count < 0:
            raise ReferenceImportError("schema_invalid")
        previous = trade_counts.get(trade_type)
        if previous is not None and previous != count:
            raise ReferenceImportError("schema_invalid")
        trade_counts[trade_type] = count

    return GptCaseObservation(
        case_id=_normalize_text(case.case_id),
        source_url_sha256=case.source_url_sha256,
        complex_id=_normalize_text(case.complex_id),
        complex_name=_normalize_text(case.complex_name),
        trade_counts=dict(sorted(trade_counts.items())),
        articles=sorted(
            (_normalize_article(article) for article in case.articles),
            key=lambda article: article.article_id,
        ),
    )


def _validate_manifest_hashes(
    reference: GptObservationSet,
    manifest: LocalCaseManifest,
) -> None:
    reference_ids = {_normalize_text(case.case_id) for case in reference.cases}
    manifest_ids = {_normalize_text(case.case_id) for case in manifest.cases}
    if reference_ids != manifest_ids:
        raise ReferenceImportError("manifest_case_mismatch")

    for case in reference.cases:
        source_url = source_url_for_case(manifest, case.case_id)
        actual_hash = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
        if actual_hash != case.source_url_sha256:
            raise ReferenceImportError("source_url_hash_mismatch")


def import_reference(
    input_path: Path,
    manifest_path: Path,
    *,
    destination: Path,
    now: datetime | None = None,
) -> ImportedReference:
    effective_now = now or datetime.now(timezone.utc)
    reference = load_reference(
        input_path,
        now=effective_now,
        require_payload_hash=False,
    )
    manifest = load_manifest(manifest_path)
    _validate_manifest_hashes(reference, manifest)

    normalized = GptObservationSet(
        schema_version="2",
        capture_tool="gpt_browser_manual",
        mode=reference.mode,
        captured_at=reference.captured_at,
        normalization_version="2",
        cases=sorted(
            (_normalize_case(case) for case in reference.cases),
            key=lambda case: case.case_id,
        ),
    )
    _validate_unique_ids(normalized)
    payload_sha256 = _payload_hash(normalized)
    output = normalized.model_copy(
        update={"payload_sha256": payload_sha256}
    )
    output_text = _canonical_bytes(
        output.model_dump(mode="json", by_alias=True)
    ).decode("utf-8")

    destination.mkdir(parents=True, exist_ok=True)
    output_path = destination / "reference.json"
    output_path.write_text(output_text + "\n", encoding="utf-8")
    return ImportedReference(
        path=output_path,
        payload_sha256=payload_sha256,
        case_count=len(output.cases),
    )
