from __future__ import annotations

import base64
import hashlib
import hmac

from database.config.settings import settings


def _mac(message: str) -> bytes:
    return hmac.new(settings.jwt_secret_key.encode(), message.encode(), hashlib.sha256).digest()


def event_code(event_id: int) -> str:
    """Codigo do evento, lido pelo aluno para confirmar a propria presenca.

    Derivado do id do evento e do segredo da API, entao nao precisa ser
    guardado no banco.
    """
    return base64.b32encode(_mac(f"event-code:{event_id}")).decode()[:8]


def is_valid_event_code(event_id: int, code: str) -> bool:
    return hmac.compare_digest(event_code(event_id), code.strip().upper())


def student_code(event_id: int, user_id: int) -> str:
    """Codigo (QR code) de um aluno inscrito, lido pelo professor."""
    mac = base64.urlsafe_b64encode(_mac(f"student-code:{event_id}:{user_id}")).decode()
    return f"{user_id}.{mac[:16]}"


def parse_student_code(event_id: int, code: str) -> int | None:
    """Devolve o id do aluno se o codigo for valido para o evento."""
    code = code.strip()
    user_part, separator, _ = code.partition(".")
    if not separator or not user_part.isdigit():
        return None
    user_id = int(user_part)
    if hmac.compare_digest(student_code(event_id, user_id), code):
        return user_id
    return None
