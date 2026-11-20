from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from api.features.event.event import AttendanceMode, Event
from api.features.event.event_repository import EventRepository
from api.features.subscription.subscription import EventSubscription
from api.features.subscription.subscription_repository import SubscriptionRepository
from api.features.user.user import User, UserRole
from api.shared.attendance_codes import (
    event_code,
    is_valid_event_code,
    parse_student_code,
)
from api.shared.exceptions import (
    BadRequestError,
    ConflictError,
    ErrorCode,
    ForbiddenError,
    ResourceNotFoundError,
)


@dataclass
class Participant:
    user_id: int
    name: str
    last_name: str
    ra: str | None
    attended: bool
    checked_in_at: datetime | None


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    # O banco pode devolver datas sem fuso; elas sao tratadas como UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class AttendanceService:
    def __init__(
        self,
        repository: SubscriptionRepository,
        event_repository: EventRepository,
    ) -> None:
        self.repository = repository
        self.event_repository = event_repository

    async def get_event_code(self, event_id: int, current_user: User) -> str:
        event = await self._get_managed_event(event_id, current_user)
        _ensure_mode(event, AttendanceMode.STUDENT)
        return event_code(event.id)

    async def list_participants(self, event_id: int, current_user: User) -> list[Participant]:
        event = await self._get_managed_event(event_id, current_user)
        rows = await self.repository.list_with_users(event.id)
        return [_participant(event, subscription, user) for subscription, user in rows]

    async def set_attendance(
        self, event_id: int, user_id: int, present: bool, current_user: User
    ) -> Participant:
        """Confirmacao manual (checkbox) feita pelo professor ou admin."""
        event = await self._get_managed_event(event_id, current_user)
        _ensure_mode(event, AttendanceMode.PROFESSOR)
        _ensure_event_started(event)
        subscription = await self._get_subscription(event.id, user_id)
        subscription.checked_in_at = _now().replace(tzinfo=None) if present else None
        subscription = await self.repository.update(subscription)
        return await self._participant_of(event, subscription)

    async def scan_student_code(self, event_id: int, code: str, current_user: User) -> Participant:
        """Professor le o QR code do aluno para confirmar a presenca dele."""
        event = await self._get_managed_event(event_id, current_user)
        _ensure_mode(event, AttendanceMode.PROFESSOR)
        _ensure_event_started(event)
        user_id = parse_student_code(event.id, code)
        if user_id is None:
            raise _invalid_code_error()
        subscription = await self._get_subscription(event.id, user_id)
        return await self._confirm(event, subscription)

    async def check_in(self, event_id: int, code: str, current_user: User) -> Participant:
        """Aluno le o codigo do evento para confirmar a propria presenca."""
        event = await self._get_event(event_id)
        _ensure_mode(event, AttendanceMode.STUDENT)
        subscription = await self._get_subscription(event.id, current_user.id)
        _ensure_event_started(event)
        if _now() > _as_utc(event.event_end_datetime):
            raise ConflictError(
                "Attendance can only be confirmed while the event is happening",
                code=ErrorCode.ATTENDANCE_WINDOW_CLOSED,
                details={"event_id": event.id, "reason": "ended"},
            )
        if not is_valid_event_code(event.id, code):
            raise _invalid_code_error()
        return await self._confirm(event, subscription)

    async def _confirm(self, event: Event, subscription: EventSubscription) -> Participant:
        # Ler o codigo de novo nao muda a hora da primeira leitura.
        if subscription.checked_in_at is None:
            subscription.checked_in_at = _now().replace(tzinfo=None)
            subscription = await self.repository.update(subscription)
        return await self._participant_of(event, subscription)

    async def _participant_of(self, event: Event, subscription: EventSubscription) -> Participant:
        for sub, user in await self.repository.list_with_users(event.id):
            if sub.id == subscription.id:
                return _participant(event, sub, user)
        raise AssertionError("subscription disappeared")  # pragma: no cover

    async def _get_event(self, event_id: int) -> Event:
        event = await self.event_repository.get_by_id(event_id)
        if event is None:
            raise ResourceNotFoundError(
                f"Event {event_id} not found",
                code=ErrorCode.EVENT_NOT_FOUND,
                details={"event_id": event_id},
            )
        return event

    async def _get_managed_event(self, event_id: int, current_user: User) -> Event:
        event = await self._get_event(event_id)
        if current_user.role != UserRole.ADMIN and event.user_id != current_user.id:
            raise ForbiddenError(
                "Only the event owner or an admin can manage attendance",
                code=ErrorCode.PERMISSION_DENIED,
            )
        return event

    async def _get_subscription(self, event_id: int, user_id: int) -> EventSubscription:
        subscription = await self.repository.get(user_id, event_id)
        if subscription is None:
            raise ResourceNotFoundError(
                f"Subscription for event {event_id} not found",
                code=ErrorCode.EVENT_SUBSCRIPTION_NOT_FOUND,
                details={"event_id": event_id, "user_id": user_id},
            )
        return subscription


def _participant(event: Event, subscription: EventSubscription, user: User) -> Participant:
    return Participant(
        user_id=user.id,
        name=user.name,
        last_name=user.last_name,
        ra=user.ra,
        attended=event.attendance_mode == AttendanceMode.NONE
        or subscription.checked_in_at is not None,
        checked_in_at=subscription.checked_in_at,
    )


def _ensure_mode(event: Event, mode: AttendanceMode) -> None:
    if event.attendance_mode != mode:
        raise ConflictError(
            f"This event does not use '{mode.value}' attendance confirmation",
            code=ErrorCode.ATTENDANCE_MODE_MISMATCH,
            details={"attendance_mode": event.attendance_mode.value},
        )


def _ensure_event_started(event: Event) -> None:
    if _now() < _as_utc(event.event_datetime):
        raise ConflictError(
            "Attendance cannot be confirmed before the event starts",
            code=ErrorCode.ATTENDANCE_WINDOW_CLOSED,
            details={"event_id": event.id, "reason": "not_started"},
        )


def _invalid_code_error() -> BadRequestError:
    return BadRequestError(
        "Invalid attendance code",
        code=ErrorCode.INVALID_ATTENDANCE_CODE,
    )
