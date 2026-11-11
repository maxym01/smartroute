"""Pola GTFS w podróżach (kompatybilność wsteczna) i rozkładowy czas w porównaniu."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

TRIPS_URL = "/api/v1/trips"
BASE_TRIP = {
    "name": "Dom → praca",
    "origin": "Wrzeszcz",
    "destination": "Śródmieście",
    "distance_km": 5,
}
GTFS_FIELDS = {
    "origin_stop_id": "A1",
    "destination_stop_id": "C1",
    "departure_at": "2026-11-12T07:55:00",
}


def create(client: TestClient, **fields: Any) -> dict[str, Any]:
    response = client.post(TRIPS_URL, json={**BASE_TRIP, **fields})
    assert response.status_code == 201, response.text
    return response.json()


def public_transport(client: TestClient, trip_id: int) -> dict[str, Any]:
    body = client.get(f"{TRIPS_URL}/{trip_id}/compare").json()
    return next(v for v in body["variants"] if v["mode"] == "public_transport")


# --- CRUD ------------------------------------------------------------------------------------


def test_legacy_payload_still_works_and_gtfs_fields_are_null(client: TestClient) -> None:
    body = create(client)

    assert body["origin_stop_id"] is None
    assert body["destination_stop_id"] is None
    assert body["departure_at"] is None


def test_naive_departure_is_local_time_and_returned_with_offset(client: TestClient) -> None:
    body = create(client, **GTFS_FIELDS)

    assert body["origin_stop_id"] == "A1"
    assert body["destination_stop_id"] == "C1"
    assert body["departure_at"] == "2026-11-12T07:55:00+01:00"
    assert client.get(f"{TRIPS_URL}/{body['id']}").json()["departure_at"] == body["departure_at"]


def test_departure_with_offset_is_stored_as_same_instant(client: TestClient) -> None:
    body = create(client, departure_at="2026-07-01T06:00:00Z")

    assert body["departure_at"] == "2026-07-01T08:00:00+02:00"  # CEST


def test_patch_sets_and_clears_gtfs_fields(client: TestClient) -> None:
    trip = create(client)
    url = f"{TRIPS_URL}/{trip['id']}"

    patched = client.patch(url, json=GTFS_FIELDS).json()
    assert patched["origin_stop_id"] == "A1"
    assert patched["name"] == BASE_TRIP["name"]

    cleared = client.patch(url, json={"departure_at": None, "origin_stop_id": ""}).json()
    assert cleared["departure_at"] is None
    assert cleared["origin_stop_id"] is None
    assert cleared["destination_stop_id"] == "C1"


@pytest.mark.parametrize(
    "fields",
    [
        {"origin_stop_id": "A1", "destination_stop_id": "A1"},
        {"origin_stop_id": "x" * 65},
        {"departure_at": "nie-data"},
    ],
)
def test_invalid_gtfs_fields_are_rejected(client: TestClient, fields: dict) -> None:
    response = client.post(TRIPS_URL, json={**BASE_TRIP, **fields})

    assert response.status_code == 422


def test_patch_rejects_same_stops_after_merge(client: TestClient) -> None:
    trip = create(client, origin_stop_id="A1")

    response = client.patch(f"{TRIPS_URL}/{trip['id']}", json={"destination_stop_id": "A1"})

    assert response.status_code == 422


# --- Porównanie ------------------------------------------------------------------------------


def test_compare_uses_gtfs_schedule_when_connection_exists(gtfs_client: TestClient) -> None:
    trip = create(gtfs_client, **GTFS_FIELDS)

    variant = public_transport(gtfs_client, trip["id"])

    assert variant["data_source"] == "gtfs_schedule"
    # 07:55 → odjazd 08:00 (5 min oczekiwania) → przyjazd 08:20 = 25 min
    assert variant["estimated_duration_min"] == 25.0
    assert "linia 8" in variant["assumptions"][0]
    assert any("bez opóźnień i danych w czasie rzeczywistym" in a for a in variant["assumptions"])
    # koszt i emisja nadal z parametrów
    assert variant["estimated_cost_pln"] == 4.4


def test_compare_without_gtfs_fields_is_unchanged(gtfs_client: TestClient) -> None:
    # Nawet z zaimportowanym rozkładem podróż bez przystanków liczona jest jak dotąd —
    # bez dodatkowych uwag i bez zgadywania przystanku z nazwy miejsca.
    trip = create(gtfs_client, origin="Dworzec Główny 01", destination="Łąkowa 01")

    variant = public_transport(gtfs_client, trip["id"])

    assert variant["data_source"] == "parametric_estimate"
    assert variant["assumptions"][0].startswith("Czas szacowany ze średniej prędkości")
    assert variant["estimated_duration_min"] == round(5 / 22 * 60 + 8, 1)


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        ({**GTFS_FIELDS, "destination_stop_id": "D1"}, "Brak bezpośredniego połączenia"),
        ({**GTFS_FIELDS, "origin_stop_id": "NOPE"}, "nie istnieje w rozkładzie GTFS"),
        ({"origin_stop_id": "A1", "destination_stop_id": "C1"}, "potrzebne są"),
        ({**GTFS_FIELDS, "departure_at": "2026-12-20T08:00:00"}, "Brak bezpośredniego"),
    ],
)
def test_compare_falls_back_to_parametric_with_reason(
    gtfs_client: TestClient, fields: dict, reason: str
) -> None:
    trip = create(gtfs_client, **fields)

    variant = public_transport(gtfs_client, trip["id"])

    assert variant["data_source"] == "parametric_estimate"
    assert reason in variant["assumptions"][0]
    assert "Użyto szacunku parametrycznego" in variant["assumptions"][0]


def test_compare_falls_back_when_gtfs_not_imported(client: TestClient) -> None:
    trip = create(client, **GTFS_FIELDS)

    variant = public_transport(client, trip["id"])

    assert variant["data_source"] == "parametric_estimate"
    assert "nie został zaimportowany" in variant["assumptions"][0]
