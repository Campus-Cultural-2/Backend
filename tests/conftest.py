from __future__ import annotations

import asyncio
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from database.config.session import DatabaseManager


async def _create_schema(database_url: str) -> None:
    manager = DatabaseManager(database_url=database_url)
    await manager.create_tables()
    await manager.dispose()


@pytest.fixture
def database_url(tmp_path) -> str:
    """Banco de teste isolado, com as tabelas ja criadas.

    Em producao quem cria e altera as tabelas e o Alembic, no deploy. Nos
    testes criamos direto pelos modelos: e mais rapido e nao depende de
    rodar a fila de migrations a cada teste.
    """
    url = f"sqlite:///{tmp_path / 'test.db'}"
    asyncio.run(_create_schema(url))
    return url


@pytest.fixture
def client(database_url: str) -> Generator[TestClient, None, None]:
    with TestClient(create_app(database_url=database_url)) as test_client:
        yield test_client
