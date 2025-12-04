"""Utilidades comunes para manejo de imágenes ALPR."""
from __future__ import annotations

import base64
import logging
import os
from datetime import datetime, timezone
from typing import Iterable, Optional

from app.config import settings

logger = logging.getLogger(__name__)


def normalize_plate(plate: Optional[str]) -> str:
    """Normaliza la matrícula para usarla en nombres de fichero."""

    if not plate:
        return "unknown"
    return plate.replace(" ", "").upper()


def resolve_image_path(path: Optional[str]) -> Optional[str]:
    """Devuelve una ruta absoluta a partir de ``IMAGES_DIR`` si es relativa."""

    if not path:
        return None
    if os.path.isabs(path):
        return path
    return os.path.join(settings.images_dir, path)


def save_reading_image(
    *,
    plate: str,
    device_sn: str,
    timestamp_utc: datetime,
    kind: str,
    base64_data: str,
) -> Optional[str]:
    """Guarda una imagen de lectura (OCR o contexto) y devuelve la ruta relativa."""

    if not base64_data:
        return None

    ts = timestamp_utc or datetime.now(timezone.utc)
    safe_plate = normalize_plate(plate)
    date_part = ts.strftime("%Y/%m/%d")
    ts_str = ts.strftime("%Y%m%d%H%M%S")

    target_dir = os.path.join(settings.images_dir, device_sn, date_part)
    try:
        os.makedirs(target_dir, exist_ok=True)
    except OSError as exc:  # pragma: no cover - defensive
        logger.error("No se pudo crear directorio de imágenes %s: %s", target_dir, exc)
        return None

    filename = f"{ts_str}_plate-{safe_plate}_{kind}.jpg"
    full_path = os.path.join(target_dir, filename)

    try:
        image_bytes = base64.b64decode(base64_data)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("No se pudo decodificar base64 de imagen %s: %s", kind, exc)
        return None

    try:
        with open(full_path, "wb") as f:
            f.write(image_bytes)
    except OSError as exc:  # pragma: no cover - filesystem
        logger.error("No se pudo escribir la imagen %s en %s: %s", kind, full_path, exc)
        return None

    rel_path = os.path.relpath(full_path, settings.images_dir)
    logger.info("[INGEST] Imagen %s almacenada en %s", kind, rel_path)
    return rel_path


def delete_reading_images(reading) -> None:
    """Elimina las imágenes asociadas a una lectura si existen."""

    paths: Iterable[Optional[str]] = (
        reading.image_ocr_path if reading else None,
        reading.image_ctx_path if reading else None,
    )
    for rel_path in paths:
        full_path = resolve_image_path(rel_path)
        if not full_path:
            continue
        try:
            if os.path.isfile(full_path):
                os.remove(full_path)
        except OSError as exc:  # pragma: no cover - defensive
            logger.warning("[CLEANUP] Error al eliminar imagen %s: %s", full_path, exc)
