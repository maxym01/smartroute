from datetime import datetime

import pytest
from fastapi.testclient import TestClient

STOPS_URL = "/api/v1/stops"
CONNECTIONS_URL = "/api/v1/connections"


def connections(client: TestClient, origin: str, destination: str, departure_at: str, **params):
    return client.get(
        CONNECTIONS_URL,
        params={
            "origin_stop_id": origin,
            "destination_stop_id": destination,
            "departure_at": departure_at,
            **params,
        },
    )


# --- /stops ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("glowny", ["A1"]),  # bez polskich znaków
        ("ŁĄKOWA", ["C1"]),  # wielkie litery z diakrytykami
        ("01", ["B1", "A1", "C1", "D1"]),  # alfabetycznie po nazwie
        ("D1", ["D1"]),  # dokładny stop_id
    ],
)
def test_search_stops(gtfs_client: TestClient, query: str, expected: list[str]) -> None:
    response = gtfs_client.get(STOPS_URL, params={"query": query})

    assert response.status_code == 200
    body = response.json()
    assert [item["stop_id"] for item in body["items"]] == expected
    assert body["count"] == len(expected)


def test_search_stops_returns_ids_and_coordinates(gtfs_client: TestClient) -> None:
    item = gtfs_client.get(STOPS_URL, params={"query": "brama"}).json()["items"][0]

    assert item == {
        "stop_id": "B1",
        "stop_name": "Brama Wyżynna 01",
        "stop_code": "B1",
        "stop_lat": 54.35,
        "stop_lon": 18.64,
    }


def test_search_stops_respects_limit(gtfs_client: TestClient) -> None:
    body = gtfs_client.get(STOPS_URL, params={"query": "01", "limit": 2}).json()

    assert body["count"] == 2


@pytest.mark.parametrize("params", [{}, {"query": "a"}, {"query": "ab", "limit": 0}])
def test_search_stops_validates_query(gtfs_client: TestClient, params: dict) -> None:
    assert gtfs_client.get(STOPS_URL, params=params).status_code == 422


def test_gtfs_endpoints_return_503_when_not_imported(client: TestClient) -> None:
    for response in (
        client.get(STOPS_URL, params={"query": "glowny"}),
        connections(client, "A1", "C1", "2026-11-12T07:55:00"),
    ):
        assert response.status_code == 503
        assert response.json()["code"] == "gtfs_not_imported"


# --- /connections ----------------------------------------------------------------------------


def test_direct_connection_with_line_times_and_duration(gtfs_client: TestClient) -> None:
    response = connections(gtfs_client, "A1", "C1", "2026-11-12T07:55:00")

    assert response.status_code == 200
    body = response.json()
    assert body["data_source"] == "gtfs_schedule"
    assert body["is_realtime"] is False
    assert body["origin"]["stop_name"] == "Dworzec Główny 01"
    assert body["departure_at"] == "2026-11-12T07:55:00+01:00"
    assert body["feed"]["valid_to"] == "2026-11-15"
    first = body["connections"][0]
    assert first["trip_id"] == "T1"
    assert first["line"] == "8"
    assert first["headsign"] == "Łąkowa"
    assert first["departure_at"] == "2026-11-12T08:00:00+01:00"
    assert first["arrival_at"] == "2026-11-12T08:20:00+01:00"
    assert first["duration_min"] == 20.0
    assert (first["origin_stop_sequence"], first["destination_stop_sequence"]) == (1, 3)


def test_opposite_direction_uses_stop_sequence(gtfs_client: TestClient) -> None:
    there = connections(gtfs_client, "A1", "C1", "2026-11-12T07:00:00", window_min=600).json()
    back = connections(gtfs_client, "C1", "A1", "2026-11-12T07:00:00", window_min=600).json()

    assert [c["trip_id"] for c in there["connections"]] == ["T1"]
    assert [c["trip_id"] for c in back["connections"]] == ["T2"]


def test_departure_with_explicit_offset_is_respected(gtfs_client: TestClient) -> None:
    # 06:58 UTC = 07:58 w Gdańsku
    body = connections(gtfs_client, "A1", "C1", "2026-11-12T06:58:00Z", window_min=5).json()

    assert [c["trip_id"] for c in body["connections"]] == ["T1"]


def test_connection_after_midnight(gtfs_client: TestClient) -> None:
    body = connections(gtfs_client, "A1", "C1", "2026-11-12T23:45:00").json()

    night = body["connections"][0]
    assert night["trip_id"] == "T3"
    assert night["line"] == "N1"
    assert night["service_date"] == "2026-11-12"
    assert night["departure_at"] == "2026-11-12T23:50:00+01:00"
    assert night["arrival_at"] == "2026-11-13T00:20:00+01:00"
    assert night["duration_min"] == 30.0


def test_after_midnight_departure_finds_previous_service_day(gtfs_client: TestClient) -> None:
    # 13.11 00:00 — kurs T3 jedzie według kalendarza z 12.11 (czasy 24:05 / 24:20).
    body = connections(gtfs_client, "B1", "C1", "2026-11-13T00:00:00").json()

    assert [c["trip_id"] for c in body["connections"]] == ["T3"]
    assert body["connections"][0]["departure_at"] == "2026-11-13T00:05:00+01:00"


def test_calendar_dates_decide_service(gtfs_client: TestClient) -> None:
    # 13.11 jeździ tylko WD (T1), a nocny NIGHT nie.
    body = connections(gtfs_client, "A1", "C1", "2026-11-13T07:00:00", window_min=1440).json()

    assert [(c["trip_id"], c["service_date"]) for c in body["connections"]] == [
        ("T1", "2026-11-13")
    ]


def test_no_connection_returns_empty_list_with_note(gtfs_client: TestClient) -> None:
    body = connections(gtfs_client, "A1", "D1", "2026-11-12T07:00:00").json()

    assert body["connections"] == []
    assert any("Brak bezpośredniego połączenia" in note for note in body["notes"])


def test_drop_off_not_allowed_at_destination_is_excluded(gtfs_client: TestClient) -> None:
    # A1 to pierwszy przystanek T1 z drop_off_type=1 — nie da się tam dojechać T1.
    body = connections(gtfs_client, "B1", "A1", "2026-11-12T08:05:00", window_min=30).json()

    assert body["connections"] == []


def test_date_outside_feed_validity_is_reported(gtfs_client: TestClient) -> None:
    body = connections(gtfs_client, "A1", "C1", "2026-12-20T08:00:00").json()

    assert body["connections"] == []
    assert any("poza okresem ważności" in note for note in body["notes"])


def test_unknown_stop_returns_404(gtfs_client: TestClient) -> None:
    response = connections(gtfs_client, "A1", "NOPE", "2026-11-12T08:00:00")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


@pytest.mark.parametrize(
    "params",
    [
        {"origin_stop_id": "A1", "destination_stop_id": "A1"},
        {"origin_stop_id": "A1"},
        {"origin_stop_id": "A1", "destination_stop_id": "C1", "departure_at": "jutro"},
        {"origin_stop_id": "A1", "destination_stop_id": "C1", "limit": 0},
    ],
)
def test_connections_validation(gtfs_client: TestClient, params: dict) -> None:
    response = gtfs_client.get(CONNECTIONS_URL, params=params)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_departure_defaults_to_now(gtfs_client: TestClient) -> None:
    body = gtfs_client.get(
        CONNECTIONS_URL, params={"origin_stop_id": "A1", "destination_stop_id": "C1"}
    ).json()

    departure = datetime.fromisoformat(body["departure_at"])
    assert departure.tzinfo is not None
    assert abs((datetime.now(departure.tzinfo) - departure).total_seconds()) < 60
