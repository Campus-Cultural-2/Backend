from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from api.features.user.user import User, UserRole
from tests.test_user_controller import admin_auth_headers, login_headers, student_payload


def professor_payload() -> dict[str, object]:
    return {
        "role": "professor",
        "email": "maria@example.com",
        "name": "Maria",
        "last_name": "Silva",
        "is_active": True,
        "ra": None,
        "password": "strong-password",
        "birth_date": None,
    }


def update_payload(user: dict[str, object], **changes: object) -> dict[str, object]:
    fields = ("role", "email", "name", "last_name", "is_active", "ra", "birth_date")
    return {**{field: user[field] for field in fields}, **changes}


def register(client: TestClient, payload: dict[str, object]) -> dict[str, object]:
    response = client.post("/users/register", json=payload)
    assert response.status_code == 201
    return response.json()


def student_headers(client: TestClient) -> dict[str, str]:
    return login_headers(client, "diego@example.com", "secret")


def professor_headers(client: TestClient) -> dict[str, str]:
    return login_headers(client, "maria@example.com", "strong-password")


def create_second_admin(client: TestClient) -> int:
    # Admins nao podem ser registrados pela API, entao o teste cria direto no banco.
    async def create() -> int:
        async with client.app.state.database_manager.session_factory() as session:
            user = User(
                role=UserRole.ADMIN,
                password_hash="unused",
                email="second-admin@example.com",
                name="Segundo",
                last_name="Admin",
                is_active=True,
            )
            session.add(user)
            await session.commit()
            return user.id

    return asyncio.run(create())


def test_list_users_is_forbidden_for_students(client: TestClient) -> None:
    register(client, student_payload())

    response = client.get("/users", headers=student_headers(client))

    assert response.status_code == 403
    assert response.json() == {
        "code": "permission_denied",
        "message": "Only professors and admins can manage users",
    }


def test_list_users_is_allowed_for_professors(client: TestClient) -> None:
    register(client, professor_payload())

    response = client.get("/users", headers=professor_headers(client))

    assert response.status_code == 200
    assert [user["email"] for user in response.json()] == [
        "admin@example.com",
        "maria@example.com",
    ]


def test_list_users_filters_by_role_and_status(client: TestClient) -> None:
    register(client, student_payload())
    register(client, professor_payload())
    register(
        client,
        {**student_payload(), "email": "ana@example.com", "ra": "2024002", "is_active": False},
    )
    headers = admin_auth_headers(client)

    students = client.get("/users", headers=headers, params={"role": "student"})
    inactive = client.get("/users", headers=headers, params={"is_active": False})

    assert [user["email"] for user in students.json()] == [
        "diego@example.com",
        "ana@example.com",
    ]
    assert [user["email"] for user in inactive.json()] == ["ana@example.com"]


def test_student_can_view_own_user(client: TestClient) -> None:
    student = register(client, student_payload())

    response = client.get(f"/users/{student['id']}", headers=student_headers(client))

    assert response.status_code == 200
    assert response.json() == student


def test_student_cannot_view_other_user(client: TestClient) -> None:
    register(client, student_payload())
    professor = register(client, professor_payload())

    response = client.get(f"/users/{professor['id']}", headers=student_headers(client))

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_professor_can_view_other_user(client: TestClient) -> None:
    student = register(client, student_payload())
    register(client, professor_payload())

    response = client.get(f"/users/{student['id']}", headers=professor_headers(client))

    assert response.status_code == 200
    assert response.json() == student


def test_student_can_update_own_profile(client: TestClient) -> None:
    student = register(client, student_payload())

    response = client.put(
        f"/users/{student['id']}",
        headers=student_headers(client),
        json=update_payload(student, name="Diego Novo", password="secret"),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Diego Novo"


def test_student_cannot_change_own_role(client: TestClient) -> None:
    student = register(client, student_payload())

    response = client.put(
        f"/users/{student['id']}",
        headers=student_headers(client),
        json=update_payload(student, role="professor", ra=None),
    )

    assert response.status_code == 403
    assert response.json() == {
        "code": "permission_denied",
        "message": "Users cannot change their own role or status",
    }


def test_student_cannot_update_other_user(client: TestClient) -> None:
    register(client, student_payload())
    professor = register(client, professor_payload())

    response = client.put(
        f"/users/{professor['id']}",
        headers=student_headers(client),
        json=update_payload(professor, name="Invadido"),
    )

    assert response.status_code == 403


def test_professor_updates_user_without_changing_password(client: TestClient) -> None:
    student = register(client, student_payload())
    register(client, professor_payload())

    response = client.put(
        f"/users/{student['id']}",
        headers=professor_headers(client),
        json=update_payload(student, name="Diego Editado"),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Diego Editado"
    # A senha antiga continua valendo.
    assert student_headers(client)


def test_professor_cannot_promote_user_to_admin(client: TestClient) -> None:
    student = register(client, student_payload())
    register(client, professor_payload())

    response = client.put(
        f"/users/{student['id']}",
        headers=professor_headers(client),
        json=update_payload(student, role="admin", ra=None),
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Only admins can manage admin users"


def test_professor_cannot_update_admin(client: TestClient) -> None:
    register(client, professor_payload())
    admin = client.get("/users/1", headers=admin_auth_headers(client)).json()

    response = client.put(
        "/users/1",
        headers=professor_headers(client),
        json=update_payload(admin, name="Hackeado"),
    )

    assert response.status_code == 403


def test_admin_can_promote_user_to_admin(client: TestClient) -> None:
    professor = register(client, professor_payload())

    response = client.put(
        f"/users/{professor['id']}",
        headers=admin_auth_headers(client),
        json=update_payload(professor, role="admin"),
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_professor_deactivates_and_reactivates_student(client: TestClient) -> None:
    student = register(client, student_payload())
    register(client, professor_payload())
    headers = professor_headers(client)

    deactivated = client.patch(
        f"/users/{student['id']}/status", headers=headers, json={"is_active": False}
    )
    login_while_inactive = client.post(
        "/users/login", json={"email": "diego@example.com", "password": "secret"}
    )
    activated = client.patch(
        f"/users/{student['id']}/status", headers=headers, json={"is_active": True}
    )

    assert deactivated.status_code == 200
    assert deactivated.json() == {**student, "is_active": False}
    assert login_while_inactive.status_code == 401
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True
    assert student_headers(client)


def test_deactivated_user_token_stops_working(client: TestClient) -> None:
    student = register(client, student_payload())
    headers = student_headers(client)

    client.patch(
        f"/users/{student['id']}/status",
        headers=admin_auth_headers(client),
        json={"is_active": False},
    )
    response = client.get(f"/users/{student['id']}", headers=headers)

    assert response.status_code == 401
    assert response.json()["message"] == "Inactive user"


def test_student_cannot_change_user_status(client: TestClient) -> None:
    register(client, student_payload())
    professor = register(client, professor_payload())

    response = client.patch(
        f"/users/{professor['id']}/status",
        headers=student_headers(client),
        json={"is_active": False},
    )

    assert response.status_code == 403


def test_user_cannot_deactivate_itself(client: TestClient) -> None:
    response = client.patch(
        "/users/1/status", headers=admin_auth_headers(client), json={"is_active": False}
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Users cannot manage their own account"


def test_professor_cannot_deactivate_admin(client: TestClient) -> None:
    register(client, professor_payload())

    response = client.patch(
        "/users/1/status", headers=professor_headers(client), json={"is_active": False}
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Only admins can manage admin users"


def test_admin_can_deactivate_other_admin(client: TestClient) -> None:
    other_admin_id = create_second_admin(client)

    response = client.patch(
        f"/users/{other_admin_id}/status",
        headers=admin_auth_headers(client),
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_change_status_of_missing_user_returns_not_found(client: TestClient) -> None:
    response = client.patch(
        "/users/999/status", headers=admin_auth_headers(client), json={"is_active": False}
    )

    assert response.status_code == 404
    assert response.json()["code"] == "user_not_found"


def test_change_status_requires_bearer_token(client: TestClient) -> None:
    response = client.patch("/users/1/status", json={"is_active": False})

    assert response.status_code == 401


def test_student_cannot_delete_user(client: TestClient) -> None:
    register(client, student_payload())
    professor = register(client, professor_payload())

    response = client.delete(f"/users/{professor['id']}", headers=student_headers(client))

    assert response.status_code == 403
