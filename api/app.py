from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.features.event.event_controller import router as event_router
from api.features.subscription.subscription_controller import router as subscription_router
from api.features.user.user_controller import router as user_router
from api.features.user.user_repository import UserRepository
from api.features.user.user_service import UserService
from api.shared.exceptions import UnhandledExceptionMiddleware, register_exception_handlers
from database.config.session import DatabaseManager
from database.config.settings import settings


def create_app(database_url: str | None = None) -> FastAPI:
    database_manager = DatabaseManager(database_url=database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # As tabelas sao criadas e alteradas pelo Alembic, no deploy.
        # A aplicacao nao mexe no formato do banco ao subir.
        app.state.database_manager = database_manager
        if settings.seed_default_admin:
            async with database_manager.session_factory() as session:
                service = UserService(UserRepository(session))
                await service.ensure_default_admin()
        yield
        await database_manager.dispose()

    app = FastAPI(title="Campus Cultural API", lifespan=lifespan)

    app.add_middleware(UnhandledExceptionMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.get("/health")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(user_router)
    app.include_router(subscription_router)
    app.include_router(event_router)
    return app


app = create_app()
