from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from tests.fakes import FakeImageStorage


def admin_auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/users/login",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def professor_auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/users/register",
        json={
            "role": "professor",
            "email": "maria@example.com",
            "name": "Maria",
            "last_name": "Silva",
            "is_active": True,
            "ra": None,
            "password": "strong-password",
            "birth_date": None,
        },
    )
    response = client.post(
        "/users/login",
        json={"email": "maria@example.com", "password": "strong-password"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def event_payload() -> dict[str, object]:
    return {
        "name": "Evento Legal",
        "description": "Um evento muito legal",
        "event_datetime": "2026-10-10T10:00:00",
        "event_location": "Laboratório de Informática",
    }


def test_create_event_returns_created(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    payload = event_payload()

    response = client.post("/events", json=payload, headers=headers)

    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert data["description"] == payload["description"]
    assert data["event_datetime"] == payload["event_datetime"]
    assert data["event_location"] == payload["event_location"]
    assert data["name"] == payload["name"]


def test_list_events_returns_list_of_events(client: TestClient) -> None:
    headers = admin_auth_headers(client)

    client.post("/events", json=event_payload(), headers=headers)

    response = client.get("/events", headers=headers)

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


def test_get_event_by_id_returns_event(client: TestClient) -> None:
    headers = admin_auth_headers(client)

    created_event = client.post("/events", json=event_payload(), headers=headers).json()

    response = client.get(f"/events/{created_event['id']}", headers=headers)

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == created_event["id"]
    assert data["name"] == created_event["name"]
    assert data["event_datetime"] == created_event["event_datetime"]
    assert data["event_location"] == created_event["event_location"]


def test_update_event_returns_updated_event(client: TestClient) -> None:
    headers = admin_auth_headers(client)

    created_event = client.post("/events", json=event_payload(), headers=headers).json()

    update_payload = {
        "event_datetime": "2026-12-25T18:00:00",
        "name": "novo evento",
        "event_location": "Auditório Principal",
        "description": "Evento atualizado",
    }

    response = client.put(
        f"/events/{created_event['id']}",
        json=update_payload,
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == created_event["id"]
    assert data["name"] == update_payload["name"]
    assert data["event_datetime"].startswith(update_payload["event_datetime"])
    assert data["event_location"] == update_payload["event_location"]
    assert data["description"] == update_payload["description"]


def test_delete_event_removes_resource(client: TestClient) -> None:
    headers = admin_auth_headers(client)

    created_event = client.post("/events", json=event_payload(), headers=headers).json()
    event_id = created_event["id"]

    delete_response = client.delete(f"/events/{event_id}", headers=headers)
    assert delete_response.status_code == 204

    get_response = client.get(f"/events/{event_id}", headers=headers)
    assert get_response.status_code == 404


def test_list_events_without_token_returns_unauthorized(client: TestClient) -> None:
    response = client.get("/events")
    assert response.status_code == 401


def test_get_event_without_token_returns_unauthorized(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    created_event = client.post("/events", json=event_payload(), headers=headers).json()

    response = client.get(f"/events/{created_event['id']}")

    assert response.status_code == 401


PNG_BYTES = b"\x89PNG\r\n\x1a\nevent-banner"
PNG_BASE64 = base64.b64encode(PNG_BYTES).decode()


def test_create_event_uploads_image_and_returns_its_url(
    client: TestClient, image_storage: FakeImageStorage
) -> None:
    headers = admin_auth_headers(client)

    response = client.post(
        "/events", json={**event_payload(), "image": PNG_BASE64}, headers=headers
    )

    assert response.status_code == 201
    assert image_storage.uploads == [(PNG_BYTES, "campus_cultural/events")]
    assert response.json()["image"] == (
        "https://res.cloudinary.com/test/image/upload/campus_cultural/events/1.png"
    )

    get_response = client.get(f"/events/{response.json()['id']}", headers=headers)
    assert get_response.json()["image"] == response.json()["image"]


def test_create_event_accepts_image_as_data_uri(
    client: TestClient, image_storage: FakeImageStorage
) -> None:
    response = client.post(
        "/events",
        json={**event_payload(), "image": f"data:image/png;base64,{PNG_BASE64}"},
        headers=admin_auth_headers(client),
    )

    assert response.status_code == 201
    assert image_storage.uploads == [(PNG_BYTES, "campus_cultural/events")]


def test_create_event_without_image_does_not_upload(
    client: TestClient, image_storage: FakeImageStorage
) -> None:
    response = client.post("/events", json=event_payload(), headers=admin_auth_headers(client))

    assert response.status_code == 201
    assert response.json()["image"] is None
    assert image_storage.uploads == []


def test_create_event_with_invalid_base64_image_returns_bad_request(
    client: TestClient, image_storage: FakeImageStorage
) -> None:
    response = client.post(
        "/events",
        json={**event_payload(), "image": "isto nao e base64!"},
        headers=admin_auth_headers(client),
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "invalid_image",
        "message": "Image must be a base64 encoded file",
    }
    assert image_storage.uploads == []


def test_update_event_without_image_field_keeps_current_image(
    client: TestClient, image_storage: FakeImageStorage
) -> None:
    headers = admin_auth_headers(client)
    created_event = client.post(
        "/events", json={**event_payload(), "image": PNG_BASE64}, headers=headers
    ).json()

    response = client.put(
        f"/events/{created_event['id']}", json={"name": "Outro nome"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["image"] == created_event["image"]
    assert len(image_storage.uploads) == 1
    assert image_storage.deleted == []


def test_update_event_with_new_image_replaces_it_and_deletes_the_old_one(
    client: TestClient, image_storage: FakeImageStorage
) -> None:
    headers = admin_auth_headers(client)
    created_event = client.post(
        "/events", json={**event_payload(), "image": PNG_BASE64}, headers=headers
    ).json()

    response = client.put(
        f"/events/{created_event['id']}", json={"image": PNG_BASE64}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["image"] == (
        "https://res.cloudinary.com/test/image/upload/campus_cultural/events/2.png"
    )
    assert image_storage.deleted == ["campus_cultural/events/1"]


def test_update_event_with_null_image_removes_it_from_storage(
    client: TestClient, image_storage: FakeImageStorage
) -> None:
    headers = admin_auth_headers(client)
    created_event = client.post(
        "/events", json={**event_payload(), "image": PNG_BASE64}, headers=headers
    ).json()

    response = client.put(f"/events/{created_event['id']}", json={"image": None}, headers=headers)

    assert response.status_code == 200
    assert response.json()["image"] is None
    assert image_storage.deleted == ["campus_cultural/events/1"]

    get_response = client.get(f"/events/{created_event['id']}", headers=headers)
    assert get_response.json()["image"] is None


def test_update_event_of_another_user_does_not_delete_its_image(
    client: TestClient, image_storage: FakeImageStorage
) -> None:
    created_event = client.post(
        "/events",
        json={**event_payload(), "image": PNG_BASE64},
        headers=admin_auth_headers(client),
    ).json()

    response = client.put(
        f"/events/{created_event['id']}",
        json={"image": None},
        headers=professor_auth_headers(client),
    )

    assert response.status_code == 404
    assert image_storage.deleted == []


def test_delete_event_deletes_its_image_from_storage(
    client: TestClient, image_storage: FakeImageStorage
) -> None:
    headers = admin_auth_headers(client)
    created_event = client.post(
        "/events", json={**event_payload(), "image": PNG_BASE64}, headers=headers
    ).json()

    response = client.delete(f"/events/{created_event['id']}", headers=headers)

    assert response.status_code == 204
    assert image_storage.deleted == ["campus_cultural/events/1"]


def test_delete_event_without_image_does_not_touch_storage(
    client: TestClient, image_storage: FakeImageStorage
) -> None:
    headers = admin_auth_headers(client)
    created_event = client.post("/events", json=event_payload(), headers=headers).json()

    response = client.delete(f"/events/{created_event['id']}", headers=headers)

    assert response.status_code == 204
    assert image_storage.deleted == []
