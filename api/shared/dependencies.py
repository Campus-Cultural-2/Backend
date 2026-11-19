from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api.features.attendance.attendance_service import AttendanceService
from api.features.event.event_repository import EventRepository
from api.features.event.event_service import EventService
from api.features.subscription.subscription_repository import SubscriptionRepository
from api.features.subscription.subscription_service import SubscriptionService
from api.features.user.user import User
from api.features.user.user_repository import UserRepository
from api.features.user.user_service import UserService
from api.shared.email_codes import EmailThrottle
from api.shared.email_sender import EmailSender
from api.shared.email_verification_codes import email_verification_throttle
from api.shared.exceptions import ErrorCode, ResourceNotFoundError, UnauthorizedError
from api.shared.image_storage import ImageStorage
from api.shared.password_reset_codes import PasswordResetThrottle, password_reset_throttle
from api.shared.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async for session in request.app.state.database_manager.session():
        yield session


def get_image_storage() -> ImageStorage:
    return ImageStorage()


def get_email_sender() -> EmailSender:
    return EmailSender()


def get_password_reset_throttle() -> PasswordResetThrottle:
    return password_reset_throttle


def get_email_verification_throttle() -> EmailThrottle:
    return email_verification_throttle


def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    image_storage: Annotated[ImageStorage, Depends(get_image_storage)],
    reset_throttle: Annotated[PasswordResetThrottle, Depends(get_password_reset_throttle)],
    verification_throttle: Annotated[EmailThrottle, Depends(get_email_verification_throttle)],
) -> UserService:
    repository = UserRepository(session)
    return UserService(repository, image_storage, reset_throttle, verification_throttle)


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


def get_attendance_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AttendanceService:
    return AttendanceService(SubscriptionRepository(session), EventRepository(session))


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
