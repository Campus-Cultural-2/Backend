from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from api.features.event.event import HoursGroup
from database.config.base import Base


def generate_validation_code() -> str:
    return str(uuid4())


class Certificate(Base):
    """Certificado emitido para um aluno inscrito em um evento.

    Cada evento gera um unico certificado (as horas e o grupo configurados no
    evento), e cada aluno inscrito recebe no maximo uma copia dele. As horas e
    o grupo sao copiados do evento no momento da emissao: se o evento for
    editado depois, os certificados ja emitidos nao mudam.
    """

    __tablename__ = "certificates"
    __table_args__ = (
        # Um aluno recebe no maximo um certificado por evento.
        UniqueConstraint("event_id", "user_id", name="uq_certificates_event_user"),
        CheckConstraint("workload_hours > 0", name="ck_certificates_workload_hours_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # Inscricao que deu origem ao certificado: sem inscricao nao ha certificado,
    # e uma inscricao gera no maximo um.
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("event_subscriptions.id"), nullable=False, unique=True
    )
    # Copia da carga horaria do evento no momento da emissao, em horas.
    workload_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    # Copia do grupo de horas do evento no momento da emissao.
    hours_group: Mapped[HoursGroup] = mapped_column(
        Enum(
            HoursGroup,
            native_enum=False,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
    )
    # Codigo publico para conferir se o certificado e autentico.
    validation_code: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, default=generate_validation_code
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
