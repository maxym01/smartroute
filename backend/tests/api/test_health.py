from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import get_db

HEALTH_URL = "/api/v1/health"


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get(HEALTH_URL)

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "SmartRoute AI",
        "version": "0.1.0",
        "environment": "test",
        "database": "ok",
    }


def test_health_reports_degraded_when_database_fails(app: FastAPI, client: TestClient) -> None:
    class BrokenSession(Session):
        def execute(self, *args, **kwargs):  # type: ignore[override]
            raise OperationalError("SELECT 1", {}, Exception("db down"))

    app.dependency_overrides[get_db] = lambda: BrokenSession()

    response = client.get(HEALTH_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "error"


def test_health_is_not_available_without_api_prefix(client: TestClient) -> None:
    assert client.get("/health").status_code == 404


def test_health_rejects_post(client: TestClient) -> None:
    assert client.post(HEALTH_URL).status_code == 405


def test_openapi_lists_health_endpoint(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert HEALTH_URL in response.json()["paths"]
