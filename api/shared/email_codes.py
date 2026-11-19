from __future__ import annotations

import base64
import hashlib
import hmac
import time

from database.config.settings import settings

# Codigos enviados por e-mail: recuperacao de senha e verificacao de e-mail.
#
# Nenhum deles e guardado no banco. Sao um HMAC com o segredo da API, como os
# codigos de presenca em attendance_codes.py: na hora de conferir, o codigo e
# calculado de novo e comparado.

# O tempo e dividido em janelas de 15 minutos. O codigo vale na janela em que
# foi emitido e na seguinte, entao vale entre 15 e 30 minutos. Para o usuario,
# dizemos "15 minutos", que e o minimo garantido.
WINDOW_SECONDS = 15 * 60

# 8 caracteres em base32 sao 40 bits: cerca de um trilhao de combinacoes.
# Como o codigo expira em no maximo 30 minutos, tentar todas pela API nao e
# viavel, mesmo sem limite de tentativas.
CODE_LENGTH = 8


def _window(now: float) -> int:
    return int(now // WINDOW_SECONDS)


def _code(purpose: str, user_id: int, binding: str, window: int) -> str:
    # `purpose` separa os tipos de codigo: um codigo de recuperacao nao serve
    # para verificar e-mail, e vice-versa. `binding` e o dado ao qual o codigo
    # fica preso; quando ele muda, o codigo para de valer.
    message = f"{purpose}:{user_id}:{binding}:{window}"
    mac = hmac.new(settings.jwt_secret_key.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b32encode(mac).decode()[:CODE_LENGTH]


def issue_code(purpose: str, user_id: int, binding: str, now: float | None = None) -> str:
    return _code(purpose, user_id, binding, _window(time.time() if now is None else now))


def is_valid_code(
    purpose: str, user_id: int, binding: str, code: str, now: float | None = None
) -> bool:
    window = _window(time.time() if now is None else now)
    candidate = code.strip().upper()
    return any(
        hmac.compare_digest(_code(purpose, user_id, binding, w), candidate)
        for w in (window, window - 1)
    )


class EmailThrottle:
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
