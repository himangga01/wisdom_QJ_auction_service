from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from tests.e2e.reference_loader import (
    GptArticleObservation,
    GptCaseObservation,
    GptObservationSet,
    ReferenceImportError,
    ReferenceStaleError,
    load_reference as _load_reference,
)


def load_reference(
    path: Path,
    *,
    now: datetime,
    max_age: timedelta,
) -> GptObservationSet:
    """Load a raw version 2 fixture for comparator-focused unit tests."""
    return _load_reference(
        path,
        now=now,
        max_age=max_age,
        require_payload_hash=False,
    )


__all__ = [
    "GptArticleObservation",
    "GptCaseObservation",
    "GptObservationSet",
    "ReferenceImportError",
    "ReferenceStaleError",
    "load_reference",
]
