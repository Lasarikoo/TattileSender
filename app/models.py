"""Definiciones de modelos y configuración del ORM.

Incluye las tablas principales previstas en el diseño conceptual:
- Municipality
- Certificate
- Endpoint
- Camera
- AlprReading (tabla temporal de trabajo)
- MessageQueue (cola temporal de envío)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.sql import func

from app.config import settings

class Base(DeclarativeBase):
    pass
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Municipality(Base):
    __tablename__ = "municipalities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    endpoint_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("endpoints.id"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    certificate: Mapped[Optional["Certificate"]] = relationship(
        "Certificate",
        back_populates="municipality",
        foreign_keys="Certificate.municipality_id",
        lazy="joined",
        uselist=False,
    )
    endpoint: Mapped[Optional["Endpoint"]] = relationship(
        "Endpoint", back_populates="municipalities", lazy="joined"
    )
    cameras: Mapped[List["Camera"]] = relationship("Camera", back_populates="municipality")


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alias: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="PEM_PAIR")
    path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    client_cert_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    key_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    pfx_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    privpub_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    public_cert_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    password_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    municipality_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("municipalities.id"), nullable=False
    )
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, server_default=func.now(), onupdate=func.now()
    )

    municipality: Mapped["Municipality"] = relationship(
        "Municipality",
        back_populates="certificate",
        foreign_keys=[municipality_id],
    )
    cameras: Mapped[List["Camera"]] = relationship("Camera", back_populates="certificate")


class Endpoint(Base):
    __tablename__ = "endpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=30000)
    retry_max: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_backoff_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)

    municipalities: Mapped[List["Municipality"]] = relationship(
        "Municipality", back_populates="endpoint"
    )
    cameras: Mapped[List["Camera"]] = relationship("Camera", back_populates="endpoint")


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    serial_number: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    codigo_lector: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    municipality_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("municipalities.id"), nullable=False
    )
    endpoint_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("endpoints.id"), nullable=True
    )
    certificate_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("certificates.id"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    coord_x: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="Coordenada X UTM31N-ETRS89 con dos decimales"
    )
    coord_y: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="Coordenada Y UTM31N-ETRS89 con dos decimales"
    )
    utm_x: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="UTM31N-ETRS89 X (Este), 2 decimales"
    )
    utm_y: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="UTM31N-ETRS89 Y (Norte), 2 decimales"
    )

    municipality: Mapped["Municipality"] = relationship("Municipality", back_populates="cameras")
    endpoint: Mapped[Optional["Endpoint"]] = relationship("Endpoint", back_populates="cameras")
    certificate: Mapped[Optional["Certificate"]] = relationship(
        "Certificate", back_populates="cameras"
    )
    readings: Mapped[List["AlprReading"]] = relationship("AlprReading", back_populates="camera")


class AlprReading(Base):
    """Tabla de trabajo temporal para lecturas aún no enviadas.

    Los registros se eliminarán tras el envío exitoso en la Fase 2 según la
    política de retención.
    """

    __tablename__ = "alpr_readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    camera_id: Mapped[int] = mapped_column(Integer, ForeignKey("cameras.id"), nullable=False)
    device_sn: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    plate: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    timestamp_utc: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    direction: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    lane_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lane_descr: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ocr_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    country_code: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bbox_min_x: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_min_y: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_max_x: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_max_y: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    char_height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    has_image_ocr: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_image_ctx: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    image_ocr_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    image_ctx_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    raw_xml: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    camera: Mapped["Camera"] = relationship("Camera", back_populates="readings")
    message: Mapped[Optional["MessageQueue"]] = relationship(
        "MessageQueue", back_populates="reading", uselist=False
    )


class MessageQueue(Base):
    """Cola temporal para gestionar el envío a Mossos.

    En la Fase 1 solo se utiliza el estado "PENDING". El borrado de registros se
    implementará en fases posteriores.
    """

    __tablename__ = "messages_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    reading_id: Mapped[int] = mapped_column(Integer, ForeignKey("alpr_readings.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    reading: Mapped["AlprReading"] = relationship("AlprReading", back_populates="message")

    @property
    def retry_delay(self) -> timedelta:
        """Devuelve el tiempo de backoff basado en ``next_retry_at`` si se ha calculado."""

        if self.next_retry_at and self.updated_at:
            return self.next_retry_at - self.updated_at
        return timedelta()


class MessageStatus:
    """Constantes de estado para ``MessageQueue``."""

    PENDING = "PENDING"
    SENDING = "SENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    DEAD = "DEAD"
