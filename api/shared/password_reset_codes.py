from __future__ import annotations

import base64
import hashlib
import hmac
import time

from database.config.settings import settings

# O tempo e dividido em janelas de 15 minutos. O codigo e aceito na janela
# em que foi emitido e na seguinte, entao vale entre 15 e 30 minutos. Para o
# usuario, dizemos "15 minutos", que e o minimo garantido.
WINDOW_SECONDS = 15 * 60

# 8 caracteres em base32 sao 40 bits: cerca de um trilhao de combinacoes.
# Como o codigo expira em no maximo 30 minutos, tentar todas pela API nao e
# viavel, mesmo sem limite de tentativas.
CODE_LENGTH = 8


def _window(now: float) -> int:
    return int(now // WINDOW_SECONDS)


def _code(user_id: int, password_hash: str, window: int) -> str:
    # O hash da senha entra na conta de proposito: assim que a senha muda,
    # o hash muda e todo codigo emitido antes deixa de valer. Isso faz o
    # codigo ser de uso unico sem precisar guardar nada no banco.
    message = f"password-reset:{user_id}:{password_hash}:{window}"
    mac = hmac.new(settings.jwt_secret_key.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b32encode(mac).decode()[:CODE_LENGTH]


def issue_code(user_id: int, password_hash: str, now: float | None = None) -> str:
    """Codigo de recuperacao de senha, enviado por e-mail ao usuario.

    Derivado do id, do hash da senha atual, da janela de tempo e do segredo
    da API, como os codigos de presenca em attendance_codes.py. Nao e
    guardado no banco: na hora de conferir, e calculado de novo.
    """
    return _code(user_id, password_hash, _window(time.time() if now is None else now))


def is_valid_code(user_id: int, password_hash: str, code: str, now: float | None = None) -> bool:
    window = _window(time.time() if now is None else now)
    candidate = code.strip().upper()
    return any(
        hmac.compare_digest(_code(user_id, password_hash, w), candidate)
        for w in (window, window - 1)
    )


class PasswordResetThrottle:
    """Permite um envio de codigo por e-mail a cada `cooldown_seconds`.

    Protege a caixa de entrada de quem e alvo de pedidos repetidos e a cota
    diaria do plano gratuito do Brevo, que e de 300 e-mails.

    Fica em memoria: zera quando o servico reinicia ou dorme, e nao e
    dividido entre instancias. Com uma instancia so, como no plano gratuito
    do Render, isso basta.
    """

    _MAX_ENTRIES = 10_000

    def __init__(self, cooldown_seconds: float = 60) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._last_sent: dict[str, float] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        last = self._last_sent.get(key)
        if last is not None and now - last < self.cooldown_seconds:
            return False

        if len(self._last_sent) >= self._MAX_ENTRIES:
            self._last_sent = {
                k: t for k, t in self._last_sent.items() if now - t < self.cooldown_seconds
            }

        self._last_sent[key] = now
        return True


password_reset_throttle = PasswordResetThrottle()
