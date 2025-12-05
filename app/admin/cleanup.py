"""Helpers de limpieza y eliminación de datos para tareas administrativas."""
from __future__ import annotations

import logging
import os
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AlprReading, Camera, Certificate, Endpoint, MessageQueue, Municipality
from app.utils.cleanup import delete_reading_images

logger = logging.getLogger(__name__)


def _log_and_count_images(readings: Iterable[AlprReading]) -> int:
    count = 0
    for reading in readings:
        count += int(
            bool(reading.image_ocr_path)
            and os.path.isfile(reading.image_ocr_path)
        )
        count += int(
            bool(reading.image_ctx_path)
            and os.path.isfile(reading.image_ctx_path)
        )
        delete_reading_images(reading)
        reading.image_ocr_path = None
        reading.image_ctx_path = None
        reading.has_image_ctx = False
        reading.has_image_ocr = False
    return count


def _get_camera(session: Session, identifier: str) -> Camera:
    camera: Optional[Camera] = None
    if identifier.isdigit():
        camera = session.get(Camera, int(identifier))
    if camera is None:
        stmt = select(Camera).where(Camera.serial_number == identifier)
        camera = session.execute(stmt).scalar_one_or_none()
    if camera is None:
        raise ValueError(f"Cámara no encontrada para identificador '{identifier}'")
    return camera


def _get_municipality(session: Session, identifier: str) -> Municipality:
    municipality: Optional[Municipality] = None
    if identifier.isdigit():
        municipality = session.get(Municipality, int(identifier))
    if municipality is None:
        stmt = select(Municipality).where(Municipality.name == identifier)
        municipality = session.execute(stmt).scalar_one_or_none()
    if municipality is None:
        raise ValueError(f"Municipio no encontrado para identificador '{identifier}'")
    return municipality


def _get_certificate(session: Session, identifier: str) -> Certificate:
    certificate: Optional[Certificate] = None
    if identifier.isdigit():
        certificate = session.get(Certificate, int(identifier))
    if certificate is None:
        stmt = select(Certificate).where(Certificate.alias == identifier)
        certificate = session.execute(stmt).scalar_one_or_none()
    if certificate is None:
        stmt = select(Certificate).where(Certificate.name == identifier)
        certificate = session.execute(stmt).scalar_one_or_none()
    if certificate is None:
        raise ValueError(f"Certificado no encontrado para identificador '{identifier}'")
    return certificate


def _get_endpoint(session: Session, identifier: str) -> Endpoint:
    endpoint: Optional[Endpoint] = None
    if identifier.isdigit():
        endpoint = session.get(Endpoint, int(identifier))
    if endpoint is None:
        stmt = select(Endpoint).where(Endpoint.name == identifier)
        endpoint = session.execute(stmt).scalar_one_or_none()
    if endpoint is None:
        raise ValueError(f"Endpoint no encontrado para identificador '{identifier}'")
    return endpoint


def delete_camera(
    session: Session,
    camera_identifier: str,
    *,
    delete_readings: bool = True,
    delete_images: bool = True,
    delete_queue: bool = True,
) -> dict:
    """Elimina una cámara y, opcionalmente, sus lecturas, imágenes y cola.

    Devuelve un resumen con los contadores de recursos eliminados.
    """

    camera = _get_camera(session, camera_identifier)
    logger.info("Eliminando cámara %s (id=%s)", camera.serial_number, camera.id)

    readings = list(
        session.execute(
            select(AlprReading).where(AlprReading.camera_id == camera.id)
        ).scalars()
    )
    reading_ids = [r.id for r in readings]

    if not delete_readings and reading_ids:
        raise ValueError("No se puede borrar la cámara sin eliminar sus lecturas asociadas.")

    deleted_images = 0
    if delete_images and readings:
        deleted_images = _log_and_count_images(readings)

    deleted_messages = 0
    if delete_queue and reading_ids:
        deleted_messages = (
            session.query(MessageQueue)
            .filter(MessageQueue.reading_id.in_(reading_ids))
            .delete(synchronize_session=False)
        )

    deleted_readings = 0
    if delete_readings and reading_ids:
        deleted_readings = (
            session.query(AlprReading)
            .filter(AlprReading.id.in_(reading_ids))
            .delete(synchronize_session=False)
        )

    session.delete(camera)
    session.commit()

    logger.info(
        "Cámara %s eliminada (lecturas=%s, mensajes=%s, imágenes=%s)",
        camera.serial_number,
        deleted_readings,
        deleted_messages,
        deleted_images,
    )
    return {
        "readings": deleted_readings or 0,
        "messages": deleted_messages or 0,
        "images": deleted_images,
        "camera": camera.serial_number,
    }


def delete_municipality(
    session: Session,
    municipality_identifier: str,
    *,
    cascade: bool = True,
) -> dict:
    """Elimina un municipio. Si ``cascade`` es True, borra también sus recursos."""

    municipality = _get_municipality(session, municipality_identifier)
    logger.info("Eliminando municipio %s (id=%s)", municipality.name, municipality.id)

    cameras = list(municipality.cameras)
    if cameras and not cascade:
        raise ValueError(
            "El municipio tiene cámaras asociadas. Usa la opción en cascada para borrarlo."
        )

    summary = {"cameras": 0, "readings": 0, "messages": 0, "images": 0}
    if cascade:
        for cam in cameras:
            cam_summary = delete_camera(
                session,
                str(cam.id),
                delete_readings=True,
                delete_images=True,
                delete_queue=True,
            )
            summary["cameras"] += 1
            summary["readings"] += cam_summary.get("readings", 0)
            summary["messages"] += cam_summary.get("messages", 0)
            summary["images"] += cam_summary.get("images", 0)

    session.delete(municipality)
    session.commit()
    logger.info("Municipio %s eliminado", municipality.name)
    return summary | {"municipality": municipality.name}


def delete_certificate(session: Session, identifier: str, *, force: bool = False) -> dict:
    """Elimina un certificado si no está en uso."""

    certificate = _get_certificate(session, identifier)
    cameras_using = session.execute(
        select(Camera).where(Camera.certificate_id == certificate.id)
    ).scalars()
    cameras = list(cameras_using)

    if cameras and not force:
        msg = (
            f"El certificado está en uso por {len(cameras)} cámara(s). "
            "Ejecute con force=True para eliminarlo."
        )
        logger.warning(msg)
        raise ValueError(msg)

    if cameras and force:
        for cam in cameras:
            cam.certificate_id = None
        logger.info("Se han desvinculado %s cámara(s) del certificado", len(cameras))

    session.delete(certificate)
    session.commit()
    logger.info("Certificado %s eliminado", certificate.name)
    return {"certificate": certificate.name, "unlinked_cameras": len(cameras)}


def delete_endpoint(session: Session, identifier: str, *, force: bool = False) -> dict:
    """Elimina un endpoint si no está en uso."""

    endpoint = _get_endpoint(session, identifier)
    cameras = list(endpoint.cameras)
    municipalities = list(endpoint.municipalities)

    if (cameras or municipalities) and not force:
        msg = (
            "El endpoint está en uso por "
            f"{len(municipalities)} municipio(s) y {len(cameras)} cámara(s). "
            "Ejecute con force=True para eliminarlo."
        )
        logger.warning(msg)
        raise ValueError(msg)

    if cameras and force:
        for cam in cameras:
            cam.endpoint_id = None
    if municipalities and force:
        for mun in municipalities:
            mun.endpoint_id = None
        logger.info(
            "Se han desvinculado %s municipio(s) y %s cámara(s) del endpoint",
            len(municipalities),
            len(cameras),
        )

    session.delete(endpoint)
    session.commit()
    logger.info("Endpoint %s eliminado", endpoint.name)
    return {
        "endpoint": endpoint.name,
        "unlinked_cameras": len(cameras),
        "unlinked_municipalities": len(municipalities),
    }


def wipe_all_queue(session: Session) -> int:
    """Borra todos los mensajes de la cola."""

    deleted = session.query(MessageQueue).delete(synchronize_session=False) or 0
    session.commit()
    logger.info("Eliminados %s mensajes de la cola", deleted)
    return deleted


def wipe_all_readings(
    session: Session,
    *,
    delete_images: bool = True,
    delete_queue: bool = True,
) -> dict:
    """Borra todas las lecturas y opcionalmente imágenes y cola."""

    readings = list(session.execute(select(AlprReading)).scalars())
    reading_ids = [r.id for r in readings]

    deleted_messages = 0
    if delete_queue:
        if reading_ids:
            deleted_messages = (
                session.query(MessageQueue)
                .filter(MessageQueue.reading_id.in_(reading_ids))
                .delete(synchronize_session=False)
            )
        else:
            deleted_messages = (
                session.query(MessageQueue).delete(synchronize_session=False)
            )
    else:
        referenced_messages = 0
        if reading_ids:
            referenced_messages = (
                session.query(MessageQueue)
                .filter(MessageQueue.reading_id.in_(reading_ids))
                .count()
            )
        if referenced_messages:
            raise ValueError(
                "No se pueden borrar lecturas mientras existan mensajes en la cola. "
                "Ejecute primero la limpieza de la cola o use delete_queue=True."
            )

    deleted_images = 0
    if delete_images and readings:
        deleted_images = _log_and_count_images(readings)

    deleted_readings = session.query(AlprReading).delete(synchronize_session=False)
    session.commit()
    logger.info(
        "Eliminadas %s lecturas, %s mensajes y %s imágenes",
        deleted_readings,
        deleted_messages,
        deleted_images,
    )
    return {
        "readings": deleted_readings or 0,
        "messages": deleted_messages or 0,
        "images": deleted_images,
    }


def wipe_all_images() -> int:
    """Borra todas las imágenes físicas bajo ``IMAGES_DIR``."""

    images_dir = settings.IMAGES_DIR
    deleted_files = 0
    for root, _, files in os.walk(images_dir):
        for filename in files:
            filepath = os.path.join(root, filename)
            try:
                os.remove(filepath)
                deleted_files += 1
            except OSError as exc:  # pragma: no cover - defensivo
                logger.warning("No se pudo borrar %s: %s", filepath, exc)

    return deleted_files


def wipe_all_images_and_unset(session: Session) -> int:
    """Borra imágenes físicas y limpia referencias en la base de datos."""

    readings = list(session.execute(select(AlprReading)).scalars())
    deleted_files = 0
    for reading in readings:
        deleted_files += _log_and_count_images([reading])
    deleted_files += wipe_all_images()
    session.commit()
    logger.info("Borradas %s imágenes físicas y referencias en lecturas", deleted_files)
    return deleted_files


def full_wipe(session: Session) -> dict:
    """Limpieza total de lecturas, cola e imágenes."""

    deleted_queue = wipe_all_queue(session)
    readings_summary = wipe_all_readings(
        session, delete_images=True, delete_queue=False
    )
    deleted_images = wipe_all_images()
    return {
        "messages": deleted_queue,
        "readings": readings_summary.get("readings", 0),
        "images": deleted_images + readings_summary.get("images", 0),
    }
