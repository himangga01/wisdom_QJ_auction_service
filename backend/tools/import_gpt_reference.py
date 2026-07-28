from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from tests.e2e.reference_loader import (  # noqa: E402
    ReferenceImportError,
    import_reference,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import a local, manually captured GPT reference."
    )
    parser.add_argument("--input-path", required=True, type=Path)
    parser.add_argument("--manifest-path", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    destination = REPOSITORY_ROOT / "temp" / "e2e" / "reference" / "current"
    try:
        result = import_reference(
            args.input_path,
            args.manifest_path,
            destination=destination,
            now=datetime.now(timezone.utc),
        )
    except ReferenceImportError as exc:
        print(f"REFERENCE_IMPORT_FAILED code={exc.code}", file=sys.stderr)
        return 1
    except OSError:
        print("REFERENCE_IMPORT_FAILED code=io_error", file=sys.stderr)
        return 1

    print(
        "REFERENCE_IMPORT_OK "
        f"cases={result.case_count} "
        f"payloadSha256={result.payload_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
