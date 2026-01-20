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
from app.logger import logger
from app.sender.cleanup import delete_reading_images
from app.sender.mossos_client import MossosZeepClient
from app.utils.images import resolve_image_path

SUCCESS_CODES = ("1", "0000", "OK", "1.0")


def _resolve_retry_config(endpoint) -> tuple[int, int]:
    retry_max = getattr(endpoint, "retry_max", None) or settings.sender_default_retry_max
    backoff_ms = getattr(endpoint, "retry_backoff_ms", None) or settings.sender_default_backoff_ms
    return int(retry_max), int(backoff_ms)


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
    logger.debug(
        "[SENDER][DEBUG] Cargando mensajes pendientes (estados=%s, límite=%s)",
        [MessageStatus.PENDING, MessageStatus.FAILED],
        batch_size,
    )
    return query.all()


def _should_skip_retry(message: MessageQueue, now: datetime) -> bool:
    return message.next_retry_at is not None and message.next_retry_at > now


def _get_plate(reading: AlprReading | None) -> str:
    return (reading.plate or "DESCONOCIDA").strip().upper() if reading else "DESCONOCIDA"


def _mark_dead(
    session: Session,
    message: MessageQueue,
    error: str,
    *,
    log_message: bool = True,
    log_level: int = logging.ERROR,
) -> None:
    message.status = MessageStatus.DEAD
    message.last_error = error
    message.updated_at = datetime.now(timezone.utc)
    session.add(message)
    session.commit()
    plate = _get_plate(message.reading)
    if log_message:
        logger.log(log_level, "[SENDER] Lectura (%s) descartada por %s", plate, error)
    logger.debug(
        "[SENDER][DEBUG] Mensaje %s marcado como DEAD por %s (reading_id=%s)",
        message.id,
        error,
        message.reading_id,
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
    logger.debug("[SENDER][DEBUG] Mensaje %s marcado como SENDING", message.id)


def _delete_success_records(session: Session, message: MessageQueue) -> None:
    reading = message.reading
    if reading:
        delete_reading_images(reading)
        session.delete(reading)
    session.delete(message)
    session.commit()


def process_message(session: Session, message: MessageQueue) -> None:
    utc_now = datetime.now(timezone.utc)
    local_now = datetime.now().astimezone()
    reading = message.reading
    camera = reading.camera if reading else None
    municipality: Municipality | None = camera.municipality if camera else None
    plate = _get_plate(reading)

    if not reading or not camera:
        logger.debug(
            "[SENDER][DEBUG] Mensaje %s sin lectura o cámara en BD (reading=%s camera=%s)",
            message.id,
            reading.id if reading else None,
            camera.serial_number if camera else None,
        )
        _mark_dead(session, message, "LECTURA_O_CAMARA_NO_ENCONTRADA")
        return

    logger.debug(
        "[SENDER][DEBUG] Contexto mensaje id=%s plate=%s ts=%s cámara=%s municipio=%s estado=%s intentos=%s",
        message.id,
        reading.plate if reading else None,
        reading.timestamp_utc if reading else None,
        camera.serial_number if camera else None,
        municipality.name if municipality else None,
        message.status,
        message.attempts,
    )

    endpoint = camera.endpoint or (municipality.endpoint if municipality else None)
    certificate = municipality.certificate if municipality else None
    if not certificate:
        logger.debug(
            "[CERT][DEBUG] No hay certificado configurado para mensaje %s (municipio=%s cámara=%s)",
            message.id,
            municipality.name if municipality else None,
            camera.serial_number if camera else None,
        )
        _mark_dead(session, message, "CERTIFICADO_NO_CONFIGURADO")
        return

    service_url = endpoint.url if endpoint else settings.MOSSOS_ENDPOINT_URL
    if not service_url:
        logger.debug(
            "[MOSSOS][DEBUG] Endpoint URL no configurada para mensaje %s (endpoint=%s)",
            message.id,
            endpoint.id if hasattr(endpoint, "id") else None,
        )
        _mark_dead(session, message, "ENDPOINT_URL_NO_CONFIGURADA")
        return
    logger.debug(
        "[SENDER][DEBUG] Endpoint efectivo para mensaje %s: %s", message.id, service_url
    )

    retry_max, backoff_ms = _resolve_retry_config(endpoint)
    if message.attempts >= retry_max:
        _mark_dead(session, message, "MAX_REINTENTOS_AGOTADOS")
        return

    if _should_skip_retry(message, utc_now):
        logger.debug(
            "[SENDER][DEBUG] Mensaje %s pospuesto hasta %s por backoff", message.id, message.next_retry_at
        )
        return

    ok_images, image_error = _validate_images(reading)
    if not ok_images:
        logger.info("[SENDER] Lectura sin imagen (%s) descartada", plate)
        logger.debug("[SENDER][DEBUG] Motivo imagen inválida para %s: %s", plate, image_error)
        _mark_dead(
            session,
            message,
            image_error or "NO_IMAGE_AVAILABLE",
            log_message=False,
        )
        return

    if message.attempts > 0:
        logger.info("[SENDER] Reintento de lectura (%s)", plate)
    else:
        logger.info("[SENDER] Enviando lectura (%s)", plate)

    _mark_sending(session, message)

    if not municipality:
        logger.debug(
            "[CERT][DEBUG] Municipio no asociado a mensaje %s (camera=%s)",
            message.id,
            camera.serial_number if camera else None,
        )
        _mark_dead(session, message, "MUNICIPIO_NO_DISPONIBLE")
        return

    timeout_ms = endpoint.timeout_ms if getattr(endpoint, "timeout_ms", None) else int(settings.mossos_timeout * 1000)
    timeout_seconds = max(timeout_ms / 1000.0, 1.0)

    cert_path = getattr(certificate, "client_cert_path", None) or certificate.path
    key_path = certificate.key_path
    if not cert_path or not key_path:
        logger.debug(
            "[CERT][DEBUG] Certificado incompleto para mensaje %s (municipio=%s)",
            message.id,
            municipality.name if municipality else None,
        )
        _mark_dead(session, message, "CERTIFICADO_INCOMPLETO")
        return

    send_started = time.monotonic()
    try:
        client = MossosZeepClient(
            wsdl_url=settings.MOSSOS_WSDL_URL,
            endpoint_url=service_url,
            cert_path=cert_path,
            key_path=key_path,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        logger.debug("[CERT][DEBUG] %s", exc)
        _mark_dead(session, message, f"CERT_FILE_NOT_FOUND:{exc}")
        return

    try:
        result = client.send_matricula(reading=reading, camera=camera)
    except FileNotFoundError as exc:
        logger.info("[SENDER] Lectura sin imagen (%s) descartada", plate)
        logger.debug(
            "[IMAGEN][DEBUG] Lectura %s sin imagen por error de disco: %s", plate, exc
        )
        _mark_dead(
            session,
            message,
            f"NO_IMAGE_FILE_RUNTIME: {exc}",
            log_message=False,
        )
        return

    duration_ms = int((time.monotonic() - send_started) * 1000)
    logger.debug(
        "[SENDER][DEBUG] Resultado envío lectura %s (msg_id=%s): éxito=%s http=%s codiRetorn=%s duración=%sms",
        reading.id,
        message.id,
        result.success,
        result.http_status,
        result.codi_retorn,
        duration_ms,
    )

    message.attempts += 1
    message.updated_at = datetime.now(timezone.utc)

    if result.success:
        message.status = MessageStatus.SUCCESS
        message.last_error = None
        message.last_sent_at = local_now
        message.sent_at = local_now
        camera.last_sent_at = local_now
        session.add(message)
        session.add(camera)
        session.flush()
        _delete_success_records(session, message)
        logger.info("[SENDER] Lectura (%s) enviada correctamente a Mossos", plate)
        return

    error_msg = result.fault or ""
    if result.codi_retorn:
        error_msg = (
            f"codiRetorn={result.codi_retorn}"
            if not error_msg
            else f"{error_msg} | codiRetorn={result.codi_retorn}"
        )

    if not error_msg:
        error_msg = "RESPUESTA_SIN_DETALLE"

    data_error = result.codi_retorn is not None and (
        result.codi_retorn not in SUCCESS_CODES
    )

    message.last_error = error_msg
    if data_error:
        message.status = MessageStatus.DEAD
        logger.error("[SENDER] Lectura (%s) descartada por %s", plate, error_msg)
    elif message.attempts >= retry_max:
        message.status = MessageStatus.DEAD
        logger.error("[SENDER] Lectura (%s) descartada por %s", plate, error_msg)
    else:
        message.status = MessageStatus.FAILED
        message.next_retry_at = utc_now + timedelta(milliseconds=backoff_ms)
        logger.warning("[SENDER] Error enviando lectura (%s): %s", plate, error_msg)

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
    logger.debug("[SENDER][DEBUG] Buscando mensajes pendientes (límite=%s)", batch_size)
    try:
        candidates = _load_candidates(session, batch_size)
        logger.debug("[SENDER][DEBUG] %s mensajes pendientes cargados para envío", len(candidates))
        now = datetime.now(timezone.utc)
        for message in candidates:
            logger.debug(
                "[SENDER][DEBUG] Procesando mensaje %s creado en %s", message.id, message.created_at
            )
            if _should_skip_retry(message, now):
                logger.debug(
                    "[SENDER][DEBUG] Mensaje %s omitido hasta %s por ventana de reintento",
                    message.id,
                    message.next_retry_at,
                )
                continue
            process_message(session, message)
            processed += 1
    finally:
        session.close()
        elapsed_ms = int((time.monotonic() - iteration_started) * 1000)
        logger.debug(
            "[SENDER][DEBUG] Iteración completada: procesados=%s duración=%sms",
            processed,
            elapsed_ms,
        )
    return processed


def run_sender_worker() -> None:
    if not settings.sender_enabled:
        logger.warning("[SENDER][ADVERTENCIA] Sender deshabilitado por variable de entorno")
        return

    logger.info(
        "[SENDER] Worker de envío iniciado. Intervalo de sondeo=%ss",
        settings.sender_poll_interval_seconds,
    )
    while True:
        try:
            processed = run_sender_iteration()
            if processed == 0:
                time.sleep(settings.sender_poll_interval_seconds)
        except Exception:  # pragma: no cover - seguridad del bucle
            logger.exception("[SENDER][ERROR] Error inesperado en el bucle principal")
            time.sleep(settings.sender_poll_interval_seconds)
