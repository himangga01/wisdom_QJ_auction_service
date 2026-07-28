from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.database import Base, get_session
from app.main import create_app


@pytest_asyncio.fixture
async def auth_client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[TestClient]:
    monkeypatch.setenv("AUTH_BOOTSTRAP_TOKEN", "b" * 32)
    monkeypatch.setenv("AUTH_ALLOWED_ORIGINS", "http://testserver")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
    get_settings.cache_clear()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def test_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as client:
        yield client
    await engine.dispose()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_bootstrap_login_and_cookie_security_contract(auth_client: TestClient) -> None:
    status_response = auth_client.get("/api/auth/bootstrap-status")
    assert status_response.json() == {"bootstrapRequired": True}

    bootstrap_response = auth_client.post(
        "/api/auth/bootstrap",
        headers={
            "Origin": "http://testserver",
            "X-Bootstrap-Token": "b" * 32,
        },
        json={
            "email": "admin@example.com",
            "displayName": "관리자",
            "password": "correct horse battery staple",
        },
    )

    assert bootstrap_response.status_code == 201
    assert "sessionToken" not in bootstrap_response.text
    set_cookie = bootstrap_response.headers.get_list("set-cookie")
    assert any(
        "wisdom_session=" in value
        and "HttpOnly" in value
        and "SameSite=lax" in value
        for value in set_cookie
    )
    assert any(
        "wisdom_csrf=" in value
        and "HttpOnly" not in value
        and "SameSite=strict" in value
        for value in set_cookie
    )
    assert auth_client.get("/api/auth/bootstrap-status").json() == {
        "bootstrapRequired": False
    }


@pytest.mark.asyncio
async def test_mutating_authenticated_request_rejects_bad_origin_and_csrf(
    auth_client: TestClient,
) -> None:
    auth_client.post(
        "/api/auth/bootstrap",
        headers={
            "Origin": "http://testserver",
            "X-Bootstrap-Token": "b" * 32,
        },
        json={
            "email": "admin@example.com",
            "displayName": "관리자",
            "password": "correct horse battery staple",
        },
    )
    no_csrf = auth_client.post(
        "/api/auth/logout",
        headers={"Origin": "http://testserver"},
    )
    bad_origin = auth_client.post(
        "/api/auth/logout",
        headers={
            "Origin": "http://attacker.example",
            "X-CSRF-Token": auth_client.cookies["wisdom_csrf"],
        },
    )

    assert no_csrf.status_code == 403
    assert no_csrf.json()["detail"]["code"] == "csrf_invalid"
    assert bad_origin.status_code == 403
    assert bad_origin.json()["detail"]["code"] == "origin_invalid"
