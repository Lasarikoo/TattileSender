"""Servicio de ingesta de lecturas Tattile (Fase 1)."""
from __future__ import annotations

import logging
import socket
from typing import Callable

from datetime import datetime, timezone

from sqlalchemy.orm import Session
from app.ingest.parser import TattileParseError, parse_tattile_xml
from app.models import AlprReading, Camera, MessageQueue, SessionLocal
from app.utils.images import save_reading_image

logger = logging.getLogger(__name__)


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
            print(f"[INGEST] Cámara no registrada para DEVICE_SN={device_sn}")
            session.rollback()
            return

        timestamp = parsed.get("timestamp_utc") or datetime.now(timezone.utc)

        image_ocr_path = None
        image_ctx_path = None

        if parsed.get("image_ocr_b64"):
            image_ocr_path = save_reading_image(
                plate=parsed.get("plate") or "",
                device_sn=device_sn,
                timestamp_utc=timestamp,
                kind="ocr",
                base64_data=parsed.get("image_ocr_b64") or "",
            )
        if parsed.get("image_ctx_b64"):
            image_ctx_path = save_reading_image(
                plate=parsed.get("plate") or "",
                device_sn=device_sn,
                timestamp_utc=timestamp,
                kind="ctx",
                base64_data=parsed.get("image_ctx_b64") or "",
            )

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
            has_image_ocr=bool(image_ocr_path),
            has_image_ctx=bool(image_ctx_path),
            image_ocr_path=image_ocr_path,
            image_ctx_path=image_ctx_path,
            raw_xml=xml_str,
        )
        session.add(reading)
        session.flush()

        message = MessageQueue(reading_id=reading.id, status="PENDING", attempts=0)
        session.add(message)

        session.commit()

        print(
            f"[INGEST] Lectura guardada plate={reading.plate} "
            f"camera_id={reading.camera_id} reading_id={reading.id} msg_id={message.id}"
        )
    except Exception as exc:
        session.rollback()
        print(f"[INGEST][ERROR] {exc}")
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
    print(f"[INGEST] XML recibido desde {addr}")
    session = session_factory()
    try:
        process_tattile_payload(xml_str, session)
    except TattileParseError as exc:
        logger.error("Error de parseo desde %s: %s", addr, exc)
        session.rollback()
    except Exception as exc:  # pragma: no cover - logging defensivo
        logger.exception("Error procesando payload desde %s", addr)
        session.rollback()
    finally:
        session.close()


def run_ingest_service() -> None:
    """Punto de entrada del servicio de ingesta síncrono."""

    listen_port = settings.transit_port
    logger.info("Iniciando Ingest Service en puerto %s", listen_port)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("0.0.0.0", listen_port))
        server_socket.listen()
        logger.info("Ingest Service escuchando en 0.0.0.0:%s", listen_port)

        while True:
            conn, addr = server_socket.accept()
            logger.info("Conexión entrante desde %s", addr)
            _serve_connection(conn, addr, SessionLocal)
