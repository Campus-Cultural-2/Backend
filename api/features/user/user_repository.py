from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.features.user.user import User, UserRole
from api.shared.exceptions import ConflictError, ErrorCode


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user: User) -> User:
        self.session.add(user)
        email = user.email
        ra = user.ra
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise self._conflict_error(email=email, ra=ra, exc=exc) from exc
        await self.session.refresh(user)
        return user

    async def list_all(
        self, *, role: UserRole | None = None, is_active: bool | None = None
    ) -> list[User]:
        statement = select(User).order_by(User.id)
        if role is not None:
            statement = statement.where(User.role == role)
        if is_active is not None:
            statement = statement.where(User.is_active == is_active)
        result = await self.session.scalars(statement)
        return list(result)

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_ra(self, ra: str) -> User | None:
        statement = select(User).where(User.ra == ra)
        return await self.session.scalar(statement)

    async def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        return await self.session.scalar(statement)

    async def get_first_admin(self) -> User | None:
        statement = select(User).where(User.role == UserRole.ADMIN).order_by(User.id)
        return await self.session.scalar(statement)

    async def update(self, user: User) -> User:
        self.session.add(user)
        email = user.email
        ra = user.ra
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise self._conflict_error(email=email, ra=ra, exc=exc) from exc
        await self.session.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        await self.session.delete(user)
        await self.session.commit()

    @staticmethod
    def _conflict_error(*, email: str, ra: str | None, exc: IntegrityError) -> ConflictError:
        error_text = str(exc.orig)
        if "users.email" in error_text:
            return ConflictError(
                "A user with this email already exists",
                code=ErrorCode.USER_EMAIL_ALREADY_EXISTS,
                details={"field": "email", "value": email},
            )
        return ConflictError(
            "A user with this RA already exists",
            code=ErrorCode.USER_RA_ALREADY_EXISTS,
            details={"field": "ra", "value": ra},
        )
