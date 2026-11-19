from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class PasswordResetRequestIn(BaseModel):
    email: str


class PasswordResetRequestOut(BaseModel):
    # A mesma resposta para qualquer e-mail, cadastrado ou nao, para a API nao
    # revelar quem tem conta. E o mesmo motivo do login devolver "e-mail ou
    # senha invalidos" sem dizer qual dos dois.
    message: str = "Se o e-mail estiver cadastrado, enviaremos um código para ele."


class PasswordResetConfirmIn(BaseModel):
    email: str
    code: str
    # O app exige ao menos 8 caracteres, um numero e um caractere especial. Aqui
    # fica so o minimo de tamanho: validacao no app ajuda o usuario, mas a API
    # precisa recusar por conta propria o que chegar direto por ela.
    new_password: str = Field(min_length=8)
