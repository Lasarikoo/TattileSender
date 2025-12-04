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

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from app.config import settings

Base = declarative_base()
engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Municipality(Base):
    __tablename__ = "municipalities"

    id: int = Column(Integer, primary_key=True, index=True)
    name: str = Column(String(255), nullable=False)
    code: Optional[str] = Column(String(64), nullable=True)
    certificate_id: Optional[int] = Column(Integer, ForeignKey("certificates.id"), nullable=True)
    endpoint_id: Optional[int] = Column(Integer, ForeignKey("endpoints.id"), nullable=True)
    active: bool = Column(Boolean, default=True, nullable=False)

    certificate = relationship("Certificate", back_populates="municipalities")
    endpoint = relationship("Endpoint", back_populates="municipalities")
    cameras: List["Camera"] = relationship("Camera", back_populates="municipality")


class Certificate(Base):
    __tablename__ = "certificates"

    id: int = Column(Integer, primary_key=True, index=True)
    name: str = Column(String(255), nullable=False)
    type: Optional[str] = Column(String(50), nullable=True)
    path: Optional[str] = Column(String(1024), nullable=True)
    password_ref: Optional[str] = Column(String(255), nullable=True)
    valid_from: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    valid_to: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    active: bool = Column(Boolean, default=True, nullable=False)

    municipalities: List["Municipality"] = relationship("Municipality", back_populates="certificate")


class Endpoint(Base):
    __tablename__ = "endpoints"

    id: int = Column(Integer, primary_key=True, index=True)
    name: str = Column(String(255), nullable=False)
    url: str = Column(String(2048), nullable=False)
    timeout_ms: int = Column(Integer, nullable=False, default=30000)
    retry_max: int = Column(Integer, nullable=False, default=3)
    retry_backoff_ms: int = Column(Integer, nullable=False, default=1000)

    municipalities: List["Municipality"] = relationship("Municipality", back_populates="endpoint")
    cameras: List["Camera"] = relationship("Camera", back_populates="endpoint")


class Camera(Base):
    __tablename__ = "cameras"

    id: int = Column(Integer, primary_key=True, index=True)
    serial_number: str = Column(String(255), nullable=False, unique=True)
    codigo_lector: str = Column(String(255), nullable=False)
    description: Optional[str] = Column(String(255), nullable=True)
    municipality_id: int = Column(Integer, ForeignKey("municipalities.id"), nullable=False)
    endpoint_id: Optional[int] = Column(Integer, ForeignKey("endpoints.id"), nullable=True)
    active: bool = Column(Boolean, default=True, nullable=False)

    municipality = relationship("Municipality", back_populates="cameras")
    endpoint = relationship("Endpoint", back_populates="cameras")
    readings: List["AlprReading"] = relationship("AlprReading", back_populates="camera")


class AlprReading(Base):
    """Tabla de trabajo temporal para lecturas aún no enviadas.

    Los registros se eliminarán tras el envío exitoso en la Fase 2 según la
    política de retención.
    """

    __tablename__ = "alpr_readings"

    id: int = Column(Integer, primary_key=True, index=True)
    camera_id: int = Column(Integer, ForeignKey("cameras.id"), nullable=False)
    device_sn: Optional[str] = Column(String(255), nullable=True)
    plate: Optional[str] = Column(String(32), nullable=True)
    timestamp_utc: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    direction: Optional[str] = Column(String(32), nullable=True)
    lane_id: Optional[int] = Column(Integer, nullable=True)
    lane_descr: Optional[str] = Column(String(255), nullable=True)
    ocr_score: Optional[int] = Column(Integer, nullable=True)
    country_code: Optional[str] = Column(String(16), nullable=True)
    country: Optional[str] = Column(String(255), nullable=True)
    bbox_min_x: Optional[int] = Column(Integer, nullable=True)
    bbox_min_y: Optional[int] = Column(Integer, nullable=True)
    bbox_max_x: Optional[int] = Column(Integer, nullable=True)
    bbox_max_y: Optional[int] = Column(Integer, nullable=True)
    char_height: Optional[int] = Column(Integer, nullable=True)
    has_image_ocr: bool = Column(Boolean, default=False, nullable=False)
    has_image_ctx: bool = Column(Boolean, default=False, nullable=False)
    raw_xml: Optional[str] = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    camera = relationship("Camera", back_populates="readings")
    message = relationship("MessageQueue", back_populates="reading", uselist=False)


class MessageQueue(Base):
    """Cola temporal para gestionar el envío a Mossos.

    En la Fase 1 solo se utiliza el estado "PENDING". El borrado de registros se
    implementará en fases posteriores.
    """

    __tablename__ = "messages_queue"

    id: int = Column(Integer, primary_key=True, index=True)
    reading_id: int = Column(Integer, ForeignKey("alpr_readings.id"), nullable=False)
    status: str = Column(String(32), nullable=False, default="PENDING")
    attempts: int = Column(Integer, nullable=False, default=0)
    last_error: Optional[str] = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    sent_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)

    reading = relationship("AlprReading", back_populates="message")
