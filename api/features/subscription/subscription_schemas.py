from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from api.features.user.user import User, UserRole


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    event_id: int
    created_at: datetime


class EventSubscriberOut(BaseModel):
    # So os dados necessarios para identificar o inscrito: a lista expoe dados
    # pessoais de alunos, entao data de nascimento, status e senha ficam de fora.
    user_id: int
    name: str
    last_name: str | None
    email: str
    ra: str | None
    role: UserRole
    subscribed_at: datetime

    @classmethod
    def from_subscription(cls, user: User, subscribed_at: datetime) -> EventSubscriberOut:
        return cls(
            user_id=user.id,
            name=user.name,
            last_name=user.last_name,
            email=user.email,
            ra=user.ra,
            role=user.role,
            subscribed_at=subscribed_at,
        )
