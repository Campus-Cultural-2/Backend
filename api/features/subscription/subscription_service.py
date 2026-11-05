from __future__ import annotations

from datetime import datetime

from api.features.event.event import Event
from api.features.event.event_repository import EventRepository
from api.features.subscription.subscription import EventSubscription
from api.features.subscription.subscription_repository import SubscriptionRepository
from api.features.user.user import User, UserRole
from api.shared.exceptions import (
    ConflictError,
    ErrorCode,
    ForbiddenError,
    ResourceNotFoundError,
)


class SubscriptionService:
    def __init__(
        self,
        repository: SubscriptionRepository,
        event_repository: EventRepository,
    ) -> None:
        self.repository = repository
        self.event_repository = event_repository

    async def subscribe(self, event_id: int, user: User) -> EventSubscription:
        event = await self.event_repository.get_by_id_for_update(event_id)
        if event is None:
            raise ResourceNotFoundError(
                f"Event {event_id} not found",
                code=ErrorCode.EVENT_NOT_FOUND,
                details={"event_id": event_id},
            )

        existing = await self.repository.get(user.id, event_id)
        if existing is not None:
            raise ConflictError(
                "User is already subscribed to this event",
                code=ErrorCode.EVENT_ALREADY_SUBSCRIBED,
                details={"event_id": event_id},
            )

        if event.max_participants is not None:
            subscribers_count = await self.repository.count_by_event(event_id)
            if subscribers_count >= event.max_participants:
                raise ConflictError(
                    "Event has reached its participant limit",
                    code=ErrorCode.EVENT_FULL,
                    details={
                        "event_id": event_id,
                        "max_participants": event.max_participants,
                    },
                )

        subscription = EventSubscription(user_id=user.id, event_id=event_id)
        return await self.repository.create(subscription)

    async def unsubscribe(self, event_id: int, user: User) -> None:
        subscription = await self.repository.get(user.id, event_id)
        if subscription is None:
            raise ResourceNotFoundError(
                f"Subscription for event {event_id} not found",
                code=ErrorCode.EVENT_SUBSCRIPTION_NOT_FOUND,
                details={"event_id": event_id},
            )

        await self.repository.delete(subscription)

    async def list_my_events(self, user: User) -> list[Event]:
        return await self.repository.list_events_by_user(user.id)

    async def list_event_subscribers(
        self, event_id: int, current_user: User
    ) -> list[tuple[User, datetime]]:
        event = await self.event_repository.get_by_id(event_id)
        if event is None:
            raise ResourceNotFoundError(
                f"Event {event_id} not found",
                code=ErrorCode.EVENT_NOT_FOUND,
                details={"event_id": event_id},
            )

        _ensure_can_view_subscribers(event, current_user)
        return await self.repository.list_subscribers_by_event(event_id)


def _ensure_can_view_subscribers(event: Event, current_user: User) -> None:
    # A lista tem e-mail e RA dos inscritos: so o dono do evento e os admins a veem.
    if event.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise ForbiddenError(
            "Only the event owner or an admin can view its subscribers",
            code=ErrorCode.PERMISSION_DENIED,
            details={"event_id": event.id},
        )
