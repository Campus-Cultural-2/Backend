"""add max_participants to events

Revision ID: c7d8e9f0a1b2
Revises: 9d706e24796a
Create Date: 2026-10-18 20:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "c7d8e9f0a1b2"
down_revision = "9d706e24796a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Eventos que ja existem ficam sem limite (coluna nula).
    with op.batch_alter_table("events") as batch_op:
        batch_op.add_column(sa.Column("max_participants", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "ck_events_max_participants_positive",
            "max_participants IS NULL OR max_participants > 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_constraint("ck_events_max_participants_positive", type_="check")
        batch_op.drop_column("max_participants")
