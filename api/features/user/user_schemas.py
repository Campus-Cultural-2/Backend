from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, model_validator

from api.features.user.user import UserRole


class UserBaseSchema(BaseModel):
    role: UserRole
    email: str
    name: str
    last_name: str
    birth_date: date | None = None
    is_active: bool
    ra: str | None = None

    @model_validator(mode="after")
    def validate_ra(self) -> UserBaseSchema:
        if self.role != UserRole.STUDENT and self.ra is not None:
            raise ValueError("ra must be null for non-student users")
        return self


class UserCreateIn(UserBaseSchema):
    password: str


class UserLoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreateOut(UserBaseSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_picture_url: str | None = None


class UserReadOut(UserBaseSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_picture_url: str | None = None


class UserUpdateIn(UserBaseSchema):
    # Sem senha, a senha atual e mantida.
    password: str | None = None


class UserStatusUpdateIn(BaseModel):
    is_active: bool


class UserUpdateOut(UserBaseSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_picture_url: str | None = None
