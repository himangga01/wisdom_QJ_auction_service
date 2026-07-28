from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pytest


NOW = datetime(2026, 7, 29, 3, 0, tzinfo=timezone.utc)
SOURCE_URL = (
    "https://fin.land.naver.com/map?"
    "center=sample-value&zoom=15&complexId=131197"
)
EXAMPLE_PATH = (
    Path(__file__).parents[1] / "e2e" / "reference" / "example.json"
)


def _source_hash(url: str = SOURCE_URL) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _document() -> dict[str, object]:
    return {
        "schemaVersion": "2",
        "captureTool": "gpt_browser_manual",
        "mode": "sample",
        "capturedAt": "2026-07-29T11:45:00+09:00",
        "normalizationVersion": "2",
        "cases": [
            {
                "caseId": "case-sample",
                "sourceUrlSha256": _source_hash(),
                "complexId": " 131197 ",
                "complexName": " 샘플   아파트 ",
                "tradeCounts": {" 매매 ": 1},
                "articles": [
                    {
                        "articleId": " article-1 ",
                        "tradeType": "매매",
                        "price": "720,000,000원",
                        "building": " 107동 ",
                        "floor": " 12 / 25층 ",
                        "direction": " 남향 ",
                        "supplyAreaM2": "84.120",
                        "exclusiveAreaM2": "59.990",
                        "displayedBrokerCount": 2,
                        "optionTags": [" 중문 ", "시스템에어컨", "중문"],
                        "moveInDate": " 2026년 8월   협의 ",
                        "requiredDetailFields": {
                            " 관리 방식 ": " 위탁   관리 ",
                            "관리 방식": "위탁 관리",
                        },
                    }
                ],
            }
        ],
    }


def _write_inputs(
    tmp_path: Path,
    document: dict[str, object],
    *,
    source_url: str = SOURCE_URL,
) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    input_path = tmp_path / "capture.json"
    manifest_path = tmp_path / "case-manifest.local.json"
    input_path.write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            {
                "schemaVersion": "1",
                "cases": [
                    {
                        "caseId": "case-sample",
                        "sourceUrl": source_url,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return input_path, manifest_path


def _import_reference(
    tmp_path: Path,
    document: dict[str, object],
    *,
    source_url: str = SOURCE_URL,
):
    from tests.e2e.reference_loader import import_reference

    input_path, manifest_path = _write_inputs(
        tmp_path,
        document,
        source_url=source_url,
    )
    return import_reference(
        input_path,
        manifest_path,
        destination=tmp_path / "current",
        now=NOW,
    )


def test_import_normalizes_and_writes_only_sanitized_canonical_json(
    tmp_path: Path,
) -> None:
    result = _import_reference(tmp_path, _document())

    output_text = result.path.read_text(encoding="utf-8")
    output = json.loads(output_text)
    article = output["cases"][0]["articles"][0]

    assert result.path == tmp_path / "current" / "reference.json"
    assert output_text.endswith("\n")
    assert SOURCE_URL not in output_text
    assert "sourceUrl" not in output["cases"][0]
    assert output["cases"][0]["sourceUrlSha256"] == _source_hash()
    assert output["cases"][0]["complexId"] == "131197"
    assert output["cases"][0]["complexName"] == "샘플 아파트"
    assert article["price"] == 720_000_000
    assert article["supplyAreaM2"] == "84.12"
    assert article["exclusiveAreaM2"] == "59.99"
    assert article["optionTags"] == ["시스템에어컨", "중문"]
    assert article["requiredDetailFields"] == {"관리 방식": "위탁 관리"}


def test_payload_hash_is_reproducible_and_covers_canonical_payload(
    tmp_path: Path,
) -> None:
    first = _import_reference(tmp_path / "first", _document())
    second = _import_reference(tmp_path / "second", _document())

    first_output = json.loads(first.path.read_text(encoding="utf-8"))
    payload_hash = first_output.pop("payloadSha256")
    canonical_payload = json.dumps(
        first_output,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert payload_hash == hashlib.sha256(canonical_payload).hexdigest()
    assert first.payload_sha256 == payload_hash
    assert second.payload_sha256 == payload_hash
    assert first.path.read_bytes() == second.path.read_bytes()


def test_committed_example_is_hash_valid_and_contains_no_full_url() -> None:
    from tests.e2e.reference_loader import load_reference

    example_text = EXAMPLE_PATH.read_text(encoding="utf-8")
    reference = load_reference(EXAMPLE_PATH, now=NOW)

    assert reference.schema_version == "2"
    assert "https://" not in example_text


@pytest.mark.parametrize(
    ("captured_at", "expected_code"),
    [
        ("2026-07-29T11:29:59+09:00", "reference_stale"),
        ("2026-07-29T12:03:01+09:00", "reference_future"),
        ("2026-07-29T11:45:00", "timezone_required"),
    ],
)
def test_import_rejects_stale_or_timezone_less_capture(
    tmp_path: Path,
    captured_at: str,
    expected_code: str,
) -> None:
    from tests.e2e.reference_loader import ReferenceImportError

    document = _document()
    document["capturedAt"] = captured_at

    with pytest.raises(ReferenceImportError) as raised:
        _import_reference(tmp_path, document)

    assert raised.value.code == expected_code


@pytest.mark.parametrize("duplicate_kind", ["case", "article"])
def test_import_rejects_duplicate_case_and_article_ids(
    tmp_path: Path,
    duplicate_kind: str,
) -> None:
    from tests.e2e.reference_loader import ReferenceImportError

    document = _document()
    cases = document["cases"]
    assert isinstance(cases, list)
    if duplicate_kind == "case":
        cases.append(deepcopy(cases[0]))
    else:
        articles = cases[0]["articles"]
        assert isinstance(articles, list)
        articles.append(deepcopy(articles[0]))

    with pytest.raises(ReferenceImportError) as raised:
        _import_reference(tmp_path, document)

    assert raised.value.code == f"duplicate_{duplicate_kind}_id"


def test_import_rejects_url_hash_mismatch_without_echoing_url(
    tmp_path: Path,
) -> None:
    from tests.e2e.reference_loader import ReferenceImportError

    with pytest.raises(ReferenceImportError) as raised:
        _import_reference(tmp_path, _document(), source_url=SOURCE_URL + "&x=1")

    assert raised.value.code == "source_url_hash_mismatch"
    assert SOURCE_URL not in str(raised.value)


def test_import_rejects_non_naver_map_manifest_url(tmp_path: Path) -> None:
    from tests.e2e.reference_loader import ReferenceImportError

    with pytest.raises(ReferenceImportError) as raised:
        _import_reference(
            tmp_path,
            _document(),
            source_url="https://example.com/map?complexId=131197",
        )

    assert raised.value.code == "manifest_url_invalid"
    assert "https://" not in str(raised.value)


@pytest.mark.parametrize(
    "sensitive_value",
    [
        "010-1234-5678",
        "+82-10-1234-5678",
        "<html><body>raw capture</body></html>",
        "<p>raw capture</p>",
        "Cookie: NID_AUT=secret",
        "NID_AUT=secret; NID_SES=secret",
        "x" * 501,
    ],
)
def test_import_rejects_sensitive_or_long_free_text(
    tmp_path: Path,
    sensitive_value: str,
) -> None:
    from tests.e2e.reference_loader import ReferenceImportError

    document = _document()
    cases = document["cases"]
    assert isinstance(cases, list)
    cases[0]["articles"][0]["requiredDetailFields"] = {
        "메모": sensitive_value
    }

    with pytest.raises(ReferenceImportError) as raised:
        _import_reference(tmp_path, document)

    assert raised.value.code == "sensitive_data"
    assert sensitive_value not in str(raised.value)


@pytest.mark.parametrize(
    "detail_key",
    [
        "중개사명",
        "중개사 주소",
        "중개사 등록번호",
        "realtor_name",
        "broker_registration_number",
    ],
)
def test_import_rejects_broker_identity_detail_keys(
    tmp_path: Path,
    detail_key: str,
) -> None:
    from tests.e2e.reference_loader import ReferenceImportError

    document = _document()
    cases = document["cases"]
    assert isinstance(cases, list)
    cases[0]["articles"][0]["requiredDetailFields"] = {
        detail_key: "공유되면 안 되는 값"
    }

    with pytest.raises(ReferenceImportError) as raised:
        _import_reference(tmp_path, document)

    assert raised.value.code == "detail_key_not_allowed"


@pytest.mark.parametrize("case_id", ["../outside", r"..\outside", "case id"])
def test_import_rejects_unsafe_case_id(
    tmp_path: Path,
    case_id: str,
) -> None:
    from tests.e2e.reference_loader import ReferenceImportError

    document = _document()
    cases = document["cases"]
    assert isinstance(cases, list)
    cases[0]["caseId"] = case_id

    with pytest.raises(ReferenceImportError) as raised:
        _import_reference(tmp_path, document)

    assert raised.value.code == "schema_invalid"
