from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database.config.base import Base


class EventSubscription(Base):
    __tablename__ = "event_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_event_subscriptions_user_event"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    # Quando a presenca foi confirmada (UTC). Nulo = presenca nao confirmada.
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
