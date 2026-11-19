from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_event_controller import admin_auth_headers
from tests.test_event_participant_limit import create_event, register_student, subscribe


def register_professor(client: TestClient, index: int) -> dict[str, str]:
    email = f"professor{index}@example.com"
    response = client.post(
        "/users/register",
        json={
            "role": "professor",
            "email": email,
            "name": f"Professor {index}",
            "last_name": "Teste",
            "is_active": True,
            "ra": None,
            "password": "secret",
            "birth_date": None,
        },
    )
    assert response.status_code == 201
    login = client.post("/users/login", json={"email": email, "password": "secret"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def list_subscribers(client: TestClient, event_id: int, headers: dict[str, str]):
    return client.get(f"/events/{event_id}/subscribers", headers=headers)


def test_owner_lists_subscribers_in_subscription_order(client: TestClient) -> None:
    owner_headers = register_professor(client, 1)
    event = create_event(client, owner_headers)
    for index in (3, 1, 2):
        assert subscribe(client, event["id"], register_student(client, index)) == 201

    response = list_subscribers(client, event["id"], owner_headers)

    assert response.status_code == 200
    subscribers = response.json()
    assert [subscriber["email"] for subscriber in subscribers] == [
        "aluno3@example.com",
        "aluno1@example.com",
        "aluno2@example.com",
    ]
    assert subscribers[0]["name"] == "Aluno 3"
    assert subscribers[0]["last_name"] == "Teste"
    assert subscribers[0]["ra"] == "202403"
    assert subscribers[0]["role"] == "student"
    assert isinstance(subscribers[0]["user_id"], int)
    assert subscribers[0]["subscribed_at"]


def test_subscribers_response_does_not_expose_private_fields(client: TestClient) -> None:
    owner_headers = register_professor(client, 1)
    event = create_event(client, owner_headers)
    subscribe(client, event["id"], register_student(client, 1))

    subscriber = list_subscribers(client, event["id"], owner_headers).json()[0]

    assert set(subscriber) == {
        "user_id",
        "name",
        "last_name",
        "email",
        "ra",
        "role",
        "subscribed_at",
    }


def test_admin_lists_subscribers_of_any_event(client: TestClient) -> None:
    event = create_event(client, register_professor(client, 1))
    subscribe(client, event["id"], register_student(client, 1))

    response = list_subscribers(client, event["id"], admin_auth_headers(client))

    assert response.status_code == 200
    assert [subscriber["email"] for subscriber in response.json()] == ["aluno1@example.com"]


def test_event_without_subscribers_returns_empty_list(client: TestClient) -> None:
    owner_headers = register_professor(client, 1)
    event = create_event(client, owner_headers)

    response = list_subscribers(client, event["id"], owner_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_unsubscribed_user_leaves_the_list(client: TestClient) -> None:
    owner_headers = register_professor(client, 1)
    event = create_event(client, owner_headers)
    student_headers = register_student(client, 1)
    subscribe(client, event["id"], student_headers)
    subscribe(client, event["id"], register_student(client, 2))

    client.delete(f"/events/{event['id']}/subscription", headers=student_headers)
    response = list_subscribers(client, event["id"], owner_headers)

    assert [subscriber["email"] for subscriber in response.json()] == ["aluno2@example.com"]


def test_subscribers_are_scoped_to_the_event(client: TestClient) -> None:
    owner_headers = register_professor(client, 1)
    event = create_event(client, owner_headers)
    other_event = create_event(client, owner_headers, name="Outro evento")
    subscribe(client, event["id"], register_student(client, 1))
    subscribe(client, other_event["id"], register_student(client, 2))

    response = list_subscribers(client, event["id"], owner_headers)

    assert [subscriber["email"] for subscriber in response.json()] == ["aluno1@example.com"]


def test_subscribed_student_cannot_list_subscribers(client: TestClient) -> None:
    event = create_event(client, register_professor(client, 1))
    student_headers = register_student(client, 1)
    subscribe(client, event["id"], student_headers)

    response = list_subscribers(client, event["id"], student_headers)

    assert response.status_code == 403
    assert response.json() == {
        "code": "permission_denied",
        "message": "Only the event owner or an admin can view its subscribers",
        "details": {"event_id": event["id"]},
    }


def test_other_professor_cannot_list_subscribers(client: TestClient) -> None:
    event = create_event(client, register_professor(client, 1))

    response = list_subscribers(client, event["id"], register_professor(client, 2))

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_list_subscribers_of_missing_event_returns_not_found(client: TestClient) -> None:
    response = list_subscribers(client, 999, admin_auth_headers(client))

    assert response.status_code == 404
    assert response.json()["code"] == "event_not_found"


def test_list_subscribers_without_token_returns_unauthorized(client: TestClient) -> None:
    event = create_event(client, register_professor(client, 1))

    response = client.get(f"/events/{event['id']}/subscribers")

    assert response.status_code == 401
