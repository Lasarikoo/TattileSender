"""Lógica principal del sender que consume ``messages_queue``."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models import (
    AlprReading,
    Camera,
    MessageQueue,
    MessageStatus,
    Municipality,
    SessionLocal,
)
from app.sender.mossos_client import MossosClient

logger = logging.getLogger(__name__)


def _resolve_retry_config(endpoint) -> tuple[int, int]:
    retry_max = getattr(endpoint, "retry_max", None) or settings.sender_default_retry_max
    backoff_ms = getattr(endpoint, "retry_backoff_ms", None) or settings.sender_default_backoff_ms
    return int(retry_max), int(backoff_ms)


def _full_cert_path(cert_path: str) -> str:
    if os.path.isabs(cert_path):
        return cert_path
    return os.path.join(settings.certs_dir, cert_path)


def _cleanup_files(*paths: str) -> None:
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                logger.warning("[SENDER] No se pudo borrar el fichero %s", path)


def _load_candidates(session: Session, batch_size: int) -> Iterable[MessageQueue]:
    return (
        session.query(MessageQueue)
        .options(
            selectinload(MessageQueue.reading)
            .selectinload(AlprReading.camera)
            .selectinload(Camera.municipality),
            selectinload(MessageQueue.reading)
            .selectinload(AlprReading.camera)
            .selectinload(Camera.endpoint),
            selectinload(MessageQueue.reading)
            .selectinload(AlprReading.camera)
            .selectinload(Camera.certificate),
            selectinload(MessageQueue.reading),
        )
        .filter(MessageQueue.status.in_([MessageStatus.PENDING, MessageStatus.FAILED]))
        .order_by(MessageQueue.created_at)
        .limit(batch_size)
        .all()
    )


def _should_skip_retry(message: MessageQueue, now: datetime) -> bool:
    return message.next_retry_at is not None and message.next_retry_at > now


def _mark_dead(session: Session, message: MessageQueue, error: str) -> None:
    message.status = MessageStatus.DEAD
    message.last_error = error
    message.updated_at = datetime.now(timezone.utc)
    session.add(message)
    session.commit()


def _mark_sending(session: Session, message: MessageQueue) -> None:
    message.status = MessageStatus.SENDING
    message.updated_at = datetime.now(timezone.utc)
    session.add(message)
    session.commit()


def _delete_success_records(session: Session, message: MessageQueue) -> None:
    reading = message.reading
    _cleanup_files(
        reading.image_ctx_path if reading else None,
        reading.image_ocr_path if reading else None,
    )
    if reading:
        session.delete(reading)
    session.delete(message)
    session.commit()


def process_message(session: Session, message: MessageQueue) -> None:
    now = datetime.now(timezone.utc)
    reading = message.reading
    camera = reading.camera if reading else None
    municipality: Municipality | None = camera.municipality if camera else None

    if not reading or not camera:
        _mark_dead(session, message, "Reading or camera not found")
        return

    endpoint = camera.endpoint or (municipality.endpoint if municipality else None)
    certificate = camera.certificate or (municipality.certificate if municipality else None)

    if not endpoint or not certificate:
        _mark_dead(session, message, "Missing certificate or endpoint")
        return

    if not certificate.path:
        _mark_dead(session, message, "Certificate path not configured")
        return
    if not endpoint.url:
        _mark_dead(session, message, "Endpoint URL not configured")
        return

    retry_max, backoff_ms = _resolve_retry_config(endpoint)
    if message.attempts >= retry_max:
        _mark_dead(session, message, "Max retries reached")
        return

    if _should_skip_retry(message, now):
        return

    _mark_sending(session, message)

    timeout_seconds = max((endpoint.timeout_ms or 5000) / 1000.0, 1.0)
    cert_path = _full_cert_path(certificate.path or "")
    key_path = _full_cert_path(certificate.key_path) if certificate.key_path else None

    if not os.path.exists(cert_path):
        _mark_dead(session, message, f"Certificate file not found: {cert_path}")
        return
    if key_path and not os.path.exists(key_path):
        _mark_dead(session, message, f"Key file not found: {key_path}")
        return

    client = MossosClient(
        endpoint_url=endpoint.url,
        cert_full_path=(cert_path, key_path) if key_path else cert_path,
        timeout=timeout_seconds,
    )

    result = client.send_matricula(reading=reading, camera=camera, municipality=municipality)

    message.attempts += 1
    message.updated_at = datetime.now(timezone.utc)

    if result.success:
        message.status = MessageStatus.SUCCESS
        message.last_error = None
        message.last_sent_at = now
        message.sent_at = now
        session.add(message)
        session.flush()
        _delete_success_records(session, message)
        logger.info(
            "[SENDER] Mensaje %s enviado correctamente y eliminado", message.id
        )
        return

    message.last_error = result.error_message
    if message.attempts >= retry_max:
        message.status = MessageStatus.DEAD
    else:
        message.status = MessageStatus.FAILED
        message.next_retry_at = now + timedelta(milliseconds=backoff_ms)

    session.add(message)
    session.commit()


def run_sender_iteration() -> int:
    """Procesa un lote de mensajes pendientes.

    Devuelve el número de mensajes intentados en la iteración para poder tomar
    decisiones de logging desde el bucle principal.
    """

    session = SessionLocal()
    processed = 0
    try:
        candidates = _load_candidates(session, settings.sender_max_batch_size)
        now = datetime.now(timezone.utc)
        for message in candidates:
            if _should_skip_retry(message, now):
                continue
            process_message(session, message)
            processed += 1
    finally:
        session.close()
    return processed


def run_sender_worker() -> None:
    if not settings.sender_enabled:
        logger.warning("Sender deshabilitado por variable de entorno")
        return

    logger.info("Iniciando sender worker (poll %ss)", settings.sender_poll_interval_seconds)
    while True:
        try:
            processed = run_sender_iteration()
            if processed == 0:
                time.sleep(settings.sender_poll_interval_seconds)
        except Exception:  # pragma: no cover - seguridad del bucle
            logger.exception("[SENDER] Error inesperado en el bucle principal")
            time.sleep(settings.sender_poll_interval_seconds)
