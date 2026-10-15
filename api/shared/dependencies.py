from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api.features.event.event_repository import EventRepository
from api.features.event.event_service import EventService
from api.features.subscription.subscription_repository import SubscriptionRepository
from api.features.subscription.subscription_service import SubscriptionService
from api.features.user.user import User
from api.features.user.user_repository import UserRepository
from api.features.user.user_service import UserService
from api.shared.exceptions import ErrorCode, ResourceNotFoundError, UnauthorizedError
from api.shared.image_storage import ImageStorage
from api.shared.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async for session in request.app.state.database_manager.session():
        yield session


def get_image_storage() -> ImageStorage:
    return ImageStorage()


def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    image_storage: Annotated[ImageStorage, Depends(get_image_storage)],
) -> UserService:
    repository = UserRepository(session)
    return UserService(repository, image_storage)


def get_event_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    image_storage: Annotated[ImageStorage, Depends(get_image_storage)],
) -> EventService:
    repository = EventRepository(session)
    return EventService(repository, image_storage)


def get_subscription_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SubscriptionService:
    repository = SubscriptionRepository(session)
    event_repository = EventRepository(session)
    return SubscriptionService(repository, event_repository)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> User:
    if credentials is None:
        raise UnauthorizedError("Missing bearer token", code=ErrorCode.INVALID_TOKEN)

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError, jwt.PyJWTError) as exc:
        raise UnauthorizedError("Invalid token", code=ErrorCode.INVALID_TOKEN) from exc

    try:
        user = await service.get_by_id(user_id)
    except ResourceNotFoundError as exc:
        raise UnauthorizedError("Invalid token", code=ErrorCode.INVALID_TOKEN) from exc
    if not user.is_active:
        raise UnauthorizedError("Inactive user", code=ErrorCode.INVALID_TOKEN)
    return user
