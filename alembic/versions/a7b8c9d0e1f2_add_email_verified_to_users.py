"""add email_verified to users

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-11-19 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # As contas que ja existem foram criadas antes da verificacao de e-mail.
    # Marca todas como verificadas: com false, ninguem conseguiria mais entrar.
    # Contas novas nascem com false, pelo default do modelo.
    #
    # ATENCAO: isso tambem vale para contas criadas indevidamente antes desta
    # mudanca, como alguem que se cadastrou como professor sem ser. Audite as
    # contas de professor depois do deploy (ver docs/RUNBOOK.md).
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.true())
        )

    # O server_default so existia para preencher as linhas antigas.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("email_verified", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("email_verified")
