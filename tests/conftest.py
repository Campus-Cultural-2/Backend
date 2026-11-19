from __future__ import annotations

import asyncio
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.shared.dependencies import (
    get_email_sender,
    get_image_storage,
    get_password_reset_throttle,
)
from api.shared.password_reset_codes import PasswordResetThrottle
from database.config.session import DatabaseManager
from tests.fakes import FakeEmailSender, FakeImageStorage


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
def image_storage() -> FakeImageStorage:
    return FakeImageStorage()


@pytest.fixture
def email_sender() -> FakeEmailSender:
    return FakeEmailSender()


@pytest.fixture
def reset_throttle() -> PasswordResetThrottle:
    # Um limitador novo por teste. O de producao e um so para o processo
    # inteiro, e os testes usam os mesmos e-mails: compartilhar faria um
    # teste bloquear o envio do seguinte.
    return PasswordResetThrottle()


@pytest.fixture
def client(
    database_url: str,
    image_storage: FakeImageStorage,
    email_sender: FakeEmailSender,
    reset_throttle: PasswordResetThrottle,
) -> Generator[TestClient, None, None]:
    app = create_app(database_url=database_url)
    app.dependency_overrides[get_image_storage] = lambda: image_storage
    app.dependency_overrides[get_email_sender] = lambda: email_sender
    app.dependency_overrides[get_password_reset_throttle] = lambda: reset_throttle
    with TestClient(app) as test_client:
        yield test_client
