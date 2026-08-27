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

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

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

        if errors:
            raise ValueError("Configuração de produção inválida:\n  - " + "\n  - ".join(errors))

        return self


settings = Settings()


def get_database_url() -> str:
    return settings.database_url
