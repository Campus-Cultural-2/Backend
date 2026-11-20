from __future__ import annotations

from api.shared.email_codes import EmailThrottle
from api.shared.email_codes import is_valid_code as _is_valid
from api.shared.email_codes import issue_code as _issue

_PURPOSE = "email-verification"


def issue_code(user_id: int, email: str, now: float | None = None) -> str:
    """Codigo que confirma que a pessoa e dona do e-mail informado no cadastro.

    Preso ao endereco: se o e-mail da conta mudar, o codigo deixa de valer, e
    so quem recebe mensagens naquele endereco consegue confirmar.
    """
    return _issue(_PURPOSE, user_id, email.lower(), now)


def is_valid_code(user_id: int, email: str, code: str, now: float | None = None) -> bool:
    return _is_valid(_PURPOSE, user_id, email.lower(), code, now)


email_verification_throttle = EmailThrottle()
