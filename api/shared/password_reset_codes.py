from __future__ import annotations

from api.shared.email_codes import CODE_LENGTH, WINDOW_SECONDS, EmailThrottle
from api.shared.email_codes import is_valid_code as _is_valid
from api.shared.email_codes import issue_code as _issue

__all__ = [
    "CODE_LENGTH",
    "WINDOW_SECONDS",
    "PasswordResetThrottle",
    "is_valid_code",
    "issue_code",
    "password_reset_throttle",
]

_PURPOSE = "password-reset"


def issue_code(user_id: int, password_hash: str, now: float | None = None) -> str:
    """Codigo de recuperacao de senha, enviado por e-mail ao usuario.

    Preso ao hash da senha atual de proposito: assim que a senha muda, o hash
    muda e todo codigo emitido antes deixa de valer. Isso faz o codigo ser de
    uso unico sem precisar guardar nada no banco.
    """
    return _issue(_PURPOSE, user_id, password_hash, now)


def is_valid_code(user_id: int, password_hash: str, code: str, now: float | None = None) -> bool:
    return _is_valid(_PURPOSE, user_id, password_hash, code, now)


# O limitador e o mesmo do codigo de verificacao de e-mail; o nome antigo fica
# para nao mudar quem ja importava daqui.
PasswordResetThrottle = EmailThrottle

password_reset_throttle = EmailThrottle()
