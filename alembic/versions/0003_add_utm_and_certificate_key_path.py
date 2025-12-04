"""Add UTM coords to cameras and key_path to certificates"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_add_utm_and_certificate_key_path"
down_revision = "0002_sender_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cameras", sa.Column("utm_x", sa.Float(), nullable=True))
    op.add_column("cameras", sa.Column("utm_y", sa.Float(), nullable=True))

    op.add_column("certificates", sa.Column("key_path", sa.String(length=1024), nullable=True))
    op.alter_column(
        "certificates",
        "type",
        existing_type=sa.String(length=50),
        existing_nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    op.alter_column(
        "certificates",
        "type",
        existing_type=sa.String(length=50),
        existing_nullable=True,
        server_default=None,
    )
    op.drop_column("certificates", "key_path")
    op.drop_column("cameras", "utm_y")
    op.drop_column("cameras", "utm_x")
