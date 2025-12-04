"""Initial schema for TattileSender Fase 1"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "certificates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=True),
        sa.Column("path", sa.String(length=1024), nullable=True),
        sa.Column("password_ref", sa.String(length=255), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_certificates_id"), "certificates", ["id"], unique=False)

    op.create_table(
        "endpoints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("timeout_ms", sa.Integer(), nullable=False, server_default="30000"),
        sa.Column("retry_max", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("retry_backoff_ms", sa.Integer(), nullable=False, server_default="1000"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_endpoints_id"), "endpoints", ["id"], unique=False)

    op.create_table(
        "municipalities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("certificate_id", sa.Integer(), nullable=True),
        sa.Column("endpoint_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["certificate_id"], ["certificates.id"]),
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_municipalities_id"), "municipalities", ["id"], unique=False)

    op.create_table(
        "cameras",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("serial_number", sa.String(length=255), nullable=False),
        sa.Column("codigo_lector", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("municipality_id", sa.Integer(), nullable=False),
        sa.Column("endpoint_id", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["endpoint_id"], ["endpoints.id"]),
        sa.ForeignKeyConstraint(["municipality_id"], ["municipalities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("serial_number"),
    )
    op.create_index(op.f("ix_cameras_id"), "cameras", ["id"], unique=False)

    op.create_table(
        "alpr_readings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.Column("device_sn", sa.String(length=255), nullable=True),
        sa.Column("plate", sa.String(length=32), nullable=True),
        sa.Column("timestamp_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("direction", sa.String(length=32), nullable=True),
        sa.Column("lane_id", sa.Integer(), nullable=True),
        sa.Column("lane_descr", sa.String(length=255), nullable=True),
        sa.Column("ocr_score", sa.Integer(), nullable=True),
        sa.Column("country_code", sa.String(length=16), nullable=True),
        sa.Column("country", sa.String(length=255), nullable=True),
        sa.Column("bbox_min_x", sa.Integer(), nullable=True),
        sa.Column("bbox_min_y", sa.Integer(), nullable=True),
        sa.Column("bbox_max_x", sa.Integer(), nullable=True),
        sa.Column("bbox_max_y", sa.Integer(), nullable=True),
        sa.Column("char_height", sa.Integer(), nullable=True),
        sa.Column("has_image_ocr", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_image_ctx", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("raw_xml", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_alpr_readings_id"), "alpr_readings", ["id"], unique=False)

    op.create_table(
        "messages_queue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reading_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["reading_id"], ["alpr_readings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_queue_id"), "messages_queue", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_messages_queue_id"), table_name="messages_queue")
    op.drop_table("messages_queue")
    op.drop_index(op.f("ix_alpr_readings_id"), table_name="alpr_readings")
    op.drop_table("alpr_readings")
    op.drop_index(op.f("ix_cameras_id"), table_name="cameras")
    op.drop_table("cameras")
    op.drop_index(op.f("ix_municipalities_id"), table_name="municipalities")
    op.drop_table("municipalities")
    op.drop_index(op.f("ix_endpoints_id"), table_name="endpoints")
    op.drop_table("endpoints")
    op.drop_index(op.f("ix_certificates_id"), table_name="certificates")
    op.drop_table("certificates")
