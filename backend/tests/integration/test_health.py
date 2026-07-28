from fastapi.testclient import TestClient

from app.api.routes.health import database_status, redis_status
from app.main import create_app


def test_health_reports_each_dependency() -> None:
    app = create_app()
    app.dependency_overrides[database_status] = lambda: "connected"
    app.dependency_overrides[redis_status] = lambda: "connected"

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "connected",
        "redis": "connected",
    }
