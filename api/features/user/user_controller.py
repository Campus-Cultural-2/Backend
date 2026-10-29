from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Response, status
from fastapi.responses import RedirectResponse

from api.features.user.user import User, UserRole
from api.features.user.user_schemas import (
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
from api.shared.dependencies import get_current_user, get_user_service

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
