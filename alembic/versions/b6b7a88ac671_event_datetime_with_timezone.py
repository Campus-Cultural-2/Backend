"""event_datetime with timezone

Revision ID: b6b7a88ac671
Revises: b2c3d4e5f6a7
Create Date: 2026-09-02 20:11:07.963671
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "b6b7a88ac671"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # O app manda event_datetime com offset (-03:00). O asyncpg quebra ao
    # inserir um datetime timezone-aware numa coluna "timestamp without time
    # zone" (TypeError: can't subtract offset-naive and offset-aware
    # datetimes), o que derrubava a criacao/edicao de eventos em producao.
    with op.batch_alter_table("events") as batch_op:
        batch_op.alter_column(
            "event_datetime",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("events") as batch_op:
        batch_op.alter_column(
            "event_datetime",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
