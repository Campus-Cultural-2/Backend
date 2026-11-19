from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from api.shared import email_sender as email_sender_module
from api.shared.email_sender import EmailSender
from api.shared.password_reset_codes import (
    WINDOW_SECONDS,
    PasswordResetThrottle,
    is_valid_code,
    issue_code,
)
from database.config.settings import Settings, settings
from tests.fakes import FakeEmailSender

EMAIL = "ana@utfpr.edu.br"
PASSWORD = "senha-antiga-1!"
NEW_PASSWORD = "senha-nova-2@"


def register(client: TestClient, *, is_active: bool = True, name: str = "Ana") -> None:
    response = client.post(
        "/users/register",
        json={
            "role": "student",
            "email": EMAIL,
            "name": name,
            "last_name": "Souza",
            "is_active": is_active,
            "ra": "2024900",
            "password": PASSWORD,
            "birth_date": None,
        },
    )
    assert response.status_code == 201


def request_reset(client: TestClient, email: str = EMAIL):
    return client.post("/users/password-reset/request", json={"email": email})


def confirm_reset(client: TestClient, code: str, email: str = EMAIL, password: str = NEW_PASSWORD):
    return client.post(
        "/users/password-reset/confirm",
        json={"email": email, "code": code, "new_password": password},
    )


def login_status(client: TestClient, password: str) -> int:
    return client.post("/users/login", json={"email": EMAIL, "password": password}).status_code


# --- pedido do codigo ---------------------------------------------------------


def test_request_sends_code_to_registered_user(
    client: TestClient, email_sender: FakeEmailSender
) -> None:
    register(client)

    response = request_reset(client)

    assert response.status_code == 202
    assert len(email_sender.password_reset_codes) == 1
    to, name, code = email_sender.password_reset_codes[0]
    assert (to, name) == (EMAIL, "Ana")
    assert len(code) == 8


def test_request_answers_the_same_for_unknown_email(
    client: TestClient, email_sender: FakeEmailSender
) -> None:
    register(client)

    known = request_reset(client)
    unknown = request_reset(client, "ninguem@utfpr.edu.br")

    # Mesma resposta: a API nao pode revelar quais e-mails tem conta.
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    assert len(email_sender.password_reset_codes) == 1


def test_request_does_not_send_to_inactive_user(
    client: TestClient, email_sender: FakeEmailSender
) -> None:
    register(client, is_active=False)

    response = request_reset(client)

    assert response.status_code == 202
    assert email_sender.password_reset_codes == []


def test_request_is_throttled_per_email(client: TestClient, email_sender: FakeEmailSender) -> None:
    register(client)

    request_reset(client)
    second = request_reset(client)

    # O segundo pedido em menos de um minuto responde igual, mas nao envia.
    assert second.status_code == 202
    assert len(email_sender.password_reset_codes) == 1


# --- confirmacao --------------------------------------------------------------


def test_confirm_with_valid_code_changes_password(
    client: TestClient, email_sender: FakeEmailSender
) -> None:
    register(client)
    request_reset(client)
    code = email_sender.password_reset_codes[0][2]

    response = confirm_reset(client, code)

    assert response.status_code == 204
    assert login_status(client, NEW_PASSWORD) == 200
    assert login_status(client, PASSWORD) == 401


def test_confirm_accepts_code_in_lowercase(
    client: TestClient, email_sender: FakeEmailSender
) -> None:
    register(client)
    request_reset(client)
    code = email_sender.password_reset_codes[0][2]

    assert confirm_reset(client, code.lower()).status_code == 204


def test_confirm_rejects_wrong_code(client: TestClient) -> None:
    register(client)
    request_reset(client)

    response = confirm_reset(client, "AAAAAAAA")

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_password_reset_code"
    assert login_status(client, PASSWORD) == 200


def test_confirm_answers_the_same_for_unknown_email(client: TestClient) -> None:
    register(client)

    wrong_code = confirm_reset(client, "AAAAAAAA")
    unknown_email = confirm_reset(client, "AAAAAAAA", email="ninguem@utfpr.edu.br")

    assert unknown_email.status_code == wrong_code.status_code == 400
    assert unknown_email.json() == wrong_code.json()


def test_code_works_only_once(client: TestClient, email_sender: FakeEmailSender) -> None:
    register(client)
    request_reset(client)
    code = email_sender.password_reset_codes[0][2]

    assert confirm_reset(client, code).status_code == 204
    # A senha mudou, o hash mudou, e o codigo que dependia dele deixou de valer.
    assert confirm_reset(client, code, password="outra-senha-3#").status_code == 400
    assert login_status(client, NEW_PASSWORD) == 200


def test_confirm_rejects_short_password(client: TestClient, email_sender: FakeEmailSender) -> None:
    register(client)
    request_reset(client)
    code = email_sender.password_reset_codes[0][2]

    response = confirm_reset(client, code, password="curta")

    assert response.status_code == 422
    assert login_status(client, PASSWORD) == 200


# --- regras do codigo, sem passar pela API ------------------------------------


def test_code_is_valid_until_the_end_of_the_next_window() -> None:
    issued_at = 10 * WINDOW_SECONDS
    code = issue_code(1, "hash", now=issued_at)

    assert is_valid_code(1, "hash", code, now=issued_at)
    assert is_valid_code(1, "hash", code, now=issued_at + WINDOW_SECONDS)
    assert not is_valid_code(1, "hash", code, now=issued_at + 2 * WINDOW_SECONDS)


def test_code_depends_on_user_and_password_hash() -> None:
    code = issue_code(1, "hash", now=0)

    assert not is_valid_code(2, "hash", code, now=0)
    assert not is_valid_code(1, "outro-hash", code, now=0)


def test_throttle_allows_again_after_cooldown() -> None:
    throttle = PasswordResetThrottle(cooldown_seconds=60)

    assert throttle.allow("a@x", now=0)
    assert not throttle.allow("a@x", now=59)
    assert throttle.allow("b@x", now=59)
    assert throttle.allow("a@x", now=60)


# --- envio pelo Brevo ---------------------------------------------------------


@pytest.fixture
def brevo_configured(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Liga a configuracao do Brevo e intercepta o envio, sem ir para a rede."""
    monkeypatch.setattr(settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(settings, "email_sender_address", "remetente@example.com")
    sent: list[dict] = []

    class FakeResponse:
        status_code = 201

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

        async def post(self, url: str, json: dict, headers: dict) -> FakeResponse:
            sent.append({"url": url, "json": json, "headers": headers})
            return FakeResponse()

    monkeypatch.setattr(email_sender_module.httpx, "AsyncClient", FakeClient)
    return sent


def test_email_goes_to_brevo_api(brevo_configured: list[dict]) -> None:
    asyncio.run(EmailSender().send_password_reset_code("ana@utfpr.edu.br", "Ana", "ABCD2345"))

    assert len(brevo_configured) == 1
    request = brevo_configured[0]
    assert request["url"] == "https://api.brevo.com/v3/smtp/email"
    assert request["headers"]["api-key"] == "test-key"
    assert request["json"]["to"] == [{"email": "ana@utfpr.edu.br", "name": "Ana"}]
    assert "ABCD2345" in request["json"]["htmlContent"]


def test_email_escapes_user_name(brevo_configured: list[dict]) -> None:
    asyncio.run(EmailSender().send_password_reset_code("a@utfpr.edu.br", "<b>Ana</b>", "ABCD2345"))

    html = brevo_configured[0]["json"]["htmlContent"]
    assert "<b>Ana</b>" not in html
    assert "&lt;b&gt;Ana&lt;/b&gt;" in html


def test_email_is_skipped_when_brevo_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "brevo_api_key", "")

    # Nao pode quebrar: roda em segundo plano, depois da resposta.
    asyncio.run(EmailSender().send_password_reset_code("a@utfpr.edu.br", "Ana", "ABCD2345"))


def test_production_requires_brevo() -> None:
    with pytest.raises(ValueError, match="BREVO_API_KEY"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret_key="x" * 64,
            database_url="postgresql://u:p@host/db",
            seed_default_admin=False,
            cors_origins="https://app.example.com",
            cloudinary_cloud_name="c",
            cloudinary_api_key="k",
            cloudinary_api_secret="s",
            brevo_api_key="",
            email_sender_address="",
        )
