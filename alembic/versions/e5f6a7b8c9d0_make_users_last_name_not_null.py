"""make users.last_name not null

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-11 10:00:00.000000

A migration que criou `last_name` deixou a coluna aceitando NULL, entao os
usuarios cadastrados antes dela ficaram sem sobrenome. A API trata o campo
como obrigatorio: ao inativar (ou listar) um desses usuarios, a alteracao era
salva mas a resposta falhava com erro 500.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE users SET last_name = '' WHERE last_name IS NULL")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "last_name",
            existing_type=sa.String(255),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "last_name",
            existing_type=sa.String(255),
            nullable=True,
        )
