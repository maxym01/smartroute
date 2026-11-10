from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.transport_params import BikeParams, TransportSettings

TRIPS_URL = "/api/v1/trips"


def compare_url(trip_id: int | str) -> str:
    return f"{TRIPS_URL}/{trip_id}/compare"


@pytest.fixture
def create_trip(client: TestClient):
    def _create(**overrides: Any) -> dict[str, Any]:
        payload = {
            "name": "Dom → praca",
            "origin": "Dom",
            "destination": "Praca",
            "distance_km": 10,
            "passengers": 1,
            "priority": "balanced",
            "has_car": True,
            "allow_bike": True,
            **overrides,
        }
        response = client.post(TRIPS_URL, json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return _create


def variants_by_mode(body: dict) -> dict[str, dict]:
    return {v["mode"]: v for v in body["variants"]}


def test_compare_returns_full_structure(client: TestClient, create_trip) -> None:
    trip = create_trip()

    response = client.get(compare_url(trip["id"]))

    assert response.status_code == 200
    body = response.json()
    assert body["trip_id"] == trip["id"]
    assert body["priority"] == "balanced"
    assert (body["distance_km"], body["passengers"]) == (10, 1)
    assert body["is_estimate"] is True
    assert "szacunkami" in body["disclaimer"]
    assert [v["mode"] for v in body["variants"]] == ["car", "public_transport", "bike"]

    for variant in body["variants"]:
        assert variant["is_estimate"] is True
        assert variant["data_source"] == "parametric_estimate"
        assert variant["assumptions"]
        for key in (
            "estimated_duration_min",
            "estimated_cost_pln",
            "estimated_cost_per_passenger_pln",
            "estimated_co2_kg",
            "estimated_co2_per_passenger_kg",
        ):
            assert isinstance(variant[key], int | float) and variant[key] >= 0
        assert variant["available"] is True
        assert variant["score"]["rank"] in (1, 2, 3)

    assert body["recommendation"]["mode"] == "bike"
    assert body["recommendation"]["label"] == "Rower"
    assert body["recommendation"]["explanation"].endswith("Wszystkie wartości są szacunkowe.")
    assert body["scoring"]["priority"] == "balanced"
    assert body["scoring"]["tie_break_order"] == ["bike", "public_transport", "car"]
    assert body["scoring"]["balanced_weights"] == {
        "duration": 0.3333,
        "cost": 0.3333,
        "co2": 0.3333,
    }


def test_compare_values_for_default_parameters(client: TestClient, create_trip) -> None:
    trip = create_trip(passengers=2)

    variants = variants_by_mode(client.get(compare_url(trip["id"])).json())

    car, pt = variants["car"], variants["public_transport"]
    assert car["estimated_duration_min"] == 20.0
    assert car["estimated_cost_pln"] == 4.55
    assert car["estimated_cost_per_passenger_pln"] == pytest.approx(4.55 / 2, abs=0.006)
    assert car["estimated_co2_kg"] == 1.7
    assert pt["estimated_cost_pln"] == 8.8
    assert pt["estimated_cost_per_passenger_pln"] == 4.4
    assert pt["estimated_co2_kg"] == 1.0


@pytest.mark.parametrize(
    ("priority", "expected"),
    [("fastest", "car"), ("cheapest", "bike"), ("greenest", "bike"), ("balanced", "bike")],
)
def test_compare_uses_saved_priority(
    client: TestClient, create_trip, priority: str, expected: str
) -> None:
    trip = create_trip(priority=priority)

    body = client.get(compare_url(trip["id"])).json()

    assert body["priority"] == priority
    assert body["recommendation"]["mode"] == expected


def test_compare_priority_query_overrides_without_saving(client: TestClient, create_trip) -> None:
    trip = create_trip(priority="greenest")

    body = client.get(compare_url(trip["id"]), params={"priority": "fastest"}).json()

    assert body["priority"] == "fastest"
    assert body["recommendation"]["mode"] == "car"
    assert client.get(f"{TRIPS_URL}/{trip['id']}").json() == trip


def test_compare_never_recommends_car_without_car(client: TestClient, create_trip) -> None:
    trip = create_trip(has_car=False, priority="fastest")

    body = client.get(compare_url(trip["id"])).json()

    car = variants_by_mode(body)["car"]
    assert car["available"] is False
    assert "has_car" in car["unavailable_reason"]
    assert car["score"] is None
    assert body["recommendation"]["mode"] != "car"
    assert "Pominięto niedostępne" in body["recommendation"]["explanation"]


def test_compare_long_trip_excludes_bike(client: TestClient, create_trip) -> None:
    trip = create_trip(distance_km=35, priority="greenest")

    body = client.get(compare_url(trip["id"])).json()

    bike = variants_by_mode(body)["bike"]
    assert bike["available"] is False and "limit" in bike["unavailable_reason"]
    assert body["recommendation"]["mode"] == "public_transport"


def test_compare_only_public_transport_left(client: TestClient, create_trip) -> None:
    trip = create_trip(has_car=False, allow_bike=False)

    body = client.get(compare_url(trip["id"])).json()

    assert body["recommendation"]["mode"] == "public_transport"
    assert "jedyny dostępny" in body["recommendation"]["explanation"]
    assert variants_by_mode(body)["public_transport"]["score"]["balanced_score"] == 0


def test_compare_boundary_trip(client: TestClient, create_trip) -> None:
    trip = create_trip(distance_km=1000, passengers=8, priority="cheapest")

    response = client.get(compare_url(trip["id"]))

    assert response.status_code == 200
    assert response.json()["recommendation"]["mode"] == "car"


def test_compare_reflects_trip_updates(client: TestClient, create_trip) -> None:
    trip = create_trip(priority="fastest")
    assert client.get(compare_url(trip["id"])).json()["recommendation"]["mode"] == "car"

    client.patch(f"{TRIPS_URL}/{trip['id']}", json={"has_car": False})

    assert client.get(compare_url(trip["id"])).json()["recommendation"]["mode"] != "car"


def test_compare_uses_configured_parameters(
    app: FastAPI, client: TestClient, create_trip, test_settings: Settings
) -> None:
    trip = create_trip(distance_km=25)
    custom = test_settings.model_copy(
        update={"transport": TransportSettings(bike=BikeParams(max_distance_km=30))}
    )
    app.dependency_overrides[get_settings] = lambda: custom

    bike = variants_by_mode(client.get(compare_url(trip["id"])).json())["bike"]

    assert bike["available"] is True


def test_compare_missing_trip_returns_404(client: TestClient) -> None:
    response = client.get(compare_url(9999))

    assert response.status_code == 404
    assert response.json() == {"detail": "Podróż o id=9999 nie istnieje", "code": "not_found"}


def test_compare_deleted_trip_returns_404(client: TestClient, create_trip) -> None:
    trip = create_trip()
    client.delete(f"{TRIPS_URL}/{trip['id']}")

    assert client.get(compare_url(trip["id"])).status_code == 404


@pytest.mark.parametrize("bad_id", ["0", "abc"])
def test_compare_invalid_id_returns_422(client: TestClient, bad_id: str) -> None:
    response = client.get(compare_url(bad_id))

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_compare_invalid_priority_returns_422(client: TestClient, create_trip) -> None:
    trip = create_trip()

    response = client.get(compare_url(trip["id"]), params={"priority": "slowest"})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_compare_is_deterministic(client: TestClient, create_trip) -> None:
    trip = create_trip(distance_km=7.3, passengers=3)

    first = client.get(compare_url(trip["id"])).json()
    second = client.get(compare_url(trip["id"])).json()

    assert first == second
