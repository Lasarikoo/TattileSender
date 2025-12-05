from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_client_cert"
down_revision = "0004_coord_paths"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "certificates",
        sa.Column("client_cert_path", sa.String(length=1024), nullable=True),
    )
    op.execute("UPDATE certificates SET client_cert_path = path WHERE client_cert_path IS NULL")


def downgrade() -> None:
    op.drop_column("certificates", "client_cert_path")
