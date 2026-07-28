from __future__ import annotations

import json

import pytest

from tests.e2e.artifact_safety import (
    artifact_safe,
    safe_case_artifact_path,
    write_artifact_json,
)


def test_artifact_safety_redacts_broker_identity_keys_and_sensitive_values(
    tmp_path,
) -> None:
    value = {
        "provider": "네이버부동산",
        "중개사 주소": "서울시 테스트구",
        "중개사 등록번호": "가1234-5678",
        "realtorName": "테스트공인중개사",
        "management_fee": "010-1234-5678",
    }

    safe = artifact_safe(value)

    assert safe["provider"] == "네이버부동산"
    assert safe["중개사 주소"] == "[redacted]"
    assert safe["중개사 등록번호"] == "[redacted]"
    assert safe["realtorName"] == "[redacted]"
    assert safe["management_fee"] == "[redacted-phone]"

    output = tmp_path / "diff.json"
    write_artifact_json(output, value)
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written == safe


@pytest.mark.parametrize("case_id", ["../outside", r"..\outside", "C:outside"])
def test_case_artifact_path_rejects_root_escape(tmp_path, case_id: str) -> None:
    with pytest.raises(ValueError, match="case_id_invalid"):
        safe_case_artifact_path(tmp_path, case_id, "diff.json")
