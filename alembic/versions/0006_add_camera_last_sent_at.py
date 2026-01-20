from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_camera_last_sent"
down_revision = "0005_client_cert"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cameras",
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("cameras", "last_sent_at")
