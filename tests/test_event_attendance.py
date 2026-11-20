from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from api.features.attendance import attendance_service
from tests.test_event_controller import admin_auth_headers, event_payload, professor_auth_headers
from tests.test_subscription_controller import register_ana


def _iso(moment: datetime) -> str:
    return moment.replace(tzinfo=None).isoformat()


def running_event(**fields: object) -> dict[str, object]:
    """Evento que comecou ha uma hora e termina daqui a uma hora."""
    now = datetime.now(UTC)
    return {
        **event_payload(),
        "event_datetime": _iso(now - timedelta(hours=1)),
        "event_end_datetime": _iso(now + timedelta(hours=1)),
        **fields,
    }


def create_event(client: TestClient, headers: dict[str, str], **fields: object) -> dict:
    response = client.post("/events", json=running_event(**fields), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def subscribe(client: TestClient, headers: dict[str, str], event_id: int) -> dict:
    response = client.post(f"/events/{event_id}/subscription", headers=headers)
    assert response.status_code == 201
    return response.json()


def ana_id(client: TestClient, headers: dict[str, str]) -> int:
    token = headers["Authorization"].removeprefix("Bearer ")
    return int(jwt.decode(token, options={"verify_signature": False})["sub"])


# --- horario de encerramento -------------------------------------------------


def test_event_stores_end_datetime(client: TestClient) -> None:
    event = create_event(client, admin_auth_headers(client))

    response = client.get(f"/events/{event['id']}", headers=admin_auth_headers(client))

    assert response.json()["event_end_datetime"] == event["event_end_datetime"]
    assert response.json()["attendance_mode"] == "none"


def test_create_event_requires_end_datetime(client: TestClient) -> None:
    payload = event_payload()
    del payload["event_end_datetime"]

    response = client.post("/events", json=payload, headers=admin_auth_headers(client))

    assert response.status_code == 422


@pytest.mark.parametrize("end", ["2026-10-10T10:00:00", "2026-10-10T09:00:00"])
def test_create_event_rejects_end_not_after_start(client: TestClient, end: str) -> None:
    response = client.post(
        "/events",
        json={**event_payload(), "event_end_datetime": end},
        headers=admin_auth_headers(client),
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_event_period"


def test_update_event_rejects_start_after_current_end(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    event = create_event(client, headers)

    response = client.put(
        f"/events/{event['id']}",
        json={"event_datetime": _iso(datetime.now(UTC) + timedelta(days=5))},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_event_period"


def test_update_event_changes_attendance_mode(client: TestClient) -> None:
    headers = admin_auth_headers(client)
    event = create_event(client, headers)

    response = client.put(
        f"/events/{event['id']}", json={"attendance_mode": "student"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["attendance_mode"] == "student"


# --- sem confirmacao ---------------------------------------------------------


def test_event_without_confirmation_counts_everyone_as_present(client: TestClient) -> None:
    admin = admin_auth_headers(client)
    ana = register_ana(client)
    event = create_event(client, admin)
    subscribe(client, ana, event["id"])

    response = client.get(f"/events/{event['id']}/participants", headers=admin)

    assert response.status_code == 200
    assert [p["attended"] for p in response.json()] == [True]
    assert response.json()[0]["name"] == "Ana"


def test_event_code_requires_student_mode(client: TestClient) -> None:
    admin = admin_auth_headers(client)
    event = create_event(client, admin)

    response = client.get(f"/events/{event['id']}/attendance/code", headers=admin)

    assert response.status_code == 409
    assert response.json()["code"] == "attendance_mode_mismatch"


# --- permissoes --------------------------------------------------------------


def test_only_owner_or_admin_can_list_participants(client: TestClient) -> None:
    professor = professor_auth_headers(client)
    ana = register_ana(client)
    event = create_event(client, professor, attendance_mode="professor")

    owner = client.get(f"/events/{event['id']}/participants", headers=professor)
    admin = client.get(f"/events/{event['id']}/participants", headers=admin_auth_headers(client))
    student = client.get(f"/events/{event['id']}/participants", headers=ana)

    assert owner.status_code == 200
    assert admin.status_code == 200
    assert student.status_code == 403
    assert student.json()["code"] == "permission_denied"


# --- confirmacao pelo professor ----------------------------------------------


def test_professor_confirms_presence_manually(client: TestClient) -> None:
    professor = professor_auth_headers(client)
    ana = register_ana(client)
    event = create_event(client, professor, attendance_mode="professor")
    subscribe(client, ana, event["id"])
    user_id = ana_id(client, ana)
    url = f"/events/{event['id']}/participants/{user_id}/attendance"

    listed = client.get(f"/events/{event['id']}/participants", headers=professor).json()
    assert listed[0]["attended"] is False

    confirmed = client.put(url, json={"present": True}, headers=professor)
    assert confirmed.status_code == 200
    assert confirmed.json()["attended"] is True
    assert confirmed.json()["checked_in_at"] is not None

    removed = client.put(url, json={"present": False}, headers=professor)
    assert removed.json()["attended"] is False
    assert removed.json()["checked_in_at"] is None


def test_manual_confirmation_is_blocked_for_other_modes(client: TestClient) -> None:
    admin = admin_auth_headers(client)
    ana = register_ana(client)
    event = create_event(client, admin, attendance_mode="student")
    subscribe(client, ana, event["id"])

    response = client.put(
        f"/events/{event['id']}/participants/{ana_id(client, ana)}/attendance",
        json={"present": True},
        headers=admin,
    )

    assert response.status_code == 409
    assert response.json()["code"] == "attendance_mode_mismatch"


def test_manual_confirmation_requires_subscription(client: TestClient) -> None:
    admin = admin_auth_headers(client)
    ana = register_ana(client)
    event = create_event(client, admin, attendance_mode="professor")

    response = client.put(
        f"/events/{event['id']}/participants/{ana_id(client, ana)}/attendance",
        json={"present": True},
        headers=admin,
    )

    assert response.status_code == 404
    assert response.json()["code"] == "event_subscription_not_found"


def test_confirmation_is_blocked_before_event_starts(client: TestClient) -> None:
    admin = admin_auth_headers(client)
    ana = register_ana(client)
    future = datetime.now(UTC) + timedelta(days=2)
    event = create_event(
        client,
        admin,
        attendance_mode="professor",
        event_datetime=_iso(future),
        event_end_datetime=_iso(future + timedelta(hours=2)),
    )
    subscribe(client, ana, event["id"])

    response = client.put(
        f"/events/{event['id']}/participants/{ana_id(client, ana)}/attendance",
        json={"present": True},
        headers=admin,
    )

    assert response.status_code == 409
    assert response.json()["code"] == "attendance_window_closed"


def test_professor_scans_student_qr_code(client: TestClient) -> None:
    professor = professor_auth_headers(client)
    ana = register_ana(client)
    event = create_event(client, professor, attendance_mode="professor")
    subscription = subscribe(client, ana, event["id"])
    code = subscription["attendance_code"]
    assert code

    first = client.post(
        f"/events/{event['id']}/attendance/scan", json={"code": code}, headers=professor
    )
    second = client.post(
        f"/events/{event['id']}/attendance/scan", json={"code": code}, headers=professor
    )

    assert first.status_code == 200
    assert first.json()["attended"] is True
    # Ler de novo nao muda a hora da primeira leitura.
    assert second.json()["checked_in_at"] == first.json()["checked_in_at"]
    mine = client.get(f"/events/{event['id']}/subscription", headers=ana).json()
    assert mine["checked_in_at"] == first.json()["checked_in_at"]
    assert mine["attendance_code"] == code


def test_scan_rejects_forged_or_foreign_code(client: TestClient) -> None:
    professor = professor_auth_headers(client)
    ana = register_ana(client)
    event = create_event(client, professor, attendance_mode="professor")
    other_event = create_event(client, professor, attendance_mode="professor")
    code = subscribe(client, ana, event["id"])["attendance_code"]
    user_id = code.split(".")[0]

    for bad_code in ("lixo", f"{user_id}.aaaaaaaaaaaaaaaa", code):
        response = client.post(
            f"/events/{other_event['id']}/attendance/scan",
            json={"code": bad_code},
            headers=professor,
        )
        assert response.status_code == 400
        assert response.json()["code"] == "invalid_attendance_code"


def test_attendance_code_is_only_given_in_professor_mode(client: TestClient) -> None:
    admin = admin_auth_headers(client)
    ana = register_ana(client)
    event = create_event(client, admin, attendance_mode="student")

    subscription = subscribe(client, ana, event["id"])

    assert subscription["attendance_code"] is None
    assert subscription["checked_in_at"] is None


# --- confirmacao pelo aluno --------------------------------------------------


def test_student_checks_in_with_event_code(client: TestClient) -> None:
    professor = professor_auth_headers(client)
    ana = register_ana(client)
    event = create_event(client, professor, attendance_mode="student")
    subscribe(client, ana, event["id"])
    code = client.get(f"/events/{event['id']}/attendance/code", headers=professor).json()["code"]

    response = client.post(
        f"/events/{event['id']}/attendance/check-in", json={"code": code.lower()}, headers=ana
    )

    assert response.status_code == 200
    assert response.json()["attended"] is True
    listed = client.get(f"/events/{event['id']}/participants", headers=professor).json()
    assert listed[0]["attended"] is True


def test_student_check_in_rejects_wrong_code(client: TestClient) -> None:
    admin = admin_auth_headers(client)
    ana = register_ana(client)
    event = create_event(client, admin, attendance_mode="student")
    subscribe(client, ana, event["id"])

    response = client.post(
        f"/events/{event['id']}/attendance/check-in", json={"code": "ZZZZZZZZ"}, headers=ana
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_attendance_code"


def test_student_check_in_requires_subscription(client: TestClient) -> None:
    admin = admin_auth_headers(client)
    ana = register_ana(client)
    event = create_event(client, admin, attendance_mode="student")
    code = client.get(f"/events/{event['id']}/attendance/code", headers=admin).json()["code"]

    response = client.post(
        f"/events/{event['id']}/attendance/check-in", json={"code": code}, headers=ana
    )

    assert response.status_code == 404
    assert response.json()["code"] == "event_subscription_not_found"


def test_student_check_in_only_while_event_is_happening(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = admin_auth_headers(client)
    ana = register_ana(client)
    event = create_event(client, admin, attendance_mode="student")
    subscribe(client, ana, event["id"])
    code = client.get(f"/events/{event['id']}/attendance/code", headers=admin).json()["code"]

    # Depois do encerramento do evento.
    monkeypatch.setattr(attendance_service, "_now", lambda: datetime.now(UTC) + timedelta(hours=3))
    response = client.post(
        f"/events/{event['id']}/attendance/check-in", json={"code": code}, headers=ana
    )

    assert response.status_code == 409
    assert response.json()["code"] == "attendance_window_closed"


def test_student_check_in_is_blocked_in_professor_mode(client: TestClient) -> None:
    admin = admin_auth_headers(client)
    ana = register_ana(client)
    event = create_event(client, admin, attendance_mode="professor")
    subscribe(client, ana, event["id"])

    response = client.post(
        f"/events/{event['id']}/attendance/check-in", json={"code": "ABCDEFGH"}, headers=ana
    )

    assert response.status_code == 409
    assert response.json()["code"] == "attendance_mode_mismatch"
