from __future__ import annotations

from dataclasses import dataclass

from pwdlib import PasswordHash

from api.features.user.user import User, UserRole
from api.features.user.user_repository import UserRepository
from api.features.user.user_schemas import (
    EmailVerificationConfirmIn,
    PasswordResetConfirmIn,
    TokenOut,
    UserCreateIn,
    UserLoginIn,
    UserUpdateIn,
)
from api.shared import email_verification_codes
from api.shared.email_codes import EmailThrottle
from api.shared.exceptions import (
    BadRequestError,
    ErrorCode,
    ForbiddenError,
    ResourceNotFoundError,
    UnauthorizedError,
)
from api.shared.image_storage import PROFILE_PICTURES_FOLDER, ImageStorage, StoredImage
from api.shared.password_reset_codes import (
    PasswordResetThrottle,
    is_valid_code,
    issue_code,
    password_reset_throttle,
)
from api.shared.security import create_access_token
from database.config.settings import settings

password_hash = PasswordHash.recommended()

# Papeis com acesso ao gerenciamento de usuarios.
MANAGER_ROLES = frozenset({UserRole.PROFESSOR, UserRole.ADMIN})


@dataclass(frozen=True)
class EmailCodeMessage:
    """O que precisa ir num e-mail com codigo: para quem, o nome e o codigo."""

    email: str
    name: str
    code: str


# Nome usado pela recuperacao de senha, mantido para quem ja importava.
PasswordResetMessage = EmailCodeMessage


class UserService:
    def __init__(
        self,
        repository: UserRepository,
        image_storage: ImageStorage,
        reset_throttle: PasswordResetThrottle | None = None,
        verification_throttle: EmailThrottle | None = None,
    ) -> None:
        self.repository = repository
        self.image_storage = image_storage
        self.reset_throttle = reset_throttle or password_reset_throttle
        self.verification_throttle = (
            verification_throttle or email_verification_codes.email_verification_throttle
        )

    async def request_password_reset(self, email: str) -> PasswordResetMessage | None:
        """Decide se um codigo de recuperacao deve ser enviado, e qual.

        Devolve None quando nao ha o que enviar: e-mail sem conta, conta
        inativa, ou um pedido para o mesmo e-mail ha menos de um minuto. Quem
        chama devolve a mesma resposta nos dois casos, para nao revelar quais
        e-mails tem conta.
        """
        user = await self.repository.get_by_email(email.strip())
        if user is None or not user.is_active:
            return None
        if not self.reset_throttle.allow(user.email):
            return None
        return PasswordResetMessage(
            email=user.email,
            name=user.name,
            code=issue_code(user.id, user.password_hash),
        )

    async def confirm_password_reset(self, payload: PasswordResetConfirmIn) -> None:
        user = await self.repository.get_by_email(payload.email.strip())
        # A mesma mensagem para e-mail inexistente, conta inativa e codigo
        # errado ou vencido, pelo mesmo motivo do pedido.
        if (
            user is None
            or not user.is_active
            or not is_valid_code(user.id, user.password_hash, payload.code)
        ):
            raise BadRequestError(
                "Invalid or expired code",
                code=ErrorCode.INVALID_PASSWORD_RESET_CODE,
            )
        # Trocar o hash invalida o codigo usado, que dependia do hash antigo.
        user.password_hash = password_hash.hash(payload.new_password)
        await self.repository.update(user)

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
        _ensure_email_domain_allowed(payload.email, payload.role)
        # A conta nasce sem verificacao, e so faz login depois de confirmar o
        # codigo enviado ao e-mail. A excecao e o ambiente local sem Brevo:
        # sem ter como enviar o codigo, ninguem conseguiria terminar um
        # cadastro. Em producao isso nao acontece, porque a guarda de producao
        # exige o Brevo configurado; a checagem de is_production e uma segunda
        # garantia.
        user.email_verified = not settings.is_production and not settings.is_email_configured
        return await self.repository.create(user)

    def build_email_verification_message(self, user: User) -> EmailCodeMessage | None:
        """Codigo para o primeiro envio, logo depois do cadastro."""
        if user.email_verified:
            return None
        return EmailCodeMessage(
            email=user.email,
            name=user.name,
            code=email_verification_codes.issue_code(user.id, user.email),
        )

    async def request_email_verification(self, email: str) -> EmailCodeMessage | None:
        """Reenvio do codigo de verificacao.

        Devolve None quando nao ha o que enviar: e-mail sem conta, conta
        inativa, conta ja verificada, ou um pedido para o mesmo e-mail ha menos
        de um minuto. Quem chama responde igual nos dois casos.
        """
        user = await self.repository.get_by_email(email.strip())
        if user is None or not user.is_active or user.email_verified:
            return None
        if not self.verification_throttle.allow(user.email):
            return None
        return self.build_email_verification_message(user)

    async def confirm_email_verification(self, payload: EmailVerificationConfirmIn) -> None:
        user = await self.repository.get_by_email(payload.email.strip())
        # A mesma mensagem para e-mail inexistente, conta inativa e codigo
        # errado ou vencido.
        if (
            user is None
            or not user.is_active
            or not email_verification_codes.is_valid_code(user.id, user.email, payload.code)
        ):
            raise BadRequestError(
                "Invalid or expired code",
                code=ErrorCode.INVALID_EMAIL_VERIFICATION_CODE,
            )
        if not user.email_verified:
            user.email_verified = True
            await self.repository.update(user)

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
        # Depois da senha, de proposito: so quem ja provou ser dono da conta
        # fica sabendo que ela existe e falta verificar.
        if not user.email_verified:
            raise ForbiddenError(
                "Email not verified",
                code=ErrorCode.EMAIL_NOT_VERIFIED,
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
            email_verified=True,
        )
        return await self.repository.create(user)

    async def list_all(
        self,
        current_user: User,
        *,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> list[User]:
        _ensure_is_manager(current_user)
        return await self.repository.list_all(role=role, is_active=is_active)

    async def get_by_id(self, user_id: int) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise ResourceNotFoundError(
                f"User {user_id} not found",
                code=ErrorCode.USER_NOT_FOUND,
                details={"user_id": user_id},
            )
        return user

    async def get_visible_by_id(self, user_id: int, current_user: User) -> User:
        if current_user.id != user_id:
            _ensure_is_manager(current_user)
        return await self.get_by_id(user_id)

    async def update(self, user_id: int, payload: UserUpdateIn, current_user: User) -> User:
        user = await self.get_by_id(user_id)
        if current_user.id == user.id:
            _ensure_keeps_own_access(user, payload)
        else:
            _ensure_can_manage(user, current_user)
            if payload.role == UserRole.ADMIN and current_user.role != UserRole.ADMIN:
                raise _admin_only_error()

        for field, value in payload.model_dump(exclude={"password"}).items():
            setattr(user, field, value)
        if payload.password is not None:
            user.password_hash = password_hash.hash(payload.password)
        return await self.repository.update(user)

    async def set_active(self, user_id: int, is_active: bool, current_user: User) -> User:
        user = await self.get_by_id(user_id)
        _ensure_can_manage(user, current_user)
        user.is_active = is_active
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

    async def delete(self, user_id: int, current_user: User) -> None:
        user = await self.get_by_id(user_id)
        _ensure_can_manage(user, current_user)
        profile_picture_public_id = user.profile_picture_public_id
        await self.repository.delete(user)

        # So depois de excluir o usuario: a foto dele nao e mais usada.
        if profile_picture_public_id:
            await self.image_storage.delete(profile_picture_public_id)


def _email_domain(email: str) -> str:
    _, separator, domain = email.strip().rpartition("@")
    return domain.lower() if separator else ""


def _ensure_email_domain_allowed(email: str, role: UserRole) -> None:
    # Comparacao pelo dominio exato. "alunos.utfpr.edu.br" termina com
    # "utfpr.edu.br": comparar pelo final aceitaria qualquer aluno como
    # servidor. Lista vazia quer dizer sem restricao.
    domain = _email_domain(email)

    allowed = settings.allowed_email_domains_list
    if allowed and domain not in allowed:
        raise BadRequestError(
            "Email domain not allowed",
            code=ErrorCode.EMAIL_DOMAIN_NOT_ALLOWED,
            details={"field": "email"},
        )

    # So o dominio nao basta, porque qualquer um digita qualquer endereco. E a
    # verificacao do e-mail que garante que a pessoa recebe mensagens nele.
    professor_domains = settings.professor_email_domains_list
    if role == UserRole.PROFESSOR and professor_domains and domain not in professor_domains:
        raise BadRequestError(
            "Professors must use a staff email address",
            code=ErrorCode.EMAIL_DOMAIN_NOT_ALLOWED,
            details={"field": "email", "role": "professor"},
        )


def _ensure_is_manager(current_user: User) -> None:
    if current_user.role not in MANAGER_ROLES:
        raise ForbiddenError(
            "Only professors and admins can manage users",
            code=ErrorCode.PERMISSION_DENIED,
        )


def _ensure_can_manage(user: User, current_user: User) -> None:
    _ensure_is_manager(current_user)
    # Impede que um gestor se desative ou se exclua e perca o proprio acesso.
    if current_user.id == user.id:
        raise ForbiddenError(
            "Users cannot manage their own account",
            code=ErrorCode.PERMISSION_DENIED,
        )
    if user.role == UserRole.ADMIN and current_user.role != UserRole.ADMIN:
        raise _admin_only_error()


def _ensure_keeps_own_access(user: User, payload: UserUpdateIn) -> None:
    # Pelo proprio perfil o usuario edita os dados dele, mas nao o papel nem o status.
    if payload.role != user.role or payload.is_active != user.is_active:
        raise ForbiddenError(
            "Users cannot change their own role or status",
            code=ErrorCode.PERMISSION_DENIED,
        )


def _admin_only_error() -> ForbiddenError:
    return ForbiddenError(
        "Only admins can manage admin users",
        code=ErrorCode.PERMISSION_DENIED,
    )


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
