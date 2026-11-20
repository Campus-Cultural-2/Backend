from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valor usado só em desenvolvimento local. A aplicação se recusa a subir
# em produção enquanto este valor não for trocado por um segredo real.
DEV_JWT_SECRET_KEY = "dev-only-insecure-secret-do-not-use-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # "development" | "production"
    environment: str = "development"

    database_url: str = "sqlite:///./database/app.db"
    jwt_secret_key: str = DEV_JWT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # Cria o admin padrão no startup. Deve ficar desligado em produção.
    seed_default_admin: bool = True

    # Origens liberadas para o CORS, separadas por vírgula.
    cors_origins: str = "*"

    # Cloudinary, onde ficam as imagens (banner dos eventos e foto de perfil).
    # Os valores estão no painel do Cloudinary, em Settings > API Keys.
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # Envio de e-mail (codigos de recuperacao de senha e de confirmacao de
    # e-mail) por um Google Apps Script que manda pelo Gmail do projeto. E
    # por HTTPS, e nao SMTP, porque o plano gratuito do Render bloqueia as
    # portas de saida 25, 465 e 587. Como montar: docs/envio-de-email/.
    email_relay_url: str = ""
    email_relay_secret: str = ""
    email_sender_name: str = "Campus Cultural UTFPR"

    # Dominios de e-mail aceitos no cadastro, separados por virgula. A
    # comparacao e pelo dominio exato: "alunos.utfpr.edu.br" termina com
    # "utfpr.edu.br", entao comparar pelo final aceitaria qualquer aluno como
    # servidor.
    allowed_email_domains: str = "utfpr.edu.br,alunos.utfpr.edu.br"
    # Dominios aceitos para o papel de professor. Aluno tem caixa em
    # alunos.utfpr.edu.br, nao em utfpr.edu.br; com a verificacao de e-mail,
    # isso impede que um aluno se cadastre como professor.
    professor_email_domains: str = "utfpr.edu.br"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_cloudinary_configured(self) -> bool:
        return all(
            (self.cloudinary_cloud_name, self.cloudinary_api_key, self.cloudinary_api_secret)
        )

    @property
    def is_email_configured(self) -> bool:
        return all((self.email_relay_url, self.email_relay_secret))

    @property
    def allowed_email_domains_list(self) -> list[str]:
        return _split_domains(self.allowed_email_domains)

    @property
    def professor_email_domains_list(self) -> list[str]:
        return _split_domains(self.professor_email_domains)

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _guard_production_config(self) -> Settings:
        if not self.is_production:
            return self

        errors: list[str] = []

        if self.jwt_secret_key == DEV_JWT_SECRET_KEY:
            errors.append(
                "JWT_SECRET_KEY ainda está no valor de desenvolvimento. "
                'Gere um segredo com: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        elif len(self.jwt_secret_key) < 32:
            errors.append("JWT_SECRET_KEY precisa ter pelo menos 32 caracteres.")

        if self.database_url.startswith("sqlite"):
            errors.append(
                "DATABASE_URL aponta para SQLite. Em produção o disco do container é apagado "
                "a cada deploy. Use um Postgres (ex.: postgresql+asyncpg://...)."
            )

        if self.seed_default_admin:
            errors.append("SEED_DEFAULT_ADMIN precisa ser false em produção.")

        if "*" in self.cors_origins_list:
            errors.append("CORS_ORIGINS não pode ser '*' em produção.")

        if not self.is_cloudinary_configured:
            errors.append(
                "CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY e CLOUDINARY_API_SECRET precisam "
                "estar preenchidas. Sem elas o upload de imagens não funciona."
            )

        if not self.is_email_configured:
            errors.append(
                "EMAIL_RELAY_URL e EMAIL_RELAY_SECRET precisam estar preenchidas. "
                "Sem elas nenhum código chega por e-mail e ninguém termina o cadastro."
            )
        else:
            if not self.email_relay_url.startswith("https://"):
                errors.append("EMAIL_RELAY_URL precisa começar com https://.")
            if len(self.email_relay_secret) < 32:
                errors.append("EMAIL_RELAY_SECRET precisa ter pelo menos 32 caracteres.")

        if not self.allowed_email_domains_list:
            errors.append("ALLOWED_EMAIL_DOMAINS não pode ficar vazio em produção.")

        if not self.professor_email_domains_list:
            errors.append(
                "PROFESSOR_EMAIL_DOMAINS não pode ficar vazio em produção. "
                "Sem ele qualquer pessoa pode se cadastrar como professor."
            )

        if errors:
            raise ValueError("Configuração de produção inválida:\n  - " + "\n  - ".join(errors))

        return self


def _split_domains(value: str) -> list[str]:
    return [domain.strip().lower() for domain in value.split(",") if domain.strip()]


settings = Settings()


def get_database_url() -> str:
    return settings.database_url
