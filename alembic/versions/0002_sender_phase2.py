"""Add sender phase 2 fields"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_sender_phase2"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cameras",
        sa.Column("certificate_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_cameras_certificate_id_certificates",
        "cameras",
        "certificates",
        ["certificate_id"],
        ["id"],
        ondelete=None,
    )

    op.add_column(
        "alpr_readings",
        sa.Column("image_ocr_path", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "alpr_readings",
        sa.Column("image_ctx_path", sa.String(length=1024), nullable=True),
    )

    op.add_column(
        "messages_queue",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.add_column(
        "messages_queue",
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "messages_queue",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages_queue", "next_retry_at")
    op.drop_column("messages_queue", "last_sent_at")
    op.drop_column("messages_queue", "updated_at")
    op.drop_column("alpr_readings", "image_ctx_path")
    op.drop_column("alpr_readings", "image_ocr_path")
    op.drop_constraint("fk_cameras_certificate_id_certificates", "cameras", type_="foreignkey")
    op.drop_column("cameras", "certificate_id")
