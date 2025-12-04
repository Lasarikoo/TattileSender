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
from app.sender.cleanup import delete_reading_images
from app.sender.mossos_client import MossosClient
from app.utils.images import resolve_image_path

logger = logging.getLogger("sender")
logger.setLevel(logging.DEBUG)
logger.propagate = True
if not logger.handlers:
    logger.addHandler(logging.NullHandler())


def _resolve_retry_config(endpoint) -> tuple[int, int]:
    retry_max = getattr(endpoint, "retry_max", None) or settings.sender_default_retry_max
    backoff_ms = getattr(endpoint, "retry_backoff_ms", None) or settings.sender_default_backoff_ms
    return int(retry_max), int(backoff_ms)


def _full_cert_path(cert_path: str) -> str:
    if os.path.isabs(cert_path):
        return cert_path
    return os.path.join(settings.certs_dir, cert_path)


def _load_candidates(session: Session, batch_size: int) -> Iterable[MessageQueue]:
    query = (
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
    )
    logger.debug("[SENDER] Query generada para carga de mensajes: %s", query)
    return query.all()


def _should_skip_retry(message: MessageQueue, now: datetime) -> bool:
    return message.next_retry_at is not None and message.next_retry_at > now


def _mark_dead(session: Session, message: MessageQueue, error: str) -> None:
    message.status = MessageStatus.DEAD
    message.last_error = error
    message.updated_at = datetime.now(timezone.utc)
    session.add(message)
    session.commit()
    logger.error(
        "[SENDER] Mensaje %s marcado como DEAD. Motivo: %s", message.id, error
    )


def _validate_images(reading: AlprReading) -> tuple[bool, str | None]:
    if not reading.has_image_ocr or not reading.image_ocr_path:
        return False, "NO_IMAGE_AVAILABLE_OCR"

    ocr_full = resolve_image_path(reading.image_ocr_path)
    if not ocr_full or not os.path.isfile(ocr_full):
        return False, f"NO_IMAGE_FILE_OCR:{ocr_full}"

    if reading.has_image_ctx:
        ctx_full = resolve_image_path(reading.image_ctx_path)
        if not ctx_full:
            return False, "NO_IMAGE_AVAILABLE_CTX"
        if not os.path.isfile(ctx_full):
            return False, f"NO_IMAGE_FILE_CTX:{ctx_full}"

    return True, None


def _mark_sending(session: Session, message: MessageQueue) -> None:
    message.status = MessageStatus.SENDING
    message.updated_at = datetime.now(timezone.utc)
    session.add(message)
    session.commit()
    logger.info("[SENDER] Mensaje %s marcado como SENDING", message.id)


def _delete_success_records(session: Session, message: MessageQueue) -> None:
    reading = message.reading
    if reading:
        delete_reading_images(reading)
        session.delete(reading)
    session.delete(message)
    session.commit()


def process_message(session: Session, message: MessageQueue) -> None:
    now = datetime.now(timezone.utc)
    reading = message.reading
    camera = reading.camera if reading else None
    municipality: Municipality | None = camera.municipality if camera else None

    logger.info("[SENDER] Procesando mensaje #%s", message.id)
    logger.debug(
        "[SENDER] Contexto mensaje id=%s plate=%s ts=%s camera=%s municipio=%s estado=%s intentos=%s",
        message.id,
        reading.plate if reading else None,
        reading.timestamp_utc if reading else None,
        camera.serial_number if camera else None,
        municipality.name if municipality else None,
        message.status,
        message.attempts,
    )

    if not reading or not camera:
        logger.error(
            "[SENDER] Reading o cámara ausente para mensaje %s (reading=%s camera=%s)",
            message.id,
            reading.id if reading else None,
            camera.serial_number if camera else None,
        )
        _mark_dead(session, message, "Reading or camera not found")
        return

    endpoint = camera.endpoint or (municipality.endpoint if municipality else None)
    certificate = camera.certificate or (municipality.certificate if municipality else None)

    if not endpoint:
        logger.error(
            "[SENDER] Municipio/cámara sin endpoint para mensaje %s (municipio=%s cámara=%s)",
            message.id,
            municipality.name if municipality else None,
            camera.serial_number if camera else None,
        )
        _mark_dead(session, message, "Missing endpoint for municipality/camera")
        return
    if not certificate:
        logger.error(
            "[SENDER] Municipio/cámara sin certificado para mensaje %s (municipio=%s cámara=%s)",
            message.id,
            municipality.name if municipality else None,
            camera.serial_number if camera else None,
        )
        _mark_dead(session, message, "Missing certificate for municipality/camera")
        return

    if not certificate.path:
        logger.error(
            "[SENDER] Ruta de certificado no configurada para mensaje %s (cert=%s)",
            message.id,
            certificate.id if hasattr(certificate, "id") else None,
        )
        _mark_dead(session, message, "Certificate path not configured")
        return
    if not endpoint.url:
        logger.error(
            "[SENDER] Endpoint URL no configurada para mensaje %s (endpoint=%s)",
            message.id,
            endpoint.id if hasattr(endpoint, "id") else None,
        )
        _mark_dead(session, message, "Endpoint URL not configured")
        return

    retry_max, backoff_ms = _resolve_retry_config(endpoint)
    logger.info(
        "[SENDER] Intento %s/%s para mensaje %s (backoff %sms)",
        message.attempts + 1,
        retry_max,
        message.id,
        backoff_ms,
    )
    if message.attempts >= retry_max:
        _mark_dead(session, message, "Max retries reached")
        return

    if _should_skip_retry(message, now):
        logger.info(
            "[SENDER] Saltando mensaje %s hasta %s por backoff", message.id, message.next_retry_at
        )
        return

    ok_images, image_error = _validate_images(reading)
    if not ok_images:
        _mark_dead(session, message, image_error or "NO_IMAGE_AVAILABLE")
        return

    _mark_sending(session, message)

    timeout_seconds = max((endpoint.timeout_ms or 5000) / 1000.0, 1.0)
    cert_candidate = certificate.public_cert_path or certificate.path or ""
    cert_path = _full_cert_path(cert_candidate)
    key_path = _full_cert_path(certificate.key_path) if certificate.key_path else None

    logger.info(
        "[SENDER] Endpoint seleccionado: %s | Certificado: %s | Key: %s",
        endpoint.url,
        cert_path,
        key_path or "<no-key>",
    )

    if not os.path.exists(cert_path):
        logger.error("[SENDER][CERT] Certificado no encontrado en %s", cert_path)
        _mark_dead(session, message, f"Certificate file not found: {cert_path}")
        return
    if key_path and not os.path.exists(key_path):
        logger.error("[SENDER][CERT] key.pem no encontrada en %s", key_path)
        _mark_dead(session, message, f"Key file not found: {key_path}")
        return

    send_started = time.monotonic()
    client = MossosClient(
        endpoint_url=endpoint.url,
        cert_full_path=(cert_path, key_path) if key_path else cert_path,
        timeout=timeout_seconds,
    )

    try:
        result = client.send_matricula(
            reading=reading,
            camera=camera,
            municipality=municipality,
        )
    except FileNotFoundError as exc:
        _mark_dead(session, message, f"NO_IMAGE_FILE_RUNTIME: {exc}")
        logger.warning(
            "[SENDER] Mensaje %s DEAD por FileNotFoundError en runtime", message.id
        )
        return

    error_msg = result.error_message or ""
    if error_msg.startswith("NO_IMAGE"):
        _mark_dead(session, message, result.error_message)
        return
    if "fichero de imagen" in error_msg or "imagen no disponible" in error_msg:
        _mark_dead(session, message, f"NO_IMAGE_FILE: {error_msg}")
        return

    duration_ms = int((time.monotonic() - send_started) * 1000)
    logger.info(
        "[SENDER] Resultado envío mensaje %s: success=%s code=%s error=%s duración=%sms",
        message.id,
        result.success,
        result.code,
        result.error_message,
        duration_ms,
    )

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
        logger.error(
            "[SENDER] Mensaje %s agotó reintentos y se marca DEAD. Último error: %s",
            message.id,
            result.error_message,
        )
    else:
        message.status = MessageStatus.FAILED
        message.next_retry_at = now + timedelta(milliseconds=backoff_ms)
        logger.warning(
            "[SENDER] Mensaje %s falló (error=%s). Reintento programado para %s",
            message.id,
            result.error_message,
            message.next_retry_at,
        )

    session.add(message)
    session.commit()


def run_sender_iteration() -> int:
    """Procesa un lote de mensajes pendientes.

    Devuelve el número de mensajes intentados en la iteración para poder tomar
    decisiones de logging desde el bucle principal.
    """

    session = SessionLocal()
    processed = 0
    batch_size = settings.sender_max_batch_size
    iteration_started = time.monotonic()
    logger.info("[SENDER] Cargando hasta %s mensajes...", batch_size)
    try:
        candidates = _load_candidates(session, batch_size)
        logger.info("[SENDER] %s mensajes cargados para envío", len(candidates))
        now = datetime.now(timezone.utc)
        for message in candidates:
            logger.info(
                "[SENDER] Inicio de iteración para mensaje %s (created_at=%s)",
                message.id,
                message.created_at,
            )
            if _should_skip_retry(message, now):
                logger.info(
                    "[SENDER] Mensaje %s omitido por ventana de reintento futura", message.id
                )
                continue
            process_message(session, message)
            processed += 1
    finally:
        session.close()
        elapsed_ms = int((time.monotonic() - iteration_started) * 1000)
        logger.info(
            "[SENDER] Iteración completada. Mensajes procesados=%s Duración=%sms",
            processed,
            elapsed_ms,
        )
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
