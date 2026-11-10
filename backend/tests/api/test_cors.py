from fastapi.testclient import TestClient

HEALTH_URL = "/api/v1/health"
ALLOWED_ORIGIN = "http://localhost:5173"
DISALLOWED_ORIGIN = "http://evil.example.com"


def test_preflight_from_allowed_origin(client: TestClient) -> None:
    response = client.options(
        HEALTH_URL,
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    allowed_methods = response.headers["access-control-allow-methods"]
    for method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        assert method in allowed_methods


def test_preflight_from_disallowed_origin_is_rejected(client: TestClient) -> None:
    response = client.options(
        HEALTH_URL,
        headers={"Origin": DISALLOWED_ORIGIN, "Access-Control-Request-Method": "GET"},
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_simple_request_from_allowed_origin_has_cors_header(client: TestClient) -> None:
    response = client.get(HEALTH_URL, headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_simple_request_from_disallowed_origin_has_no_cors_header(client: TestClient) -> None:
    response = client.get(HEALTH_URL, headers={"Origin": DISALLOWED_ORIGIN})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
