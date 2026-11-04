from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.test_event_controller import admin_auth_headers, event_payload


def certificate_fields(**changes: object) -> dict[str, object]:
    return {
        "has_certificate": True,
        "workload_hours": 4,
        "hours_group": "group_1",
        **changes,
    }


def create_event(client: TestClient, headers: dict[str, str], **fields: object) -> dict:
    response = client.post("/events", json={**event_payload(), **fields}, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_event_without_certificate_info_defaults_to_no_certificate(client: TestClient) -> None:
    event = create_event(client, admin_auth_headers(client))

    assert event["has_certificate"] is False
    assert event["workload_hours"] is None
    assert event["hours_group"] is None


def test_create_event_stores_certificate_info(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    created = create_event(client, headers, **certificate_fields())

    response = client.get(f"/events/{created['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json()["has_certificate"] is True
    assert response.json()["workload_hours"] == 4
    assert response.json()["hours_group"] == "group_1"


def test_list_events_includes_certificate_info(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    create_event(client, headers, **certificate_fields(hours_group="group_3"))

    response = client.get("/events", headers=headers)

    assert response.json()[0]["hours_group"] == "group_3"


@pytest.mark.parametrize(
    "fields",
    [
        {"has_certificate": True},
        {"has_certificate": True, "workload_hours": 4},
        {"has_certificate": True, "hours_group": "group_1"},
    ],
)
def test_create_event_with_certificate_requires_workload_and_group(
    client: TestClient, fields: dict[str, object]
) -> None:
    response = client.post(
        "/events", json={**event_payload(), **fields}, headers=admin_auth_headers(client)
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "invalid_certificate_info",
        "message": "Events with certificate must have workload_hours and hours_group",
    }


def test_create_event_without_certificate_rejects_workload(client: TestClient) -> None:
    response = client.post(
        "/events",
        json={**event_payload(), **certificate_fields(has_certificate=False)},
        headers=admin_auth_headers(client),
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_certificate_info"


@pytest.mark.parametrize(
    "fields",
    [
        certificate_fields(workload_hours=0),
        certificate_fields(hours_group="group_9"),
    ],
)
def test_create_event_rejects_invalid_certificate_values(
    client: TestClient, fields: dict[str, object]
) -> None:
    response = client.post(
        "/events", json={**event_payload(), **fields}, headers=admin_auth_headers(client)
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_update_event_adds_certificate(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    event = create_event(client, headers)

    response = client.put(f"/events/{event['id']}", json=certificate_fields(), headers=headers)

    assert response.status_code == 200
    assert response.json()["has_certificate"] is True
    assert response.json()["workload_hours"] == 4


def test_update_event_changes_only_workload(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    event = create_event(client, headers, **certificate_fields())

    response = client.put(f"/events/{event['id']}", json={"workload_hours": 8}, headers=headers)

    assert response.status_code == 200
    assert response.json()["workload_hours"] == 8
    assert response.json()["hours_group"] == "group_1"


def test_update_event_without_certificate_fields_keeps_them(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    event = create_event(client, headers, **certificate_fields())

    response = client.put(f"/events/{event['id']}", json={"name": "Novo Nome"}, headers=headers)

    assert response.json()["has_certificate"] is True
    assert response.json()["workload_hours"] == 4
    assert response.json()["hours_group"] == "group_1"


def test_update_event_removing_certificate_clears_workload_and_group(
    client: TestClient,
) -> None:
    headers = admin_auth_headers(client)
    event = create_event(client, headers, **certificate_fields())

    response = client.put(
        f"/events/{event['id']}", json={"has_certificate": False}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["has_certificate"] is False
    assert response.json()["workload_hours"] is None
    assert response.json()["hours_group"] is None


def test_update_event_cannot_add_certificate_without_workload(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    event = create_event(client, headers)

    response = client.put(f"/events/{event['id']}", json={"has_certificate": True}, headers=headers)

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_certificate_info"


def test_update_event_cannot_clear_workload_of_event_with_certificate(
    client: TestClient,
) -> None:
    headers = admin_auth_headers(client)
    event = create_event(client, headers, **certificate_fields())

    response = client.put(f"/events/{event['id']}", json={"workload_hours": None}, headers=headers)
    event_after = client.get(f"/events/{event['id']}", headers=headers).json()

    assert response.status_code == 400
    assert event_after["workload_hours"] == 4


def test_update_event_rejects_null_has_certificate(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    event = create_event(client, headers)

    response = client.put(f"/events/{event['id']}", json={"has_certificate": None}, headers=headers)

    assert response.status_code == 400
    assert response.json()["message"] == "has_certificate cannot be null"
