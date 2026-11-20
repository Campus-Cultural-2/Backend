from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_event_controller import admin_auth_headers, event_payload


def register_student(client: TestClient, index: int) -> dict[str, str]:
    email = f"aluno{index}@example.com"
    response = client.post(
        "/users/register",
        json={
            "role": "student",
            "email": email,
            "name": f"Aluno {index}",
            "last_name": "Teste",
            "is_active": True,
            "ra": f"20240{index}",
            "password": "secret",
            "birth_date": None,
        },
    )
    assert response.status_code == 201
    login = client.post("/users/login", json={"email": email, "password": "secret"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_event(client: TestClient, headers: dict[str, str], **fields: object) -> dict:
    response = client.post("/events", json={**event_payload(), **fields}, headers=headers)
    assert response.status_code == 201
    return response.json()


def subscribe(client: TestClient, event_id: int, headers: dict[str, str]) -> int:
    return client.post(f"/events/{event_id}/subscription", headers=headers).status_code


def test_event_without_limit_has_no_available_spots_count(client: TestClient) -> None:
    event = create_event(client, admin_auth_headers(client))

    assert event["max_participants"] is None
    assert event["subscribers_count"] == 0
    assert event["available_spots"] is None
    assert event["is_full"] is False


def test_create_event_stores_participant_limit(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    created = create_event(client, headers, max_participants=30)

    response = client.get(f"/events/{created['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["max_participants"] == 30
    assert response.json()["available_spots"] == 30
    assert response.json()["is_full"] is False


def test_create_event_rejects_non_positive_limit(client: TestClient) -> None:
    response = client.post(
        "/events",
        json={**event_payload(), "max_participants": 0},
        headers=admin_auth_headers(client),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_event_compares_subscribers_with_limit(client: TestClient) -> None:
    admin_headers = admin_auth_headers(client)
    event = create_event(client, admin_headers, max_participants=2)
    subscribe(client, event["id"], register_student(client, 1))

    response = client.get(f"/events/{event['id']}", headers=admin_headers)

    assert response.json()["subscribers_count"] == 1
    assert response.json()["available_spots"] == 1
    assert response.json()["is_full"] is False


def test_list_events_includes_subscribers_count(client: TestClient) -> None:
    admin_headers = admin_auth_headers(client)
    event = create_event(client, admin_headers, max_participants=5)
    create_event(client, admin_headers, name="Outro Evento")
    subscribe(client, event["id"], register_student(client, 1))
    subscribe(client, event["id"], register_student(client, 2))

    response = client.get("/events", headers=admin_headers)

    counts = {item["id"]: item["subscribers_count"] for item in response.json()}
    assert counts == {event["id"]: 2, event["id"] + 1: 0}


def test_subscribe_to_full_event_returns_conflict(client: TestClient) -> None:
    admin_headers = admin_auth_headers(client)
    event = create_event(client, admin_headers, max_participants=1)
    assert subscribe(client, event["id"], register_student(client, 1)) == 201

    response = client.post(
        f"/events/{event['id']}/subscription", headers=register_student(client, 2)
    )
    event_after = client.get(f"/events/{event['id']}", headers=admin_headers).json()

    assert response.status_code == 409
    assert response.json() == {
        "code": "event_full",
        "message": "Event has reached its participant limit",
        "details": {"event_id": event["id"], "max_participants": 1},
    }
    assert event_after["subscribers_count"] == 1
    assert event_after["available_spots"] == 0
    assert event_after["is_full"] is True


def test_unsubscribe_frees_a_spot(client: TestClient) -> None:
    admin_headers = admin_auth_headers(client)
    event = create_event(client, admin_headers, max_participants=1)
    first_student = register_student(client, 1)
    subscribe(client, event["id"], first_student)

    client.delete(f"/events/{event['id']}/subscription", headers=first_student)

    assert subscribe(client, event["id"], register_student(client, 2)) == 201


def test_update_event_changes_participant_limit(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    event = create_event(client, headers, max_participants=10)

    response = client.put(f"/events/{event['id']}", json={"max_participants": 20}, headers=headers)

    assert response.status_code == 200
    assert response.json()["max_participants"] == 20
    assert response.json()["available_spots"] == 20


def test_update_event_without_limit_field_keeps_current_limit(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    event = create_event(client, headers, max_participants=10)

    response = client.put(f"/events/{event['id']}", json={"name": "Novo Nome"}, headers=headers)

    assert response.json()["max_participants"] == 10


def test_update_event_with_null_limit_removes_limit(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    event = create_event(client, headers, max_participants=10)

    response = client.put(
        f"/events/{event['id']}", json={"max_participants": None}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["max_participants"] is None
    assert response.json()["available_spots"] is None


def test_update_event_rejects_limit_below_subscribers(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    event = create_event(client, headers, max_participants=5)
    subscribe(client, event["id"], register_student(client, 1))
    subscribe(client, event["id"], register_student(client, 2))

    response = client.put(f"/events/{event['id']}", json={"max_participants": 1}, headers=headers)

    assert response.status_code == 409
    assert response.json() == {
        "code": "event_limit_below_subscribers",
        "message": "Participant limit cannot be lower than the current number of subscribers",
        "details": {"max_participants": 1, "subscribers_count": 2},
    }


def test_update_event_accepts_limit_equal_to_subscribers(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    event = create_event(client, headers, max_participants=5)
    subscribe(client, event["id"], register_student(client, 1))

    response = client.put(f"/events/{event['id']}", json={"max_participants": 1}, headers=headers)

    assert response.status_code == 200
    assert response.json()["is_full"] is True
