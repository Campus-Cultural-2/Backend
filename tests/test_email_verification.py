from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from api.shared import email_sender as email_sender_module
from api.shared.email_sender import EmailSender
from api.shared.email_verification_codes import is_valid_code, issue_code
from database.config.settings import Settings, settings
from tests.fakes import FakeEmailSender

STUDENT_EMAIL = "aluna@alunos.utfpr.edu.br"
STAFF_EMAIL = "professora@utfpr.edu.br"
PASSWORD = "senha-forte-1!"


@pytest.fixture(autouse=True)
def real_signup_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Religa as regras de verdade, que o conftest desliga para os testes antigos.

    Com o Brevo "configurado", a conta nao nasce verificada. O envio em si
    continua indo para o FakeEmailSender, sem rede.
    """
    monkeypatch.setattr(settings, "allowed_email_domains", "utfpr.edu.br,alunos.utfpr.edu.br")
    monkeypatch.setattr(settings, "professor_email_domains", "utfpr.edu.br")
    monkeypatch.setattr(settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(settings, "email_sender_address", "remetente@example.com")


def payload(email: str, role: str = "student", ra: str | None = "2024100") -> dict:
    return {
        "role": role,
        "email": email,
        "name": "Ana",
        "last_name": "Souza",
        "is_active": True,
        "ra": ra if role == "student" else None,
        "password": PASSWORD,
        "birth_date": None,
    }


def register(client: TestClient, email: str = STUDENT_EMAIL, role: str = "student"):
    return client.post("/users/register", json=payload(email, role))


def login(client: TestClient, email: str = STUDENT_EMAIL, password: str = PASSWORD):
    return client.post("/users/login", json={"email": email, "password": password})


def confirm(client: TestClient, code: str, email: str = STUDENT_EMAIL):
    return client.post("/users/verify-email/confirm", json={"email": email, "code": code})


def resend(client: TestClient, email: str = STUDENT_EMAIL):
    return client.post("/users/verify-email/request", json={"email": email})


# --- cadastro e login ---------------------------------------------------------


def test_signup_sends_code_and_blocks_login_until_verified(
    client: TestClient, email_sender: FakeEmailSender
) -> None:
    assert register(client).status_code == 201

    assert len(email_sender.verification_codes) == 1
    to, name, code = email_sender.verification_codes[0]
    assert (to, name, len(code)) == (STUDENT_EMAIL, "Ana", 8)

    response = login(client)
    assert response.status_code == 403
    assert response.json()["code"] == "email_not_verified"


def test_verified_user_can_log_in(client: TestClient, email_sender: FakeEmailSender) -> None:
    register(client)
    code = email_sender.verification_codes[0][2]

    assert confirm(client, code).status_code == 204
    assert login(client).status_code == 200


def test_wrong_password_on_unverified_account_does_not_reveal_it(client: TestClient) -> None:
    register(client)

    # Senha errada responde como qualquer login errado. So depois da senha
    # certa a API conta que falta verificar: senao, tentar entrar revelaria
    # quais e-mails tem conta.
    response = login(client, password="errada-000!")
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_existing_seed_admin_is_verified(client: TestClient) -> None:
    response = login(client, email="admin@example.com", password="admin123")
    assert response.status_code == 200


# --- confirmacao --------------------------------------------------------------


def test_wrong_code_is_rejected(client: TestClient) -> None:
    register(client)

    response = confirm(client, "AAAAAAAA")

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_email_verification_code"
    assert login(client).status_code == 403


def test_confirm_answers_the_same_for_unknown_email(client: TestClient) -> None:
    register(client)

    wrong_code = confirm(client, "AAAAAAAA")
    unknown = confirm(client, "AAAAAAAA", email="ninguem@alunos.utfpr.edu.br")

    assert unknown.status_code == wrong_code.status_code == 400
    assert unknown.json() == wrong_code.json()


def test_code_of_one_account_does_not_verify_another(
    client: TestClient, email_sender: FakeEmailSender
) -> None:
    register(client)
    client.post("/users/register", json={**payload("outra@alunos.utfpr.edu.br"), "ra": "2024101"})
    first_code = email_sender.verification_codes[0][2]

    assert confirm(client, first_code, email="outra@alunos.utfpr.edu.br").status_code == 400


def test_confirm_accepts_lowercase_code(client: TestClient, email_sender: FakeEmailSender) -> None:
    register(client)
    code = email_sender.verification_codes[0][2]

    assert confirm(client, code.lower()).status_code == 204


# --- reenvio ------------------------------------------------------------------


def test_resend_sends_code_after_cooldown_only(
    client: TestClient, email_sender: FakeEmailSender
) -> None:
    register(client)

    first = resend(client)
    second = resend(client)

    assert first.status_code == second.status_code == 202
    # 1 no cadastro + 1 no primeiro reenvio; o segundo, em menos de um minuto, nao envia.
    assert len(email_sender.verification_codes) == 2


def test_resend_answers_the_same_for_unknown_or_verified_email(
    client: TestClient, email_sender: FakeEmailSender
) -> None:
    register(client)
    confirm(client, email_sender.verification_codes[0][2])
    sent_before = len(email_sender.verification_codes)

    verified = resend(client)
    unknown = resend(client, "ninguem@alunos.utfpr.edu.br")

    assert verified.json() == unknown.json()
    assert len(email_sender.verification_codes) == sent_before


# --- dominios -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("email", "role", "allowed"),
    [
        ("aluna@alunos.utfpr.edu.br", "student", True),
        ("servidora@utfpr.edu.br", "student", True),
        ("professora@utfpr.edu.br", "professor", True),
        ("aluno@alunos.utfpr.edu.br", "professor", False),
        ("alguem@gmail.com", "student", False),
        ("alguem@utfpr.edu.br.evil.com", "professor", False),
        ("alguem@falso-utfpr.edu.br", "professor", False),
    ],
)
def test_signup_email_domains(client: TestClient, email: str, role: str, allowed: bool) -> None:
    response = register(client, email=email, role=role)

    if allowed:
        assert response.status_code == 201
    else:
        assert response.status_code == 400
        assert response.json()["code"] == "email_domain_not_allowed"


def test_stranger_can_no_longer_take_over_a_student_account(
    client: TestClient, email_sender: FakeEmailSender
) -> None:
    """O ataque que motivou esta mudanca, agora bloqueado em cada passo.

    Antes: qualquer pessoa se cadastrava como professor, entrava, listava
    todos os usuarios e trocava a senha de qualquer aluno.
    """
    register(client)
    confirm(client, email_sender.verification_codes[0][2])

    # 1. Com e-mail de aluno, nao da para se cadastrar como professor.
    as_student_email = register(client, email="intruso@alunos.utfpr.edu.br", role="professor")
    assert as_student_email.status_code == 400

    # 2. Com um e-mail de servidor que nao e seu, o cadastro passa, mas o
    #    codigo vai para a caixa do dono do endereco. Sem ele, nao entra.
    assert register(client, email="vitima@utfpr.edu.br", role="professor").status_code == 201
    assert login(client, email="vitima@utfpr.edu.br").status_code == 403


# --- regras do codigo e ambiente ----------------------------------------------


def test_code_is_bound_to_the_email_address() -> None:
    code = issue_code(1, "a@utfpr.edu.br", now=0)

    assert is_valid_code(1, "A@UTFPR.EDU.BR", code, now=0)
    assert not is_valid_code(1, "b@utfpr.edu.br", code, now=0)


def test_local_environment_without_brevo_skips_verification(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Sem como enviar o codigo, ninguem terminaria um cadastro localmente.
    monkeypatch.setattr(settings, "brevo_api_key", "")

    register(client)

    assert login(client).status_code == 200


def test_production_never_skips_verification(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Mesmo que o Brevo estivesse faltando (a guarda de producao nao deixa a
    # aplicacao subir assim), producao nunca libera a conta sem verificar.
    monkeypatch.setattr(settings, "brevo_api_key", "")
    monkeypatch.setattr(settings, "environment", "production")

    register(client)

    assert login(client).status_code == 403


def test_production_requires_professor_email_domains() -> None:
    with pytest.raises(ValueError, match="PROFESSOR_EMAIL_DOMAINS"):
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
            brevo_api_key="k",
            email_sender_address="a@example.com",
            professor_email_domains="",
        )


def test_verification_email_goes_to_brevo(monkeypatch: pytest.MonkeyPatch) -> None:
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
            sent.append(json)
            return FakeResponse()

    monkeypatch.setattr(email_sender_module.httpx, "AsyncClient", FakeClient)

    asyncio.run(EmailSender().send_email_verification_code(STUDENT_EMAIL, "<i>Ana</i>", "ABCD2345"))

    assert sent[0]["subject"] == "Confirme seu e-mail no Campus Cultural"
    assert "ABCD2345" in sent[0]["htmlContent"]
    assert "<i>Ana</i>" not in sent[0]["htmlContent"]
