from __future__ import annotations

from pathlib import Path
import subprocess

import yaml


REPOSITORY_ROOT = Path(__file__).parents[3]


def _compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_every_docker_scheduler_can_reach_healthy_chrome() -> None:
    for relative_path in (
        "backend/docker-compose.yml",
        "docker-compose.production.yml",
    ):
        document = _compose(REPOSITORY_ROOT / relative_path)
        scheduler = document["services"]["scheduler"]

        assert "crawler_control" in scheduler["networks"]
        assert scheduler["depends_on"]["chrome"]["condition"] == "service_healthy"


def test_live_workflow_runs_only_from_main() -> None:
    workflow = _compose(REPOSITORY_ROOT / ".github/workflows/live-naver-e2e.yml")
    condition = workflow["jobs"]["live-one-apartment"]["if"]

    assert "github.ref == 'refs/heads/main'" in condition


def test_chrome_build_uses_current_stable_by_default_with_optional_exact_pin() -> None:
    for relative_path in (
        "backend/docker-compose.yml",
        "docker-compose.production.yml",
    ):
        document = _compose(REPOSITORY_ROOT / relative_path)
        chrome = document["services"]["chrome"]

        assert chrome["image"].endswith("${CHROME_IMAGE_TAG:-stable}")
        assert chrome["build"]["args"]["GOOGLE_CHROME_VERSION"] == (
            "${GOOGLE_CHROME_VERSION:-}"
        )

    dockerfile = (
        REPOSITORY_ROOT / "docker/chrome/Dockerfile"
    ).read_text(encoding="utf-8")
    assert "ARG GOOGLE_CHROME_VERSION" in dockerfile
    assert "ARG GOOGLE_CHROME_VERSION=138.0.7204.157-1" not in dockerfile


def test_windows_local_runtime_generates_and_reuses_bootstrap_token(
    tmp_path: Path,
) -> None:
    token_path = tmp_path / "bootstrap-token.txt"
    script_path = REPOSITORY_ROOT / "scripts/runtime-common.ps1"
    command = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            f". '{script_path}'",
            (
                "$first = Ensure-LocalBootstrapToken "
                f"-TokenPath '{token_path}'"
            ),
            (
                "$second = Ensure-LocalBootstrapToken "
                f"-TokenPath '{token_path}'"
            ),
            "if ($first -cne $second) { throw 'token_not_reused' }",
            "if ($first.Length -lt 64) { throw 'token_too_short' }",
            (
                "Set-LocalRuntimeEnvironment "
                f"-BootstrapTokenPath '{token_path}'"
            ),
            (
                "if ($env:AUTH_BOOTSTRAP_TOKEN -cne $first) "
                "{ throw 'token_not_exported' }"
            ),
        ]
    )

    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert token_path.read_text(encoding="ascii").strip()


def test_live_runner_requires_root_virtual_environment() -> None:
    runner = (
        REPOSITORY_ROOT / "scripts/run-live-naver-e2e.ps1"
    ).read_text(encoding="utf-8")
    workflow = _compose(REPOSITORY_ROOT / ".github/workflows/live-naver-e2e.yml")
    install_step = next(
        step
        for step in workflow["jobs"]["live-one-apartment"]["steps"]
        if step["name"] == "Install live E2E dependencies"
    )

    assert "Join-Path $repositoryRoot '.venv\\Scripts\\python.exe'" in runner
    assert "'python'" not in runner
    assert "python -m venv .venv" in install_step["run"]
    assert ".\\.venv\\Scripts\\python" in install_step["run"]


def test_reference_importer_requires_root_virtual_environment() -> None:
    importer = (
        REPOSITORY_ROOT / "scripts/import-gpt-reference.ps1"
    ).read_text(encoding="utf-8")

    assert "Join-Path $repositoryRoot '.venv\\Scripts\\python.exe'" in importer
    assert "backendRoot \".venv\\Scripts\\python.exe\"" not in importer
    assert '$pythonCommand = "python"' not in importer


def test_backend_docker_context_excludes_local_secrets_and_runtime_data() -> None:
    patterns = {
        line.strip()
        for line in (
            REPOSITORY_ROOT / "backend/.dockerignore"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {".env", ".env.*", "data/", ".venv/", "tests/e2e/artifacts/"}.issubset(
        patterns
    )
