from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.features.event.event import Event
from api.features.subscription.subscription import EventSubscription


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, user_id: int, event_id: int) -> EventSubscription | None:
        statement = select(EventSubscription).where(
            EventSubscription.user_id == user_id,
            EventSubscription.event_id == event_id,
        )
        return await self.session.scalar(statement)

    async def count_by_event(self, event_id: int) -> int:
        statement = select(func.count(EventSubscription.id)).where(
            EventSubscription.event_id == event_id
        )
        return await self.session.scalar(statement) or 0

    async def create(self, subscription: EventSubscription) -> EventSubscription:
        self.session.add(subscription)
        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription

    async def delete(self, subscription: EventSubscription) -> None:
        await self.session.delete(subscription)
        await self.session.commit()

    async def list_events_by_user(self, user_id: int) -> list[Event]:
        statement = (
            select(Event)
            .join(EventSubscription, EventSubscription.event_id == Event.id)
            .where(EventSubscription.user_id == user_id)
            .order_by(Event.id)
        )
        result = await self.session.scalars(statement)
        return list(result)
