from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.orm import Mapped, column_property, mapped_column

from api.features.subscription.subscription import EventSubscription
from database.config.base import Base


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "max_participants IS NULL OR max_participants > 0",
            name="ck_events_max_participants_positive",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # Link da imagem no Cloudinary. O arquivo em si nao fica no banco.
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Identificador da imagem no Cloudinary, usado para apaga-la de la.
    image_public_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    event_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_location: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Limite de inscricoes do evento. Nulo significa sem limite.
    max_participants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Calculado pelo banco a cada consulta do evento; nao e uma coluna.
    subscribers_count: Mapped[int] = column_property(
        select(func.count(EventSubscription.id))
        .where(EventSubscription.event_id == id)
        .correlate_except(EventSubscription)
        .scalar_subquery()
    )

    @property
    def available_spots(self) -> int | None:
        if self.max_participants is None:
            return None
        return max(self.max_participants - self.subscribers_count, 0)

    @property
    def is_full(self) -> bool:
        return self.available_spots == 0
