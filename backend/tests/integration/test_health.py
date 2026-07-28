from fastapi.testclient import TestClient

from app.api.routes.health import browser_status, database_status, redis_status
from app.main import create_app


def test_health_reports_each_dependency() -> None:
    app = create_app()
    app.dependency_overrides[database_status] = lambda: "connected"
    app.dependency_overrides[redis_status] = lambda: "connected"
    app.dependency_overrides[browser_status] = lambda: "ready"

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "connected",
        "redis": "connected",
        "browser": "ready",
    }


def test_health_degrades_when_browser_is_unavailable() -> None:
    app = create_app()
    app.dependency_overrides[database_status] = lambda: "connected"
    app.dependency_overrides[redis_status] = lambda: "connected"
    app.dependency_overrides[browser_status] = lambda: "unavailable"

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "database": "connected",
        "redis": "connected",
        "browser": "unavailable",
    }
