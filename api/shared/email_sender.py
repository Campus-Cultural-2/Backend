from __future__ import annotations

import html
import logging

import httpx

from api.shared.password_reset_codes import WINDOW_SECONDS
from database.config.settings import settings

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"

logger = logging.getLogger(__name__)


class EmailSender:
    """Envia e-mails pela API HTTP do Brevo.

    E por API HTTP, e nao por SMTP, de proposito: o plano gratuito do Render
    bloqueia as portas de saida 25, 465 e 587, que sao as do SMTP. Um envio
    por SMTP funcionaria na maquina de quem desenvolve e falharia em silencio
    em producao.
    """

    async def send_password_reset_code(self, to: str, name: str, code: str) -> None:
        """Envia o codigo de recuperacao de senha.

        Roda em segundo plano, depois que a resposta ja foi devolvida ao app,
        entao uma falha aqui nao chega ao usuario: vai para o log. O endereco e
        o codigo nao entram no log.
        """
        if not settings.is_email_configured:
            logger.warning("Password reset email not sent: Brevo is not configured")
            return

        minutes = WINDOW_SECONDS // 60
        # O nome vem do cadastro do usuario: escapar evita que alguem injete
        # HTML no e-mail colocando tags no proprio nome.
        safe_name = html.escape(name)
        body = f"""\
<p>Olá, {safe_name}.</p>
<p>Recebemos um pedido para redefinir a senha da sua conta no Campus Cultural.</p>
<p>Seu código é:</p>
<p style="font-size:24px;font-weight:bold;letter-spacing:4px">{code}</p>
<p>Ele vale por {minutes} minutos e só pode ser usado uma vez.</p>
<p>Se não foi você que pediu, ignore este e-mail: sua senha continua a mesma.</p>
"""
        payload = {
            "sender": {"name": settings.email_sender_name, "email": settings.email_sender_address},
            "to": [{"email": to, "name": name}],
            "subject": "Seu código para redefinir a senha",
            "htmlContent": body,
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    BREVO_SEND_URL,
                    json=payload,
                    headers={"api-key": settings.brevo_api_key, "accept": "application/json"},
                )
        except httpx.HTTPError as exc:
            logger.warning("Password reset email not sent: %s", type(exc).__name__)
            return

        if response.status_code >= 400:
            logger.warning("Password reset email not sent: Brevo returned %s", response.status_code)
