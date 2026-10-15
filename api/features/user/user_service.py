from __future__ import annotations

from pwdlib import PasswordHash

from api.features.user.user import User, UserRole
from api.features.user.user_repository import UserRepository
from api.features.user.user_schemas import TokenOut, UserCreateIn, UserLoginIn, UserUpdateIn
from api.shared.exceptions import (
    BadRequestError,
    ErrorCode,
    ForbiddenError,
    ResourceNotFoundError,
    UnauthorizedError,
)
from api.shared.image_storage import PROFILE_PICTURES_FOLDER, ImageStorage, StoredImage
from api.shared.security import create_access_token

password_hash = PasswordHash.recommended()


class UserService:
    def __init__(self, repository: UserRepository, image_storage: ImageStorage) -> None:
        self.repository = repository
        self.image_storage = image_storage

    async def create(self, payload: UserCreateIn) -> User:
        user_data = payload.model_dump(exclude={"password"})
        user = User(
            **user_data,
            password_hash=password_hash.hash(payload.password),
        )
        if user.role == UserRole.ADMIN:
            raise BadRequestError(
                "Admin users cannot be created",
                code=ErrorCode.INVALID_CREDENTIALS,
            )
        return await self.repository.create(user)

    async def login(self, payload: UserLoginIn) -> TokenOut:
        user = await self.repository.get_by_email(payload.email)
        if user is None or not password_hash.verify(payload.password, user.password_hash):
            raise UnauthorizedError(
                "Invalid email or password",
                code=ErrorCode.INVALID_CREDENTIALS,
            )
        if not user.is_active:
            raise UnauthorizedError(
                "Inactive user",
                code=ErrorCode.INVALID_CREDENTIALS,
            )
        return self.create_token(user)

    def create_token(self, user: User) -> TokenOut:
        return TokenOut(access_token=create_access_token(user))

    async def ensure_default_admin(self) -> User | None:
        admin = await self.repository.get_first_admin()
        if admin is not None:
            return None

        user = User(
            role=UserRole.ADMIN,
            password_hash=password_hash.hash("admin123"),
            email="admin@example.com",
            name="super_user",
            last_name="admin",
            is_active=True,
            ra=None,
            birth_date=None,
        )
        return await self.repository.create(user)

    async def list_all(self) -> list[User]:
        return await self.repository.list_all()

    async def get_by_id(self, user_id: int) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise ResourceNotFoundError(
                f"User {user_id} not found",
                code=ErrorCode.USER_NOT_FOUND,
                details={"user_id": user_id},
            )
        return user

    async def update(self, user_id: int, payload: UserUpdateIn) -> User:
        user = await self.get_by_id(user_id)
        for field, value in payload.model_dump(exclude={"password"}).items():
            setattr(user, field, value)
        user.password_hash = password_hash.hash(payload.password)
        return await self.repository.update(user)

    async def update_profile_picture(
        self, user_id: int, profile_picture: bytes, current_user: User
    ) -> User:
        user = await self.get_by_id(user_id)
        _ensure_can_change_profile_picture(user, current_user)

        old_public_id = user.profile_picture_public_id
        _set_profile_picture(
            user, await self.image_storage.upload(profile_picture, PROFILE_PICTURES_FOLDER)
        )
        user = await self.repository.update(user)

        # So depois de salvar: a foto antiga nao e mais usada por ninguem.
        if old_public_id:
            await self.image_storage.delete(old_public_id)
        return user

    async def delete_profile_picture(self, user_id: int, current_user: User) -> None:
        user = await self.get_by_id(user_id)
        _ensure_can_change_profile_picture(user, current_user)
        if user.profile_picture_url is None:
            raise _profile_picture_not_found(user_id)

        public_id = user.profile_picture_public_id
        _set_profile_picture(user, None)
        await self.repository.update(user)

        if public_id:
            await self.image_storage.delete(public_id)

    async def get_profile_picture_url(self, user_id: int) -> str:
        user = await self.get_by_id(user_id)
        if user.profile_picture_url is None:
            raise _profile_picture_not_found(user_id)
        return user.profile_picture_url

    async def delete(self, user_id: int) -> None:
        user = await self.get_by_id(user_id)
        profile_picture_public_id = user.profile_picture_public_id
        await self.repository.delete(user)

        # So depois de excluir o usuario: a foto dele nao e mais usada.
        if profile_picture_public_id:
            await self.image_storage.delete(profile_picture_public_id)


def _ensure_can_change_profile_picture(user: User, current_user: User) -> None:
    # Trocar ou remover a foto apaga a anterior do Cloudinary de vez, entao
    # so o proprio usuario ou um admin pode fazer isso.
    if current_user.id != user.id and current_user.role != UserRole.ADMIN:
        raise ForbiddenError(
            "Only the user or an admin can change this profile picture",
            code=ErrorCode.PERMISSION_DENIED,
        )


def _profile_picture_not_found(user_id: int) -> ResourceNotFoundError:
    return ResourceNotFoundError(
        f"User {user_id} profile picture not found",
        code=ErrorCode.USER_PROFILE_PICTURE_NOT_FOUND,
        details={"user_id": user_id},
    )


def _set_profile_picture(user: User, image: StoredImage | None) -> None:
    user.profile_picture_url = image.url if image else None
    user.profile_picture_public_id = image.public_id if image else None
