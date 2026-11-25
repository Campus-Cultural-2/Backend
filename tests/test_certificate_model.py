from __future__ import annotations

import logging.config
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, event, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from api.features.certificate.certificate import Certificate
from api.features.event.event import Event, HoursGroup
from api.features.subscription.subscription import EventSubscription
from api.features.user.user import User, UserRole
from database.config.base import Base
from database.config.settings import settings

BACKEND_DIR = Path(__file__).resolve().parent.parent


def sqlite_engine(database_url: str) -> Engine:
    engine = create_engine(database_url)

    # O SQLite so confere chave estrangeira com este PRAGMA ligado, como o
    # Postgres de producao sempre faz.
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _record) -> None:  # noqa: ANN001
        dbapi_connection.execute("PRAGMA foreign_keys = ON")

    return engine


@pytest.fixture
def session(database_url: str) -> Generator[Session, None, None]:
    engine = sqlite_engine(database_url)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


def add_student(session: Session, email: str = "aluno@example.com", ra: str = "1234567") -> User:
    student = User(
        role=UserRole.STUDENT,
        password_hash="unused",
        email=email,
        name="Aluno",
        last_name="Teste",
        ra=ra,
    )
    session.add(student)
    session.flush()
    return student


def add_event(session: Session, owner: User, name: str = "Palestra") -> Event:
    start = datetime(2026, 11, 20, 14, tzinfo=UTC)
    created = Event(
        name=name,
        user_id=owner.id,
        event_datetime=start,
        event_end_datetime=start + timedelta(hours=4),
        event_location="Auditorio",
        description="Evento com certificado",
        has_certificate=True,
        workload_hours=4,
        hours_group=HoursGroup.GROUP_1,
    )
    session.add(created)
    session.flush()
    return created


def subscribe(session: Session, student: User, subscribed_event: Event) -> EventSubscription:
    subscription = EventSubscription(user_id=student.id, event_id=subscribed_event.id)
    session.add(subscription)
    session.flush()
    return subscription


def issue(session: Session, subscription: EventSubscription, **changes: object) -> Certificate:
    subscribed_event = session.get(Event, subscription.event_id)
    fields: dict[str, object] = {
        "event_id": subscription.event_id,
        "user_id": subscription.user_id,
        "subscription_id": subscription.id,
        "workload_hours": subscribed_event.workload_hours,
        "hours_group": subscribed_event.hours_group,
        **changes,
    }
    certificate = Certificate(**fields)
    session.add(certificate)
    session.flush()
    return certificate


@pytest.fixture
def subscription(session: Session) -> EventSubscription:
    student = add_student(session)
    return subscribe(session, student, add_event(session, owner=student))


def test_certificate_is_issued_with_validation_code_and_date(
    session: Session, subscription: EventSubscription
) -> None:
    certificate = issue(session, subscription)

    assert certificate.id is not None
    assert certificate.workload_hours == 4
    assert certificate.hours_group == HoursGroup.GROUP_1
    assert len(certificate.validation_code) == 36
    assert certificate.issued_at is not None


def test_student_can_have_many_certificates(session: Session) -> None:
    student = add_student(session)
    first = subscribe(session, student, add_event(session, student, name="Palestra"))
    second = subscribe(session, student, add_event(session, student, name="Oficina"))

    issue(session, first)
    issue(session, second)

    certificates = session.scalars(
        select(Certificate).where(Certificate.user_id == student.id)
    ).all()
    assert len(certificates) == 2
    assert certificates[0].validation_code != certificates[1].validation_code


def test_event_certificate_is_issued_to_each_subscribed_student(session: Session) -> None:
    owner = add_student(session)
    palestra = add_event(session, owner)
    other = add_student(session, email="outro@example.com", ra="7654321")

    issue(session, subscribe(session, owner, palestra))
    issue(session, subscribe(session, other, palestra))

    certificates = session.scalars(
        select(Certificate).where(Certificate.event_id == palestra.id)
    ).all()
    assert {certificate.user_id for certificate in certificates} == {owner.id, other.id}
    assert {certificate.workload_hours for certificate in certificates} == {4}


def test_editing_event_does_not_change_issued_certificate(
    session: Session, subscription: EventSubscription
) -> None:
    certificate = issue(session, subscription)
    subscribed_event = session.get(Event, subscription.event_id)

    subscribed_event.workload_hours = 10
    subscribed_event.hours_group = HoursGroup.GROUP_2
    session.commit()
    session.expire_all()

    stored = session.get(Certificate, certificate.id)
    assert stored.workload_hours == 4
    assert stored.hours_group == HoursGroup.GROUP_1


def test_student_cannot_get_two_certificates_for_same_event(
    session: Session, subscription: EventSubscription
) -> None:
    issue(session, subscription)

    # Mesmo aluno e evento, ainda que apontando para outra inscricao.
    other_subscription = subscribe(
        session,
        add_student(session, email="outro@example.com", ra="7654321"),
        session.get(Event, subscription.event_id),
    )
    with pytest.raises(IntegrityError):
        issue(session, subscription, subscription_id=other_subscription.id)


def test_subscription_cannot_generate_two_certificates(session: Session) -> None:
    student = add_student(session)
    subscription = subscribe(session, student, add_event(session, student))
    issue(session, subscription)

    with pytest.raises(IntegrityError):
        issue(session, subscription, event_id=add_event(session, student, name="Outro").id)


def test_certificate_requires_existing_subscription(
    session: Session, subscription: EventSubscription
) -> None:
    with pytest.raises(IntegrityError):
        issue(session, subscription, subscription_id=subscription.id + 999)


def test_validation_code_is_unique(session: Session) -> None:
    student = add_student(session)
    first = issue(session, subscribe(session, student, add_event(session, student)))
    second_subscription = subscribe(session, student, add_event(session, student, name="Outro"))

    with pytest.raises(IntegrityError):
        issue(session, second_subscription, validation_code=first.validation_code)


@pytest.mark.parametrize("workload_hours", [0, -2, None])
def test_certificate_requires_positive_workload_hours(
    session: Session, subscription: EventSubscription, workload_hours: int | None
) -> None:
    with pytest.raises(IntegrityError):
        issue(session, subscription, workload_hours=workload_hours)


def test_certificate_requires_hours_group(
    session: Session, subscription: EventSubscription
) -> None:
    with pytest.raises(IntegrityError):
        issue(session, subscription, hours_group=None)


def test_certificates_migration_matches_model_and_can_be_reverted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "migrations.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    # O env.py do Alembic reconfigura o log a partir do alembic.ini, o que
    # desliga os loggers ja criados e quebra os testes que conferem mensagens
    # de log rodando depois deste.
    monkeypatch.setattr(logging.config, "fileConfig", lambda *args, **kwargs: None)
    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    engine = create_engine(f"sqlite:///{db_path}")

    command.upgrade(alembic_config, "head")
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    certificate_differences = [
        difference for difference in differences if "certificates" in repr(difference)
    ]
    assert certificate_differences == []

    command.downgrade(alembic_config, "a7b8c9d0e1f2")
    assert "certificates" not in inspect(engine).get_table_names()
    engine.dispose()
