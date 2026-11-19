"""add event end time and attendance confirmation

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-18 10:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("events") as batch_op:
        batch_op.add_column(
            sa.Column("event_end_datetime", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "attendance_mode",
                sa.Enum(
                    "none",
                    "professor",
                    "student",
                    name="attendancemode",
                    native_enum=False,
                ),
                nullable=False,
                server_default="none",
            )
        )

    # Eventos antigos nao tinham horario final: terminam uma hora depois de comecar.
    if op.get_bind().dialect.name == "sqlite":
        op.execute("UPDATE events SET event_end_datetime = datetime(event_datetime, '+1 hour')")
    else:
        op.execute("UPDATE events SET event_end_datetime = event_datetime + INTERVAL '1 hour'")

    with op.batch_alter_table("events") as batch_op:
        batch_op.alter_column(
            "event_end_datetime",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_events_end_after_start",
            "event_end_datetime > event_datetime",
        )

    with op.batch_alter_table("event_subscriptions") as batch_op:
        batch_op.add_column(sa.Column("checked_in_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("event_subscriptions") as batch_op:
        batch_op.drop_column("checked_in_at")

    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_constraint("ck_events_end_after_start", type_="check")
        batch_op.drop_column("attendance_mode")
        batch_op.drop_column("event_end_datetime")
