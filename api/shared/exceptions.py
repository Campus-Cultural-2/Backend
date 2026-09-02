from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class ErrorCode(StrEnum):
    INVALID_CREDENTIALS = "invalid_credentials"
    INVALID_TOKEN = "invalid_token"
    USER_PROFILE_PICTURE_NOT_FOUND = "user_profile_picture_not_found"
    USER_NOT_FOUND = "user_not_found"
    USER_EMAIL_ALREADY_EXISTS = "user_email_already_exists"
    USER_RA_ALREADY_EXISTS = "user_ra_already_exists"
    VALIDATION_ERROR = "validation_error"
    INTERNAL_ERROR = "internal_error"
    EVENT_NOT_FOUND = "event_not_found"
    EVENT_ALREADY_SUBSCRIBED = "event_already_subscribed"
    EVENT_SUBSCRIPTION_NOT_FOUND = "event_subscription_not_found"


class AppError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(message)

    def to_response(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload


class ResourceNotFoundError(AppError):
    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode = ErrorCode.USER_NOT_FOUND,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ConflictError(AppError):
    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class UnauthorizedError(AppError):
    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class BadRequestError(AppError):
    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    headers = (
        {"WWW-Authenticate": "Bearer"} if exc.status_code == status.HTTP_401_UNAUTHORIZED else None
    )
    return JSONResponse(status_code=exc.status_code, content=exc.to_response(), headers=headers)


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": ErrorCode.VALIDATION_ERROR,
            "message": "Dados de entrada invalidos",
            "details": {"errors": jsonable_encoder(exc.errors())},
        },
    )


async def internal_error_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": ErrorCode.INTERNAL_ERROR,
            "message": "Erro interno do servidor",
            "details": {"error_type": exc.__class__.__name__},
        },
    )


class UnhandledExceptionMiddleware(BaseHTTPMiddleware):
    """Converte excecoes nao tratadas em uma resposta 500 antes que elas escapem
    para o ServerErrorMiddleware do Starlette."""

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001
            return await internal_error_handler(request, exc)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, internal_error_handler)
