from __future__ import annotations

from database.config.urls import (
    async_connect_args,
    async_engine_options,
    to_async_url,
    to_sync_url,
)

# String no formato que o Neon entrega ao criar o banco.
NEON_URL = (
    "postgresql://user:s3cr3t@ep-cool-name-123456-pooler.sa-east-1.aws.neon.tech/"
    "neondb?sslmode=require&channel_binding=require"
)


def test_to_async_url_converts_sqlite_to_aiosqlite() -> None:
    assert to_async_url("sqlite:///./database/app.db") == "sqlite+aiosqlite:///./database/app.db"


def test_to_async_url_keeps_already_async_sqlite_url() -> None:
    database_url = "sqlite+aiosqlite:///already-async.db"

    assert to_async_url(database_url) == database_url


def test_to_async_url_converts_postgres_to_asyncpg() -> None:
    assert to_async_url(NEON_URL).startswith("postgresql+asyncpg://")


def test_to_async_url_drops_params_that_asyncpg_rejects() -> None:
    converted = to_async_url(NEON_URL)

    assert "sslmode" not in converted
    assert "channel_binding" not in converted


def test_to_async_url_keeps_credentials_and_host() -> None:
    converted = to_async_url(NEON_URL)

    assert "user:s3cr3t@" in converted
    assert "ep-cool-name-123456-pooler.sa-east-1.aws.neon.tech/neondb" in converted


def test_to_async_url_accepts_legacy_postgres_scheme() -> None:
    assert to_async_url("postgres://user:pw@host/db").startswith("postgresql+asyncpg://")


def test_to_sync_url_converts_postgres_to_psycopg() -> None:
    assert to_sync_url(NEON_URL).startswith("postgresql+psycopg://")


def test_to_sync_url_keeps_sslmode_because_psycopg_understands_it() -> None:
    assert "sslmode=require" in to_sync_url(NEON_URL)


def test_to_sync_url_makes_sqlite_synchronous_again() -> None:
    assert to_sync_url("sqlite+aiosqlite:///app.db") == "sqlite:///app.db"


def test_async_connect_args_for_sqlite_allows_other_threads() -> None:
    assert async_connect_args("sqlite:///app.db") == {"check_same_thread": False}


def test_async_connect_args_for_postgres_require_tls_and_disable_statement_cache() -> None:
    connect_args = async_connect_args(NEON_URL)

    assert connect_args["ssl"] == "require"
    assert connect_args["statement_cache_size"] == 0


def test_async_engine_options_for_postgres_recycle_idle_connections() -> None:
    options = async_engine_options(NEON_URL)

    assert options["pool_pre_ping"] is True
    assert options["pool_recycle"] == 300


def test_async_engine_options_are_empty_for_sqlite() -> None:
    assert async_engine_options("sqlite:///app.db") == {}
