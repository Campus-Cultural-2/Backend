"""add certificate info to events

Revision ID: d4e5f6a7b8c9
Revises: 9d706e24796a
Create Date: 2026-10-18 21:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "9d706e24796a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Eventos que ja existem ficam sem certificado.
    with op.batch_alter_table("events") as batch_op:
        batch_op.add_column(
            sa.Column(
                "has_certificate",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(sa.Column("workload_hours", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "hours_group",
                sa.Enum(
                    "group_1",
                    "group_2",
                    "group_3",
                    name="hoursgroup",
                    native_enum=False,
                ),
                nullable=True,
            )
        )
        batch_op.create_check_constraint(
            "ck_events_workload_hours_positive",
            "workload_hours IS NULL OR workload_hours > 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_constraint("ck_events_workload_hours_positive", type_="check")
        batch_op.drop_column("hours_group")
        batch_op.drop_column("workload_hours")
        batch_op.drop_column("has_certificate")
