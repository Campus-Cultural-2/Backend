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


# --- envio pelo script do Google ----------------------------------------------

RELAY_URL = "https://script.google.com/macros/s/teste/exec"
RELAY_SECRET = "s" * 48


class FakeRelay:
    """Faz o papel do Apps Script: guarda o que chegou e devolve `reply`."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.status_code = 200
        self.reply: object = {"ok": True, "error": None}


@pytest.fixture
def relay(monkeypatch: pytest.MonkeyPatch) -> FakeRelay:
    """Liga a configuracao do envio e intercepta a chamada, sem ir para a rede."""
    monkeypatch.setattr(settings, "email_relay_url", RELAY_URL)
    monkeypatch.setattr(settings, "email_relay_secret", RELAY_SECRET)
    fake = FakeRelay()

    class FakeResponse:
        def __init__(self) -> None:
            self.status_code = fake.status_code

        def json(self) -> object:
            if isinstance(fake.reply, str):
                raise ValueError("not json")
            return fake.reply

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            fake.requests.append({"client_kwargs": kwargs})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

        async def post(self, url: str, json: dict) -> FakeResponse:
            fake.requests[-1].update(url=url, json=json)
            return FakeResponse()

    monkeypatch.setattr(email_sender_module.httpx, "AsyncClient", FakeClient)
    return fake


def send(to: str = "ana@utfpr.edu.br", name: str = "Ana") -> None:
    asyncio.run(EmailSender().send_password_reset_code(to, name, "ABCD2345"))


def test_email_goes_to_the_relay(relay: FakeRelay) -> None:
    send()

    assert len(relay.requests) == 1
    request = relay.requests[0]
    assert request["url"] == RELAY_URL
    # O Apps Script responde com um redirecionamento; sem segui-lo, a API
    # nunca veria o resultado.
    assert request["client_kwargs"]["follow_redirects"] is True
    assert request["json"]["secret"] == RELAY_SECRET
    assert request["json"]["to"] == "ana@utfpr.edu.br"
    assert request["json"]["subject"] == "Seu código para redefinir a senha"
    assert "ABCD2345" in request["json"]["html"]


def test_email_escapes_user_name(relay: FakeRelay) -> None:
    send(name="<b>Ana</b>")

    html = relay.requests[0]["json"]["html"]
    assert "<b>Ana</b>" not in html
    assert "&lt;b&gt;Ana&lt;/b&gt;" in html


@pytest.mark.parametrize(
    ("status_code", "reply", "logged"),
    [
        (200, {"ok": False, "error": "quota"}, "relay error quota"),
        (200, {"ok": False, "error": "<script>"}, "relay error unknown"),
        (200, "<html>pagina de login do Google</html>", "unexpected page"),
        (500, {"ok": True}, "relay returned 500"),
    ],
)
def test_relay_failures_are_logged_without_the_address(
    relay: FakeRelay,
    caplog: pytest.LogCaptureFixture,
    status_code: int,
    reply: object,
    logged: str,
) -> None:
    relay.status_code = status_code
    relay.reply = reply

    send()

    assert logged in caplog.text
    assert "ana@utfpr.edu.br" not in caplog.text
    assert "ABCD2345" not in caplog.text


def test_email_is_skipped_when_relay_is_not_configured(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "email_relay_url", "")

    # Nao pode quebrar: roda em segundo plano, depois da resposta.
    send()

    assert "email relay is not configured" in caplog.text


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "jwt_secret_key": "x" * 64,
        "database_url": "postgresql://u:p@host/db",
        "seed_default_admin": False,
        "cors_origins": "https://app.example.com",
        "cloudinary_cloud_name": "c",
        "cloudinary_api_key": "k",
        "cloudinary_api_secret": "s",
        "email_relay_url": RELAY_URL,
        "email_relay_secret": RELAY_SECRET,
    }
    return Settings(_env_file=None, **{**values, **overrides})


def test_production_accepts_a_complete_relay_configuration() -> None:
    assert production_settings().is_email_configured


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"email_relay_url": "", "email_relay_secret": ""}, "EMAIL_RELAY_URL e EMAIL_RELAY_SECRET"),
        ({"email_relay_url": "http://script.google.com/x"}, "https://"),
        ({"email_relay_secret": "curto"}, "32 caracteres"),
    ],
)
def test_production_requires_a_safe_relay_configuration(overrides: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        production_settings(**overrides)
