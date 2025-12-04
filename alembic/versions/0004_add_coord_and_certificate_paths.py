"""Add coord_x/y to cameras and new certificate paths"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_add_coord_and_certificate_paths"
down_revision = "0003_utm_cert_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cameras",
        sa.Column("coord_x", sa.String(length=32), nullable=True, comment="Coordenada X UTM31N-ETRS89 con dos decimales"),
    )
    op.add_column(
        "cameras",
        sa.Column("coord_y", sa.String(length=32), nullable=True, comment="Coordenada Y UTM31N-ETRS89 con dos decimales"),
    )

    op.add_column("certificates", sa.Column("alias", sa.String(length=255), nullable=True))
    op.add_column("certificates", sa.Column("pfx_path", sa.String(length=1024), nullable=True))
    op.add_column("certificates", sa.Column("privpub_path", sa.String(length=1024), nullable=True))
    op.add_column("certificates", sa.Column("public_cert_path", sa.String(length=1024), nullable=True))
    op.add_column("certificates", sa.Column("municipality_id", sa.Integer(), nullable=True))
    op.add_column(
        "certificates",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.add_column(
        "certificates",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_foreign_key(
        "certificates_municipality_fk",
        "certificates",
        "municipalities",
        ["municipality_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("certificates_municipality_fk", "certificates", type_="foreignkey")
    op.drop_column("certificates", "updated_at")
    op.drop_column("certificates", "created_at")
    op.drop_column("certificates", "municipality_id")
    op.drop_column("certificates", "public_cert_path")
    op.drop_column("certificates", "privpub_path")
    op.drop_column("certificates", "pfx_path")
    op.drop_column("certificates", "alias")
    op.drop_column("cameras", "coord_y")
    op.drop_column("cameras", "coord_x")
