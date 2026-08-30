from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Parametros que so o driver do libpq (psycopg) entende. O asyncpg rejeita
# estes nomes, entao eles precisam sair da URL e virar connect_args.
_LIBPQ_ONLY_PARAMS = frozenset({"sslmode", "channel_binding", "options", "target_session_attrs"})

_ASYNC_POSTGRES_PREFIX = "postgresql+asyncpg://"
_SYNC_POSTGRES_PREFIX = "postgresql+psycopg://"


def _is_sqlite(database_url: str) -> bool:
    return database_url.startswith("sqlite")


def _is_postgres(database_url: str) -> bool:
    return database_url.startswith(("postgres://", "postgresql://", "postgresql+"))


def _swap_scheme(database_url: str, new_prefix: str) -> str:
    """Troca o esquema da URL preservando usuario, senha, host e caminho."""
    _, _, rest = database_url.partition("://")
    return f"{new_prefix}{rest}"


def _strip_libpq_params(database_url: str) -> str:
    """Remove da query os parametros que o asyncpg nao aceita."""
    parts = urlsplit(database_url)
    if not parts.query:
        return database_url

    kept = [(key, value) for key, value in parse_qsl(parts.query) if key not in _LIBPQ_ONLY_PARAMS]
    return urlunsplit(parts._replace(query=urlencode(kept)))


def to_async_url(database_url: str) -> str:
    """URL usada pela aplicacao, sempre com driver assincrono."""
    if _is_sqlite(database_url):
        if database_url.startswith("sqlite+"):
            return database_url
        return database_url.replace("sqlite://", "sqlite+aiosqlite://", 1)

    if _is_postgres(database_url):
        return _strip_libpq_params(_swap_scheme(database_url, _ASYNC_POSTGRES_PREFIX))

    return database_url


def to_sync_url(database_url: str) -> str:
    """URL usada pelo Alembic, sempre com driver sincrono."""
    if _is_sqlite(database_url):
        if database_url.startswith("sqlite+"):
            return database_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        return database_url

    if _is_postgres(database_url):
        # O psycopg entende sslmode e channel_binding, entao a query fica.
        return _swap_scheme(database_url, _SYNC_POSTGRES_PREFIX)

    return database_url


def async_connect_args(database_url: str) -> dict[str, Any]:
    """connect_args do driver assincrono, por banco."""
    if _is_sqlite(database_url):
        # O SQLite so permite usar a conexao na thread que a criou.
        return {"check_same_thread": False}

    if _is_postgres(database_url):
        return {
            # Provedores gerenciados (Neon, Render, Supabase) exigem TLS.
            "ssl": "require",
            # O pooler do Neon e um pgbouncer em modo transaction, que nao
            # suporta prepared statements. Sem isto, a aplicacao quebra com
            # "prepared statement already exists" sob concorrencia.
            "statement_cache_size": 0,
        }

    return {}


def async_engine_options(database_url: str) -> dict[str, Any]:
    """Opcoes de pool do engine assincrono, por banco."""
    if not _is_postgres(database_url):
        return {}

    return {
        # O Neon suspende o banco depois de 5 min ociosos e derruba as
        # conexoes. Sem o pre_ping, a primeira query depois disso falha.
        "pool_pre_ping": True,
        # Descarta conexoes antigas antes que o provedor as feche sozinho.
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 5,
    }
