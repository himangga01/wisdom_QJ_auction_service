from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.core.config import Settings
from app.crawler.browser import PlaywrightNaverLandCollector
from app.crawler.browser_readiness import probe_browser_cdp
from app.crawler.delay import humanized_delay_for_preset
from app.crawler.errors import BlockedCrawlError, CrawlError
from app.crawler.scope import CrawlScope
from tests.e2e.comparison import ComparisonReport, compare_case
from tests.e2e.artifact_safety import (
    SAFE_CASE_ID_PATTERN,
    write_artifact_json,
)
from tests.e2e.reference_loader import (
    REFERENCE_MAX_AGE,
    GptArticleObservation,
    GptCaseObservation,
    ReferenceImportError,
    load_manifest,
    load_reference,
    source_url_for_case,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one protected Naver live E2E case."
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument(
        "--include-details",
        required=True,
        choices=("true", "false"),
    )
    parser.add_argument(
        "--delay-profile",
        required=True,
        choices=("normal", "careful", "very_careful"),
    )
    parser.add_argument("--manifest-path", required=True, type=Path)
    parser.add_argument("--reference-path", required=True, type=Path)
    parser.add_argument("--artifact-directory", required=True, type=Path)
    parser.add_argument(
        "--cdp-url",
        default="http://127.0.0.1:42973",
    )
    return parser.parse_args()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    write_artifact_json(path, value)


def _write_result(
    artifact_directory: Path,
    *,
    case_id: str,
    status: str,
    include_details: bool,
    delay_profile: str,
    error_code: str | None = None,
    report: ComparisonReport | None = None,
) -> None:
    artifact_directory.mkdir(parents=True, exist_ok=True)
    differences = [] if report is None else report.model_dump(mode="json")["differences"]
    summary: dict[str, Any] = {
        "caseId": case_id,
        "status": status,
        "includeDetails": include_details,
        "delayProfile": delay_profile,
        "differenceCount": len(differences),
    }
    if error_code is not None:
        summary["errorCode"] = error_code
    _write_json(artifact_directory / "summary.json", summary)
    _write_json(
        artifact_directory / "diff.json",
        {
            "caseId": case_id,
            "differences": differences,
        },
    )


def _without_detail_expectations(
    expected: GptCaseObservation,
) -> GptCaseObservation:
    articles = [
        GptArticleObservation(
            article_id=article.article_id,
            trade_type=article.trade_type,
            price=article.price,
            building=article.building,
            floor=article.floor,
            direction=article.direction,
            supply_area_m2=article.supply_area_m2,
            exclusive_area_m2=article.exclusive_area_m2,
            displayed_broker_count=article.displayed_broker_count,
            option_tags=[],
            move_in_date=None,
            required_detail_fields={},
        )
        for article in expected.articles
    ]
    return expected.model_copy(update={"articles": articles})


def _load_selected_case(
    *,
    reference_path: Path,
    manifest_path: Path,
    case_id: str,
) -> tuple[GptCaseObservation, str]:
    reference = load_reference(
        reference_path,
        now=datetime.now(timezone.utc),
        max_age=REFERENCE_MAX_AGE,
    )
    if reference.mode != "sample":
        raise ReferenceImportError("reference_mode_invalid")
    expected = next(
        (case for case in reference.cases if case.case_id == case_id),
        None,
    )
    if expected is None:
        raise ReferenceImportError("reference_case_missing")

    manifest = load_manifest(manifest_path)
    source_url = source_url_for_case(manifest, case_id)
    source_url_sha256 = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
    if source_url_sha256 != expected.source_url_sha256:
        raise ReferenceImportError("source_url_hash_mismatch")
    return expected, source_url


async def _collect_and_compare(
    *,
    expected: GptCaseObservation,
    source_url: str,
    include_details: bool,
    delay_profile: str,
    cdp_url: str,
) -> ComparisonReport:
    if await probe_browser_cdp(cdp_url) != "ready":
        raise ReferenceImportError("browser_unavailable")

    settings = Settings(
        app_runtime="local",
        crawler_cdp_url=cdp_url,
        _env_file=None,
    )
    collector = PlaywrightNaverLandCollector(
        settings=settings,
        delay=humanized_delay_for_preset(delay_profile),
    )
    article_ids = {article.article_id for article in expected.articles}
    actual = await collector.collect(
        source_url,
        scope=CrawlScope.sampled(
            article_ids,
            collect_broker_details=include_details,
        ),
    )
    comparison_expected = (
        expected if include_details else _without_detail_expectations(expected)
    )
    return compare_case(comparison_expected, actual)


def main() -> int:
    args = _parse_args()
    include_details = args.include_details == "true"
    case_id = args.case_id
    artifact_directory = args.artifact_directory.resolve()

    if SAFE_CASE_ID_PATTERN.fullmatch(case_id) is None:
        _write_result(
            artifact_directory,
            case_id="invalid-case-id",
            status="rejected",
            include_details=include_details,
            delay_profile=args.delay_profile,
            error_code="case_id_invalid",
        )
        return 3

    try:
        expected, source_url = _load_selected_case(
            reference_path=args.reference_path.resolve(strict=True),
            manifest_path=args.manifest_path.resolve(strict=True),
            case_id=case_id,
        )
        report = asyncio.run(
            _collect_and_compare(
                expected=expected,
                source_url=source_url,
                include_details=include_details,
                delay_profile=args.delay_profile,
                cdp_url=args.cdp_url,
            )
        )
    except BlockedCrawlError as exc:
        _write_result(
            artifact_directory,
            case_id=case_id,
            status="blocked",
            include_details=include_details,
            delay_profile=args.delay_profile,
            error_code=exc.code,
        )
        print(f"LIVE_E2E_RESULT blocked code={exc.code}", flush=True)
        return 2
    except ReferenceImportError as exc:
        _write_result(
            artifact_directory,
            case_id=case_id,
            status="rejected",
            include_details=include_details,
            delay_profile=args.delay_profile,
            error_code=exc.code,
        )
        print(f"LIVE_E2E_RESULT rejected code={exc.code}", flush=True)
        return 3
    except CrawlError as exc:
        _write_result(
            artifact_directory,
            case_id=case_id,
            status="failed",
            include_details=include_details,
            delay_profile=args.delay_profile,
            error_code=exc.code,
        )
        print(f"LIVE_E2E_RESULT failed code={exc.code}", flush=True)
        return 4
    except Exception:
        _write_result(
            artifact_directory,
            case_id=case_id,
            status="failed",
            include_details=include_details,
            delay_profile=args.delay_profile,
            error_code="live_e2e_failed",
        )
        print("LIVE_E2E_RESULT failed code=live_e2e_failed", flush=True)
        return 5

    _write_result(
        artifact_directory,
        case_id=case_id,
        status="passed" if report.ok else "failed",
        include_details=include_details,
        delay_profile=args.delay_profile,
        report=report,
        error_code=None if report.ok else "comparison_failed",
    )
    print(
        "LIVE_E2E_RESULT "
        f"{'passed' if report.ok else 'failed'} "
        f"differences={len(report.differences)}",
        flush=True,
    )
    return 0 if report.ok else 6


if __name__ == "__main__":
    raise SystemExit(main())
