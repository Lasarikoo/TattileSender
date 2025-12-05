"""Servicio de ingesta de lecturas Tattile (Fase 1)."""
from __future__ import annotations

import socket
from typing import Callable

from datetime import datetime, timezone

from sqlalchemy.orm import Session
from app.config import settings
from app.logger import logger
from app.ingest.image_storage import save_reading_image_base64
from app.ingest.parser import TattileParseError, parse_tattile_xml
from app.models import AlprReading, Camera, MessageQueue, SessionLocal


def process_tattile_payload(xml_str: str, session: Session) -> None:
    """Parsea y persiste una lectura Tattile en la base de datos.

    Crea un registro en ``alpr_readings`` y su correspondiente entrada en
    ``messages_queue`` con estado ``PENDING``. Si la cámara no existe, se registra
    un aviso y la lectura no se guarda.
    """

    try:
        parsed = parse_tattile_xml(xml_str)
        device_sn = parsed["device_sn"]

        camera = session.query(Camera).filter(Camera.serial_number == device_sn).first()
        if not camera:
            logger.warning(
                "[INGEST][ADVERTENCIA] Cámara no registrada: device_sn=%s. Lectura descartada.",
                device_sn,
            )
            session.rollback()
            return

        timestamp = parsed.get("timestamp_utc") or datetime.now(timezone.utc)

        image_ocr_path = None
        image_ctx_path = None
        has_image_ocr = False
        has_image_ctx = False

        if parsed.get("image_ocr_b64"):
            image_ocr_path = save_reading_image_base64(
                plate=parsed.get("plate") or "",
                device_sn=device_sn,
                timestamp_utc=timestamp,
                kind="ocr",
                base64_data=parsed.get("image_ocr_b64") or "",
            )
            has_image_ocr = image_ocr_path is not None
        if parsed.get("image_ctx_b64"):
            image_ctx_path = save_reading_image_base64(
                plate=parsed.get("plate") or "",
                device_sn=device_sn,
                timestamp_utc=timestamp,
                kind="ctx",
                base64_data=parsed.get("image_ctx_b64") or "",
            )
            has_image_ctx = image_ctx_path is not None

        reading = AlprReading(
            camera_id=camera.id,
            device_sn=device_sn,
            plate=parsed.get("plate"),
            timestamp_utc=timestamp,
            direction=parsed.get("direction"),
            lane_id=parsed.get("lane_id"),
            lane_descr=parsed.get("lane_descr"),
            ocr_score=parsed.get("ocr_score"),
            country_code=parsed.get("country_code"),
            country=parsed.get("country"),
            bbox_min_x=parsed.get("bbox_min_x"),
            bbox_min_y=parsed.get("bbox_min_y"),
            bbox_max_x=parsed.get("bbox_max_x"),
            bbox_max_y=parsed.get("bbox_max_y"),
            char_height=parsed.get("char_height"),
            has_image_ocr=has_image_ocr,
            has_image_ctx=has_image_ctx,
            image_ocr_path=image_ocr_path,
            image_ctx_path=image_ctx_path,
            raw_xml=xml_str,
        )
        session.add(reading)
        session.flush()

        message = MessageQueue(reading_id=reading.id, status="PENDING", attempts=0)
        session.add(message)

        session.commit()

        logger.info(
            "Lectura recibida %s de %s",
            (parsed.get("plate") or "").strip().upper(),
            device_sn,
        )
    except Exception as exc:
        session.rollback()
        logger.error("[INGEST][ERROR] Error guardando lectura: %s", exc)
        raise


def _serve_connection(conn: socket.socket, addr: tuple, session_factory: Callable[[], Session]) -> None:
    data_chunks: list[bytes] = []
    with conn:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data_chunks.append(chunk)

    if not data_chunks:
        logger.debug("Conexión %s cerrada sin datos", addr)
        return

    xml_str = b"".join(data_chunks).decode("utf-8", errors="replace")
    logger.info("[INGEST] XML recibido desde %s", addr)
    session = session_factory()
    try:
        process_tattile_payload(xml_str, session)
    except TattileParseError as exc:
        logger.error("[INGEST][ERROR] No se ha podido parsear el XML desde %s: %s", addr, exc)
        session.rollback()
    except Exception as exc:  # pragma: no cover - logging defensivo
        logger.exception("[INGEST][ERROR] Error procesando payload desde %s", addr)
        session.rollback()
    finally:
        session.close()


def run_ingest_service() -> None:
    """Punto de entrada del servicio de ingesta síncrono."""

    listen_port = getattr(settings, "TRANSIT_PORT", None) or settings.transit_port
    logger.info("[INGEST] Servicio de ingesta iniciado en 0.0.0.0:%s", listen_port)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("0.0.0.0", listen_port))
        server_socket.listen()
        while True:
            conn, addr = server_socket.accept()
            logger.debug("[INGEST] Conexión entrante desde %s", addr)
            _serve_connection(conn, addr, SessionLocal)
