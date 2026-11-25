"""create certificates table

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-11-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # So cria uma tabela nova: nenhum dado existente e alterado.
    op.create_table(
        "certificates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("workload_hours", sa.Integer(), nullable=False),
        sa.Column(
            "hours_group",
            sa.Enum(
                "group_1",
                "group_2",
                "group_3",
                name="hoursgroup",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("validation_code", sa.String(length=36), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["subscription_id"], ["event_subscriptions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "user_id", name="uq_certificates_event_user"),
        sa.UniqueConstraint("subscription_id"),
        sa.UniqueConstraint("validation_code"),
        sa.CheckConstraint("workload_hours > 0", name="ck_certificates_workload_hours_positive"),
    )
    op.create_index(op.f("ix_certificates_event_id"), "certificates", ["event_id"], unique=False)
    op.create_index(op.f("ix_certificates_user_id"), "certificates", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_certificates_user_id"), table_name="certificates")
    op.drop_index(op.f("ix_certificates_event_id"), table_name="certificates")
    op.drop_table("certificates")
