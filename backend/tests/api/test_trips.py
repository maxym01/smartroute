from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

TRIPS_URL = "/api/v1/trips"


def trip_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "Dom → praca",
        "origin": "Kraków, Rynek",
        "destination": "Kraków, Nowa Huta",
        "distance_km": 12.5,
        "passengers": 2,
        "priority": "cheapest",
        "has_car": True,
        "allow_bike": False,
        "notes": "Poranny dojazd",
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def create_trip(client: TestClient):
    def _create(**overrides: Any) -> dict[str, Any]:
        response = client.post(TRIPS_URL, json=trip_payload(**overrides))
        assert response.status_code == 201, response.text
        return response.json()

    return _create


def error_fields(response) -> set[str]:
    return {str(error["loc"][-1]) for error in response.json()["detail"]}


# --- POST /trips -----------------------------------------------------------------------------


def test_create_trip_returns_201_and_body(client: TestClient) -> None:
    response = client.post(TRIPS_URL, json=trip_payload())

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    for key, value in trip_payload().items():
        assert body[key] == value
    created_at = datetime.fromisoformat(body["created_at"])
    assert created_at.utcoffset() is not None and created_at.utcoffset().total_seconds() == 0
    assert datetime.fromisoformat(body["updated_at"]) >= created_at


def test_create_trip_applies_defaults(client: TestClient) -> None:
    minimal = {"name": "Spacer", "origin": "A", "destination": "B", "distance_km": 3}

    response = client.post(TRIPS_URL, json=minimal)

    assert response.status_code == 201
    body = response.json()
    assert body["passengers"] == 1
    assert body["priority"] == "balanced"
    assert body["has_car"] is True
    assert body["allow_bike"] is True
    assert body["notes"] is None


def test_create_trip_strips_whitespace_and_blank_notes(client: TestClient) -> None:
    response = client.post(
        TRIPS_URL, json=trip_payload(name="  Trasa  ", origin=" A ", destination=" B ", notes="   ")
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["name"], body["origin"], body["destination"]) == ("Trasa", "A", "B")
    assert body["notes"] is None


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"distance_km": 0}, "distance_km"),
        ({"distance_km": -5}, "distance_km"),
        ({"distance_km": 1000.01}, "distance_km"),
        ({"passengers": 0}, "passengers"),
        ({"passengers": 9}, "passengers"),
        ({"name": ""}, "name"),
        ({"name": "   "}, "name"),
        ({"name": "x" * 101}, "name"),
        ({"origin": "x" * 201}, "origin"),
        ({"notes": "x" * 501}, "notes"),
        ({"priority": "slowest"}, "priority"),
        ({"distance_km": "daleko"}, "distance_km"),
        ({"unknown_field": 1}, "unknown_field"),
    ],
)
def test_create_trip_rejects_invalid_data(client: TestClient, overrides: dict, field: str) -> None:
    response = client.post(TRIPS_URL, json=trip_payload(**overrides))

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert field in error_fields(response)


@pytest.mark.parametrize("field", ["name", "origin", "destination", "distance_km"])
def test_create_trip_requires_field(client: TestClient, field: str) -> None:
    payload = trip_payload()
    del payload[field]

    response = client.post(TRIPS_URL, json=payload)

    assert response.status_code == 422
    assert field in error_fields(response)


def test_create_trip_rejects_same_origin_and_destination_case_insensitive(
    client: TestClient,
) -> None:
    response = client.post(TRIPS_URL, json=trip_payload(origin="Kraków", destination=" KRAKÓW "))

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert "różnić" in body["detail"][0]["msg"]


def test_create_trip_accepts_boundary_values(client: TestClient) -> None:
    response = client.post(
        TRIPS_URL,
        json=trip_payload(distance_km=1000, passengers=8, name="x" * 100, notes="n" * 500),
    )

    assert response.status_code == 201


def test_create_trip_rejects_invalid_json(client: TestClient) -> None:
    response = client.post(
        TRIPS_URL, content="{not json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


# --- GET /trips/{id} -------------------------------------------------------------------------


def test_get_trip_returns_200(client: TestClient, create_trip) -> None:
    created = create_trip()

    response = client.get(f"{TRIPS_URL}/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_missing_trip_returns_404(client: TestClient) -> None:
    response = client.get(f"{TRIPS_URL}/9999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Podróż o id=9999 nie istnieje", "code": "not_found"}


@pytest.mark.parametrize("bad_id", ["0", "-1", "abc"])
def test_get_trip_with_invalid_id_returns_422(client: TestClient, bad_id: str) -> None:
    response = client.get(f"{TRIPS_URL}/{bad_id}")

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


# --- GET /trips ------------------------------------------------------------------------------


def test_list_trips_empty(client: TestClient) -> None:
    response = client.get(TRIPS_URL)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "skip": 0, "limit": 20}


def test_list_trips_newest_first(client: TestClient, create_trip) -> None:
    ids = [create_trip(name=f"Trasa {i}")["id"] for i in range(3)]

    body = client.get(TRIPS_URL).json()

    assert body["total"] == 3
    assert [item["id"] for item in body["items"]] == list(reversed(ids))


def test_list_trips_pagination(client: TestClient, create_trip) -> None:
    ids = [create_trip(name=f"Trasa {i}")["id"] for i in range(5)]
    newest_first = list(reversed(ids))

    page = client.get(TRIPS_URL, params={"skip": 2, "limit": 2}).json()

    assert page["total"] == 5
    assert (page["skip"], page["limit"]) == (2, 2)
    assert [item["id"] for item in page["items"]] == newest_first[2:4]

    beyond = client.get(TRIPS_URL, params={"skip": 10}).json()
    assert beyond["items"] == [] and beyond["total"] == 5


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 101}, {"skip": -1}, {"q": "x" * 101}, {"limit": "dużo"}]
)
def test_list_trips_rejects_invalid_query(client: TestClient, params: dict) -> None:
    response = client.get(TRIPS_URL, params=params)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_list_trips_search_by_name_origin_and_destination(client: TestClient, create_trip) -> None:
    by_name = create_trip(name="Siłownia", origin="Dom", destination="Centrum")
    by_origin = create_trip(name="Trasa 1", origin="Dworzec Główny", destination="Lotnisko")
    by_destination = create_trip(name="Trasa 2", origin="Biuro", destination="Dworzec Wschodni")
    create_trip(name="Inna", origin="Park", destination="Szkoła")

    def search(q: str) -> set[int]:
        body = client.get(TRIPS_URL, params={"q": q}).json()
        assert body["total"] == len(body["items"])
        return {item["id"] for item in body["items"]}

    assert search("siłow") == {by_name["id"]}
    assert search("DWORZEC") == {by_origin["id"], by_destination["id"]}
    assert search("  lotnisko ") == {by_origin["id"]}
    assert search("brak-wyników") == set()
    assert len(search("   ")) == 4  # empty phrase = no filter


def test_list_trips_search_is_case_insensitive_for_polish_letters(
    client: TestClient, create_trip
) -> None:
    created = create_trip(name="Weekend", origin="Warszawa", destination="ŁÓDŹ Kaliska")

    for q in ("łódź", "ŁÓDŹ", "Łódź kal"):
        body = client.get(TRIPS_URL, params={"q": q}).json()
        assert [item["id"] for item in body["items"]] == [created["id"]], q


def test_list_trips_search_escapes_like_wildcards(client: TestClient, create_trip) -> None:
    create_trip(name="Trasa 100%")
    create_trip(name="Trasa 1000")

    body = client.get(TRIPS_URL, params={"q": "100%"}).json()

    assert [item["name"] for item in body["items"]] == ["Trasa 100%"]


# --- PUT /trips/{id} -------------------------------------------------------------------------


def test_replace_trip_overwrites_all_fields(client: TestClient, create_trip) -> None:
    created = create_trip()
    replacement = {
        "name": "Weekend",
        "origin": "Warszawa",
        "destination": "Łódź",
        "distance_km": 135,
        "passengers": 4,
        "priority": "fastest",
        "has_car": False,
        "allow_bike": True,
    }

    response = client.put(f"{TRIPS_URL}/{created['id']}", json=replacement)

    assert response.status_code == 200
    body = response.json()
    for key, value in replacement.items():
        assert body[key] == value
    assert body["notes"] is None  # an omitted field reverts to its default value
    assert body["id"] == created["id"]
    assert body["created_at"] == created["created_at"]
    assert client.get(f"{TRIPS_URL}/{created['id']}").json() == body


def test_replace_trip_requires_full_payload(client: TestClient, create_trip) -> None:
    created = create_trip()

    response = client.put(f"{TRIPS_URL}/{created['id']}", json={"name": "Tylko nazwa"})

    assert response.status_code == 422
    assert {"origin", "destination", "distance_km"} <= error_fields(response)


def test_replace_trip_rejects_invalid_data(client: TestClient, create_trip) -> None:
    created = create_trip()

    response = client.put(f"{TRIPS_URL}/{created['id']}", json=trip_payload(distance_km=-1))

    assert response.status_code == 422
    assert client.get(f"{TRIPS_URL}/{created['id']}").json()["distance_km"] == 12.5


def test_replace_missing_trip_returns_404(client: TestClient) -> None:
    response = client.put(f"{TRIPS_URL}/9999", json=trip_payload())

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


# --- PATCH /trips/{id} -----------------------------------------------------------------------


def test_patch_trip_updates_only_given_fields(client: TestClient, create_trip) -> None:
    created = create_trip()

    response = client.patch(
        f"{TRIPS_URL}/{created['id']}", json={"distance_km": 20, "priority": "greenest"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["distance_km"] == 20
    assert body["priority"] == "greenest"
    unchanged = {"name", "origin", "destination", "passengers", "has_car", "allow_bike", "notes"}
    for key in unchanged:
        assert body[key] == created[key]
    assert client.get(f"{TRIPS_URL}/{created['id']}").json() == body


def test_patch_trip_with_empty_body_changes_nothing(client: TestClient, create_trip) -> None:
    created = create_trip()

    response = client.patch(f"{TRIPS_URL}/{created['id']}", json={})

    assert response.status_code == 200
    body = response.json()
    for key in trip_payload():
        assert body[key] == created[key]


def test_patch_trip_can_clear_notes(client: TestClient, create_trip) -> None:
    created = create_trip()

    response = client.patch(f"{TRIPS_URL}/{created['id']}", json={"notes": None})

    assert response.status_code == 200
    assert response.json()["notes"] is None


@pytest.mark.parametrize("field", ["name", "origin", "distance_km", "priority", "has_car"])
def test_patch_trip_rejects_null_for_required_field(
    client: TestClient, create_trip, field: str
) -> None:
    created = create_trip()

    response = client.patch(f"{TRIPS_URL}/{created['id']}", json={field: None})

    assert response.status_code == 422
    assert field in error_fields(response)


@pytest.mark.parametrize(
    ("changes", "field"),
    [({"passengers": 9}, "passengers"), ({"distance_km": 0}, "distance_km"), ({"x": 1}, "x")],
)
def test_patch_trip_rejects_invalid_values(
    client: TestClient, create_trip, changes: dict, field: str
) -> None:
    created = create_trip()

    response = client.patch(f"{TRIPS_URL}/{created['id']}", json=changes)

    assert response.status_code == 422
    assert field in error_fields(response)


def test_patch_trip_validates_origin_against_stored_destination(
    client: TestClient, create_trip
) -> None:
    created = create_trip(origin="Dom", destination="Praca")

    response = client.patch(f"{TRIPS_URL}/{created['id']}", json={"origin": "praca"})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert client.get(f"{TRIPS_URL}/{created['id']}").json()["origin"] == "Dom"


def test_patch_trip_can_swap_origin_and_destination(client: TestClient, create_trip) -> None:
    created = create_trip(origin="Dom", destination="Praca")

    response = client.patch(
        f"{TRIPS_URL}/{created['id']}", json={"origin": "Praca", "destination": "Dom"}
    )

    assert response.status_code == 200
    assert (response.json()["origin"], response.json()["destination"]) == ("Praca", "Dom")


def test_patch_missing_trip_returns_404(client: TestClient) -> None:
    response = client.patch(f"{TRIPS_URL}/9999", json={"name": "X"})

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


# --- DELETE /trips/{id} ----------------------------------------------------------------------


def test_delete_trip_returns_204_and_removes_it(client: TestClient, create_trip) -> None:
    created = create_trip()
    other = create_trip(name="Zostaje")

    response = client.delete(f"{TRIPS_URL}/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"{TRIPS_URL}/{created['id']}").status_code == 404
    listing = client.get(TRIPS_URL).json()
    assert [item["id"] for item in listing["items"]] == [other["id"]]


def test_delete_missing_trip_returns_404(client: TestClient) -> None:
    response = client.delete(f"{TRIPS_URL}/9999")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_delete_trip_twice_returns_404_second_time(client: TestClient, create_trip) -> None:
    created = create_trip()

    assert client.delete(f"{TRIPS_URL}/{created['id']}").status_code == 204
    assert client.delete(f"{TRIPS_URL}/{created['id']}").status_code == 404


# --- database isolation ----------------------------------------------------------------------


def test_database_is_isolated_between_tests_part_1(client: TestClient, create_trip) -> None:
    create_trip()
    assert client.get(TRIPS_URL).json()["total"] == 1


def test_database_is_isolated_between_tests_part_2(client: TestClient) -> None:
    assert client.get(TRIPS_URL).json()["total"] == 0
