from __future__ import annotations

import json
import logging
import re
import sys
from typing import Literal
from uuid import UUID


_LOGGER_NAME = "app.operations"
_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
_ALLOWED_STAGES = {
    "url",
    "complex",
    "listings",
    "brokers",
    "details",
    "compare",
    "save",
}
_ALLOWED_EVENTS = {"crawl_started", "crawl_stage", "crawl_metric", "crawl_finished"}

LogLevel = Literal["info", "warning", "error"]


def configure_logging() -> None:
    """Configure the isolated operational logger without exposing request queries."""
    logger = logging.getLogger(_LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Uvicorn's default access line contains the full request target, including query.
    logging.getLogger("uvicorn.access").disabled = True


def _uuid_text(value: UUID | str | None) -> str | None:
    if value is None:
        return None
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        return None


def _code(value: str | None, *, fallback: str) -> str | None:
    if value is None:
        return None
    return value if _CODE_PATTERN.fullmatch(value) else fallback


def log_run_event(
    event: str,
    *,
    run_id: UUID | str | None = None,
    source_id: UUID | str | None = None,
    stage: str | None = None,
    count: int | None = None,
    error: str | None = None,
    duration: int | None = None,
    level: LogLevel = "info",
) -> None:
    """Emit a JSON run event containing only the approved operational context."""
    configure_logging()
    payload: dict[str, str | int] = {
        "event": event if event in _ALLOWED_EVENTS else "crawl_metric"
    }

    normalized_run_id = _uuid_text(run_id)
    normalized_source_id = _uuid_text(source_id)
    if normalized_run_id is not None:
        payload["runId"] = normalized_run_id
    if normalized_source_id is not None:
        payload["sourceId"] = normalized_source_id
    if stage in _ALLOWED_STAGES:
        payload["stage"] = stage
    if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
        payload["count"] = count
    normalized_error = _code(error, fallback="invalid_error_code")
    if normalized_error is not None:
        payload["error"] = normalized_error
    if isinstance(duration, int) and not isinstance(duration, bool) and duration >= 0:
        payload["duration"] = duration

    logger = logging.getLogger(_LOGGER_NAME)
    log_method = getattr(logger, level, logger.info)
    log_method(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
