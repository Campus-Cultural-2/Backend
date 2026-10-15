"""store images on cloudinary

Revision ID: 9d706e24796a
Revises: b6b7a88ac671
Create Date: 2026-10-14 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "9d706e24796a"
down_revision = "b6b7a88ac671"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # As imagens passam a ficar no Cloudinary. O banco guarda o link, para
    # mostrar a imagem, e o public_id, para apaga-la de la quando deixar de
    # ser usada.
    # ATENCAO: as imagens que ainda estiverem salvas dentro do banco (colunas
    # binarias) sao descartadas. Precisam ser enviadas de novo pelo app.
    with op.batch_alter_table("events") as batch_op:
        batch_op.add_column(sa.Column("image_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("image_public_id", sa.String(length=255), nullable=True))
        batch_op.drop_column("image")

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("profile_picture_url", sa.String(length=500), nullable=True))
        batch_op.add_column(
            sa.Column("profile_picture_public_id", sa.String(length=255), nullable=True)
        )
        batch_op.drop_column("profile_picture")


def downgrade() -> None:
    # Volta as colunas binarias vazias. Os links ficam perdidos, mas as
    # imagens continuam no Cloudinary.
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("profile_picture", sa.LargeBinary(), nullable=True))
        batch_op.drop_column("profile_picture_public_id")
        batch_op.drop_column("profile_picture_url")

    with op.batch_alter_table("events") as batch_op:
        batch_op.add_column(sa.Column("image", sa.LargeBinary(), nullable=True))
        batch_op.drop_column("image_public_id")
        batch_op.drop_column("image_url")
