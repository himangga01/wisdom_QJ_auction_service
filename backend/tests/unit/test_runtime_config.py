import asyncio

import pytest
from pydantic import ValidationError

from app.api.routes import health as health_route
from app.core.config import Settings
from app.core.database import configure_sqlite_connection


def test_local_runtime_uses_sqlite_by_default() -> None:
    settings = Settings(app_runtime="local", _env_file=None)

    assert settings.is_local is True
    assert settings.database_url == "sqlite+aiosqlite:///./data/wisdom_local.db"


def test_docker_runtime_keeps_postgres_default() -> None:
    settings = Settings(app_runtime="docker", _env_file=None)

    assert settings.is_local is False
    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_runtime_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        Settings(app_runtime="desktop", _env_file=None)


def test_local_crawler_runtime_defaults_to_project_loopback_chrome() -> None:
    settings = Settings(app_runtime="local", _env_file=None)

    assert settings.crawler_browser_mode == "external_chrome"
    assert settings.crawler_cdp_url == "http://127.0.0.1:42973"


def test_docker_crawler_runtime_defaults_to_playwright() -> None:
    settings = Settings(app_runtime="docker", _env_file=None)

    assert settings.crawler_browser_mode == "playwright"


def test_crawler_fallback_delay_matches_normal_preset() -> None:
    settings = Settings(_env_file=None)

    assert (
        settings.naver_request_delay_min,
        settings.naver_request_delay_max,
    ) == (1.0, 2.5)


def test_local_crawler_runtime_preserves_explicit_playwright_mode() -> None:
    settings = Settings(
        app_runtime="local",
        crawler_browser_mode="playwright",
        _env_file=None,
    )

    assert settings.crawler_browser_mode == "playwright"


def test_crawler_runtime_rejects_unknown_browser_mode() -> None:
    with pytest.raises(ValidationError):
        Settings(crawler_browser_mode="remote_chrome", _env_file=None)


@pytest.mark.parametrize(
    "cdp_url",
    [
        "https://127.0.0.1:42973",
        "http://localhost:42973",
        "http://0.0.0.0:42973",
        "http://127.0.0.1",
        "http://user:password@127.0.0.1:42973",
        "http://127.0.0.1:42973/json/version",
        "http://127.0.0.1:42973?token=secret",
        "http://127.0.0.1:42973#fragment",
    ],
)
def test_crawler_runtime_rejects_non_loopback_or_non_base_cdp_url(
    cdp_url: str,
) -> None:
    with pytest.raises(ValidationError):
        Settings(crawler_cdp_url=cdp_url, _env_file=None)


class RecordingCursor:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: str) -> None:
        self.statements.append(statement)

    def close(self) -> None:
        return None


class RecordingConnection:
    def __init__(self) -> None:
        self.cursor_instance = RecordingCursor()

    def cursor(self) -> RecordingCursor:
        return self.cursor_instance


def test_sqlite_connections_enable_integrity_and_concurrency_pragmas() -> None:
    connection = RecordingConnection()

    configure_sqlite_connection(connection, None)

    assert connection.cursor_instance.statements == [
        "PRAGMA foreign_keys=ON",
        "PRAGMA journal_mode=WAL",
        "PRAGMA busy_timeout=5000",
    ]


def test_local_health_does_not_require_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        health_route,
        "get_settings",
        lambda: Settings(app_runtime="local", _env_file=None),
    )

    assert asyncio.run(health_route.redis_status()) == "not_required"
    response = asyncio.run(health_route.health("connected", "not_required"))
    assert response.status == "ok"
