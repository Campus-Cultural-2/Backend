from __future__ import annotations

import asyncio

import jwt
from fastapi.testclient import TestClient
from pwdlib import PasswordHash

from api.app import create_app
from api.features.user.user import User
from api.features.user.user_repository import UserRepository
from api.shared.security import create_access_token
from database.config.settings import settings


def student_payload() -> dict[str, object]:
    return {
        "role": "student",
        "email": "diego@example.com",
        "name": "Diego",
        "last_name": "Ferraz",
        "is_active": True,
        "ra": "2024001",
        "password": "secret",
        "birth_date": None,
    }


def admin_auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/users/login",
        json={"email": "admin@example.com", "password": "admin123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_startup_creates_default_admin_user(client: TestClient) -> None:
    response = client.get("/users", headers=admin_auth_headers(client))

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "role": "admin",
            "email": "admin@example.com",
            "name": "super_user",
            "last_name": "admin",
            "is_active": True,
            "ra": None,
            "birth_date": None,
        }
    ]


def test_healthcheck_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unhandled_exception_returns_internal_error(database_url: str) -> None:
    app = create_app(database_url=database_url)

    @app.get("/broken")
    async def broken_healthcheck() -> dict[str, str]:
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as local_client:
        response = local_client.get("/broken")

    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "Erro interno do servidor",
        "details": {"error_type": "RuntimeError"},
    }


def test_startup_hashes_default_admin_password(client: TestClient) -> None:
    async def get_admin_password_hash() -> str:
        async with client.app.state.database_manager.session_factory() as session:
            user = await session.get(User, 1)
            assert user is not None
            return user.password_hash

    stored_password = asyncio.run(get_admin_password_hash())

    assert stored_password != "admin123"
    assert PasswordHash.recommended().verify("admin123", stored_password)


def test_startup_does_not_duplicate_default_admin(database_url: str) -> None:
    with TestClient(create_app(database_url=database_url)) as first_client:
        first_response = first_client.get("/users", headers=admin_auth_headers(first_client))

    with TestClient(create_app(database_url=database_url)) as second_client:
        second_response = second_client.get("/users", headers=admin_auth_headers(second_client))

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert len(first_response.json()) == 1
    assert second_response.json() == first_response.json()


def test_register_user_is_public_and_returns_created_user(client: TestClient) -> None:
    response = client.post("/users/register", json=student_payload())

    assert response.status_code == 201
    assert response.json() == {
        "id": 2,
        "role": "student",
        "email": "diego@example.com",
        "name": "Diego",
        "last_name": "Ferraz",
        "is_active": True,
        "ra": "2024001",
        "birth_date": None,
    }


def test_register_user_hashes_password_without_exposing_it(client: TestClient) -> None:
    response = client.post("/users/register", json=student_payload())

    async def get_password_hash() -> str:
        async with client.app.state.database_manager.session_factory() as session:
            user = await session.get(User, response.json()["id"])
            assert user is not None
            return user.password_hash

    stored_password = asyncio.run(get_password_hash())

    assert response.status_code == 201
    assert "password" not in response.json()
    assert "password_hash" not in response.json()
    assert stored_password != "secret"
    assert PasswordHash.recommended().verify("secret", stored_password)


def test_login_returns_bearer_token_with_role_and_30_minute_lifetime(client: TestClient) -> None:
    response = client.post(
        "/users/login",
        json={"email": "admin@example.com", "password": "admin123"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"

    token_payload = jwt.decode(
        response.json()["access_token"],
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert token_payload["sub"] == "1"
    assert token_payload["role"] == "admin"
    assert token_payload["exp"] - token_payload["iat"] == 30 * 60


def test_login_with_invalid_credentials_returns_unauthorized(client: TestClient) -> None:
    response = client.post(
        "/users/login",
        json={"email": "admin@example.com", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": "invalid_credentials",
        "message": "Invalid email or password",
    }


def test_login_with_inactive_user_returns_unauthorized(client: TestClient) -> None:
    client.post(
        "/users/register",
        json={
            **student_payload(),
            "is_active": False,
        },
    )

    response = client.post(
        "/users/login",
        json={"email": "diego@example.com", "password": "secret"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": "invalid_credentials",
        "message": "Inactive user",
    }


def test_refresh_token_returns_new_bearer_token(client: TestClient) -> None:
    response = client.post("/users/refresh-token", headers=admin_auth_headers(client))

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"

    token_payload = jwt.decode(
        response.json()["access_token"],
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    assert token_payload["sub"] == "1"
    assert token_payload["role"] == "admin"
    assert token_payload["exp"] - token_payload["iat"] == 30 * 60


def test_list_users_requires_bearer_token(client: TestClient) -> None:
    response = client.get("/users")

    assert response.status_code == 401
    assert response.json() == {
        "code": "invalid_token",
        "message": "Missing bearer token",
    }


def test_list_users_with_malformed_token_returns_unauthorized(client: TestClient) -> None:
    response = client.get("/users", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401
    assert response.json() == {
        "code": "invalid_token",
        "message": "Invalid token",
    }


def test_list_users_with_deleted_user_token_returns_unauthorized(client: TestClient) -> None:
    async def get_admin_token_and_delete_user() -> str:
        async with client.app.state.database_manager.session_factory() as session:
            user = await session.get(User, 1)
            assert user is not None
            token = create_access_token(user)
            await session.delete(user)
            await session.commit()
            return token

    token = asyncio.run(get_admin_token_and_delete_user())

    response = client.get("/users", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json() == {
        "code": "invalid_token",
        "message": "Invalid token",
    }


def test_list_users_with_inactive_token_user_returns_unauthorized(client: TestClient) -> None:
    async def get_inactive_admin_token() -> str:
        async with client.app.state.database_manager.session_factory() as session:
            user = await session.get(User, 1)
            assert user is not None
            user.is_active = False
            token = create_access_token(user)
            await session.commit()
            return token

    token = asyncio.run(get_inactive_admin_token())

    response = client.get("/users", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json() == {
        "code": "invalid_token",
        "message": "Inactive user",
    }


def test_register_user_rejects_admin_role(client: TestClient) -> None:
    response = client.post(
        "/users/register",
        json={
            "role": "admin",
            "email": "another-admin@example.com",
            "name": "Administrador",
            "last_name": "Admin",
            "is_active": True,
            "ra": None,
            "password": "admin-secret",
            "birth_date": None,
        },
    )

    assert response.status_code == 400


def test_register_non_student_user_with_ra_returns_validation_error(client: TestClient) -> None:
    response = client.post(
        "/users/register",
        json={
            "role": "professor",
            "email": "maria@example.com",
            "name": "Maria",
            "last_name": "Silva",
            "is_active": True,
            "ra": "2024002",
            "password": "strong-password",
            "birth_date": None,
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_list_users_returns_created_users(client: TestClient) -> None:
    client.post("/users/register", json=student_payload())
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

    response = client.get("/users", headers=admin_auth_headers(client))
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "role": "admin",
            "email": "admin@example.com",
            "name": "super_user",
            "last_name": "admin",
            "is_active": True,
            "ra": None,
            "birth_date": None,
        },
        {
            "id": 2,
            "role": "student",
            "email": "diego@example.com",
            "name": "Diego",
            "last_name": "Ferraz",
            "is_active": True,
            "ra": "2024001",
            "birth_date": None,
        },
        {
            "id": 3,
            "role": "professor",
            "email": "maria@example.com",
            "name": "Maria",
            "last_name": "Silva",
            "is_active": True,
            "ra": None,
            "birth_date": None,
        },
    ]


def test_get_user_by_id_returns_user(client: TestClient) -> None:
    created = client.post("/users/register", json=student_payload()).json()

    response = client.get(f"/users/{created['id']}", headers=admin_auth_headers(client))

    assert response.status_code == 200
    assert response.json() == created


def test_update_user_uses_id_from_url_and_returns_updated_user(client: TestClient) -> None:
    created = client.post("/users/register", json=student_payload()).json()

    response = client.put(
        f"/users/{created['id']}",
        headers=admin_auth_headers(client),
        json={
            "role": "professor",
            "email": "diego.updated@example.com",
            "name": "Diego Atualizado",
            "last_name": "Ferraz Atualizado",
            "is_active": False,
            "ra": None,
            "password": "new-password",
            "birth_date": None,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": created["id"],
        "role": "professor",
        "email": "diego.updated@example.com",
        "name": "Diego Atualizado",
        "last_name": "Ferraz Atualizado",
        "is_active": False,
        "ra": None,
        "birth_date": None,
    }


def test_update_profile_picture_stores_binary_without_exposing_it(client: TestClient) -> None:
    created = client.post("/users/register", json=student_payload()).json()
    image_bytes = b"\x89PNG\r\n\x1a\nprofile-picture"

    response = client.post(
        f"/users/{created['id']}/profile-picture",
        headers={
            **admin_auth_headers(client),
            "Content-Type": "application/octet-stream",
        },
        content=image_bytes,
    )

    async def get_profile_picture() -> bytes | None:
        async with client.app.state.database_manager.session_factory() as session:
            user = await session.get(User, created["id"])
            assert user is not None
            return user.profile_picture

    stored_profile_picture = asyncio.run(get_profile_picture())

    assert response.status_code == 200
    assert response.json() == created
    assert "profile_picture" not in response.json()
    assert stored_profile_picture == image_bytes


def test_update_profile_picture_requires_bearer_token(client: TestClient) -> None:
    created = client.post("/users/register", json=student_payload()).json()

    response = client.post(
        f"/users/{created['id']}/profile-picture",
        content=b"image",
        headers={"Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "code": "invalid_token",
        "message": "Missing bearer token",
    }


def test_get_profile_picture_returns_binary_data(client: TestClient) -> None:
    created = client.post("/users/register", json=student_payload()).json()
    image_bytes = b"\x89PNG\r\n\x1a\nprofile-picture"
    headers = admin_auth_headers(client)
    client.post(
        f"/users/{created['id']}/profile-picture",
        headers={
            **headers,
            "Content-Type": "application/octet-stream",
        },
        content=image_bytes,
    )

    response = client.get(f"/users/{created['id']}/profile-picture", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.content == image_bytes


def test_get_profile_picture_returns_not_found_when_missing(client: TestClient) -> None:
    created = client.post("/users/register", json=student_payload()).json()

    response = client.get(
        f"/users/{created['id']}/profile-picture",
        headers=admin_auth_headers(client),
    )

    assert response.status_code == 404
    assert response.json() == {
        "code": "user_profile_picture_not_found",
        "message": f"User {created['id']} profile picture not found",
        "details": {"user_id": created["id"]},
    }


def test_delete_user_removes_resource(client: TestClient) -> None:
    created = client.post("/users/register", json=student_payload()).json()
    headers = admin_auth_headers(client)

    delete_response = client.delete(f"/users/{created['id']}", headers=headers)
    get_response = client.get(f"/users/{created['id']}", headers=headers)

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
    assert get_response.json() == {
        "code": "user_not_found",
        "message": f"User {created['id']} not found",
        "details": {"user_id": created["id"]},
    }


def test_register_user_with_duplicate_ra_returns_conflict_error(client: TestClient) -> None:
    payload = student_payload()
    duplicate_ra_payload = {
        **payload,
        "email": "another-student@example.com",
    }

    first_response = client.post("/users/register", json=payload)
    second_response = client.post("/users/register", json=duplicate_ra_payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {
        "code": "user_ra_already_exists",
        "message": "A user with this RA already exists",
        "details": {"field": "ra", "value": "2024001"},
    }


def test_register_user_with_duplicate_email_returns_conflict_error(client: TestClient) -> None:
    payload = student_payload()
    duplicate_email_payload = {
        **payload,
        "ra": "2024002",
    }

    first_response = client.post("/users/register", json=payload)
    second_response = client.post("/users/register", json=duplicate_email_payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {
        "code": "user_email_already_exists",
        "message": "A user with this email already exists",
        "details": {"field": "email", "value": "diego@example.com"},
    }


def test_user_repository_get_by_ra_returns_user(client: TestClient) -> None:
    created = client.post("/users/register", json=student_payload()).json()

    async def get_user_by_ra() -> User | None:
        async with client.app.state.database_manager.session_factory() as session:
            return await UserRepository(session).get_by_ra("2024001")

    user = asyncio.run(get_user_by_ra())

    assert user is not None
    assert user.id == created["id"]


def test_update_user_with_duplicate_email_returns_conflict_error(client: TestClient) -> None:
    client.post("/users/register", json=student_payload())
    second_user = client.post(
        "/users/register",
        json={
            **student_payload(),
            "email": "second@example.com",
            "ra": "2024002",
        },
    ).json()

    response = client.put(
        f"/users/{second_user['id']}",
        headers=admin_auth_headers(client),
        json={
            **student_payload(),
            "ra": "2024002",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "code": "user_email_already_exists",
        "message": "A user with this email already exists",
        "details": {"field": "email", "value": "diego@example.com"},
    }
