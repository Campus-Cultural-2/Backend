from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.features.event.event import Event


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, event: Event) -> Event:
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def list_all(self) -> list[Event]:
        result = await self.session.scalars(select(Event).order_by(Event.id))
        return list(result)

    async def get_by_id(self, event_id: int) -> Event | None:
        return await self.session.get(Event, event_id)

    async def get_by_id_for_update(self, event_id: int) -> Event | None:
        # Trava a linha do evento ate o commit, para duas inscricoes
        # simultaneas nao passarem do limite. O SQLite ignora o FOR UPDATE.
        return await self.session.get(Event, event_id, with_for_update=True)

    async def get_by_user_id(self, user_id: int) -> list[Event]:
        statement = select(Event).where(Event.user_id == user_id).order_by(Event.id)
        result = await self.session.scalars(statement)
        return list(result)

    async def update(self, event: Event) -> Event:
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event

    async def delete(self, event: Event) -> None:
        await self.session.delete(event)
        await self.session.commit()
