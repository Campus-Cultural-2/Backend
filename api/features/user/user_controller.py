from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query, Response, status
from fastapi.responses import RedirectResponse

from api.features.user.user import User, UserRole
from api.features.user.user_schemas import (
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    PasswordResetRequestOut,
    TokenOut,
    UserCreateIn,
    UserCreateOut,
    UserLoginIn,
    UserReadOut,
    UserStatusUpdateIn,
    UserUpdateIn,
    UserUpdateOut,
)
from api.features.user.user_service import UserService
from api.shared.dependencies import get_current_user, get_email_sender, get_user_service
from api.shared.email_sender import EmailSender

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserCreateOut, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserCreateIn,
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserCreateOut:
    return UserCreateOut.model_validate(await service.create(payload))


@router.post("/login", response_model=TokenOut)
async def login_user(
    payload: UserLoginIn,
    service: Annotated[UserService, Depends(get_user_service)],
) -> TokenOut:
    return await service.login(payload)


@router.post(
    "/password-reset/request",
    response_model=PasswordResetRequestOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_password_reset(
    payload: PasswordResetRequestIn,
    background_tasks: BackgroundTasks,
    service: Annotated[UserService, Depends(get_user_service)],
    email_sender: Annotated[EmailSender, Depends(get_email_sender)],
) -> PasswordResetRequestOut:
    message = await service.request_password_reset(payload.email)
    if message is not None:
        # O envio fica para depois da resposta. Assim a resposta demora o
        # mesmo para e-mail cadastrado ou nao, e o tempo dela nao revela quem
        # tem conta. A consulta ao banco ja foi feita acima, antes da sessao
        # fechar.
        background_tasks.add_task(
            email_sender.send_password_reset_code, message.email, message.name, message.code
        )
    return PasswordResetRequestOut()


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_password_reset(
    payload: PasswordResetConfirmIn,
    service: Annotated[UserService, Depends(get_user_service)],
) -> Response:
    await service.confirm_password_reset(payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/refresh-token", response_model=TokenOut)
async def refresh_token(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> TokenOut:
    return service.create_token(current_user)


@router.get("", response_model=list[UserReadOut])
async def list_users(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
    role: Annotated[UserRole | None, Query()] = None,
    is_active: Annotated[bool | None, Query()] = None,
) -> list[UserReadOut]:
    users: list[User] = await service.list_all(current_user, role=role, is_active=is_active)
    users_dto = []
    for user in users:
        users_dto.append(UserReadOut.model_validate(user))
    return users_dto


@router.get("/{user_id}", response_model=UserReadOut)
async def get_user(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserReadOut:
    return UserReadOut.model_validate(await service.get_visible_by_id(user_id, current_user))


@router.put("/{user_id}", response_model=UserUpdateOut)
async def update_user(
    user_id: int,
    payload: UserUpdateIn,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserUpdateOut:
    return UserUpdateOut.model_validate(await service.update(user_id, payload, current_user))


@router.patch("/{user_id}/status", response_model=UserReadOut)
async def update_user_status(
    user_id: int,
    payload: UserStatusUpdateIn,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserReadOut:
    return UserReadOut.model_validate(
        await service.set_active(user_id, payload.is_active, current_user)
    )


@router.post("/{user_id}/profile-picture", response_model=UserReadOut)
async def update_profile_picture(
    user_id: int,
    profile_picture: Annotated[bytes, Body(media_type="application/octet-stream")],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserReadOut:
    return UserReadOut.model_validate(
        await service.update_profile_picture(user_id, profile_picture, current_user)
    )


@router.delete("/{user_id}/profile-picture", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile_picture(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> Response:
    await service.delete_profile_picture(user_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{user_id}/profile-picture")
async def get_profile_picture(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> RedirectResponse:
    # A foto fica no Cloudinary; a API so redireciona para o link dela.
    return RedirectResponse(
        await service.get_profile_picture_url(user_id),
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> Response:
    await service.delete(user_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
