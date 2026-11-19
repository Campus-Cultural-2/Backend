from __future__ import annotations

from fastapi.testclient import TestClient


def admin_auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/users/login",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def register_ana(client: TestClient) -> dict[str, str]:
    """Register a student (Ana) and return her auth headers."""
    register_response = client.post(
        "/users/register",
        json={
            "role": "student",
            "email": "ana@example.com",
            "name": "Ana",
            "last_name": "Silva",
            "is_active": True,
            "ra": "1234567",
            "password": "ana12345",
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/users/login",
        json={"email": "ana@example.com", "password": "ana12345"},
    )
    assert login_response.status_code == 200
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


def event_payload(name: str = "Evento Legal") -> dict[str, object]:
    return {
        "name": name,
        "description": "Um evento muito legal",
        "event_datetime": "2026-10-10T10:00:00",
        "event_end_datetime": "2026-10-10T12:00:00",
        "event_location": "Laboratório de Informática",
    }


def create_event(client: TestClient, headers: dict[str, str], name: str = "Evento Legal") -> int:
    response = client.post("/events", json=event_payload(name), headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


# --- subscribe ---------------------------------------------------------------


def test_subscribe_to_event_returns_created(client: TestClient) -> None:
    admin_headers = admin_auth_headers(client)
    ana_headers = register_ana(client)
    event_id = create_event(client, admin_headers)

    response = client.post(f"/events/{event_id}/subscription", headers=ana_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["event_id"] == event_id
    assert "id" in data
    assert "created_at" in data


def test_subscribe_twice_returns_conflict(client: TestClient) -> None:
    admin_headers = admin_auth_headers(client)
    ana_headers = register_ana(client)
    event_id = create_event(client, admin_headers)

    first = client.post(f"/events/{event_id}/subscription", headers=ana_headers)
    assert first.status_code == 201

    second = client.post(f"/events/{event_id}/subscription", headers=ana_headers)
    assert second.status_code == 409
    assert second.json()["code"] == "event_already_subscribed"


def test_subscribe_to_missing_event_returns_not_found(client: TestClient) -> None:
    ana_headers = register_ana(client)

    response = client.post("/events/999999/subscription", headers=ana_headers)

    assert response.status_code == 404
    assert response.json()["code"] == "event_not_found"


def test_subscribe_without_token_returns_unauthorized(client: TestClient) -> None:
    admin_headers = admin_auth_headers(client)
    event_id = create_event(client, admin_headers)

    response = client.post(f"/events/{event_id}/subscription")

    assert response.status_code == 401


# --- unsubscribe -------------------------------------------------------------


def test_unsubscribe_removes_subscription(client: TestClient) -> None:
    admin_headers = admin_auth_headers(client)
    ana_headers = register_ana(client)
    event_id = create_event(client, admin_headers)

    client.post(f"/events/{event_id}/subscription", headers=ana_headers)

    response = client.delete(f"/events/{event_id}/subscription", headers=ana_headers)
    assert response.status_code == 204

    my_events = client.get("/events/subscriptions/me", headers=ana_headers)
    assert my_events.status_code == 200
    assert my_events.json() == []


def test_unsubscribe_when_not_subscribed_returns_not_found(client: TestClient) -> None:
    admin_headers = admin_auth_headers(client)
    ana_headers = register_ana(client)
    event_id = create_event(client, admin_headers)

    response = client.delete(f"/events/{event_id}/subscription", headers=ana_headers)

    assert response.status_code == 404
    assert response.json()["code"] == "event_subscription_not_found"


# --- list my subscriptions (Ana's story) -------------------------------------


def test_list_my_subscriptions_returns_only_subscribed_events(client: TestClient) -> None:
    admin_headers = admin_auth_headers(client)
    ana_headers = register_ana(client)

    event_a = create_event(client, admin_headers, name="Show de Jazz")
    event_b = create_event(client, admin_headers, name="Feira de Livros")
    create_event(client, admin_headers, name="Evento que Ana ignora")

    client.post(f"/events/{event_a}/subscription", headers=ana_headers)
    client.post(f"/events/{event_b}/subscription", headers=ana_headers)

    response = client.get("/events/subscriptions/me", headers=ana_headers)

    assert response.status_code == 200
    subscribed_ids = {event["id"] for event in response.json()}
    assert subscribed_ids == {event_a, event_b}


def test_list_my_subscriptions_is_scoped_to_current_user(client: TestClient) -> None:
    admin_headers = admin_auth_headers(client)
    ana_headers = register_ana(client)
    event_id = create_event(client, admin_headers)

    # Admin subscribes, Ana does not.
    client.post(f"/events/{event_id}/subscription", headers=admin_headers)

    response = client.get("/events/subscriptions/me", headers=ana_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_list_my_subscriptions_without_token_returns_unauthorized(client: TestClient) -> None:
    response = client.get("/events/subscriptions/me")

    assert response.status_code == 401
