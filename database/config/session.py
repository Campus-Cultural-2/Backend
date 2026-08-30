from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from database.config.base import Base
from database.config.settings import get_database_url
from database.config.urls import async_connect_args, async_engine_options, to_async_url


class DatabaseManager:
    def __init__(self, database_url: str | None = None) -> None:
        configured_database_url = database_url or get_database_url()
        self.engine: AsyncEngine = create_async_engine(
            to_async_url(configured_database_url),
            connect_args=async_connect_args(configured_database_url),
            **async_engine_options(configured_database_url),
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def create_tables(self) -> None:
        """Cria as tabelas direto pelos modelos.

        Usado apenas pelos testes. Em producao quem cria e altera as tabelas
        e o Alembic (`uv run task db-upgrade`), para haver uma unica fonte
        de verdade sobre o formato do banco.
        """
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self.engine.dispose()

    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.session_factory() as session:
            yield session
