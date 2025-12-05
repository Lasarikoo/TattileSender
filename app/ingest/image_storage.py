"""Helpers para guardar imágenes ALPR en disco."""
from __future__ import annotations

import base64
from datetime import datetime

from app.logger import logger
from app.utils.images import build_image_paths, normalize_plate


def save_reading_image_base64(
    plate: str,
    device_sn: str,
    timestamp_utc: datetime,
    kind: str,
    base64_data: str,
) -> str | None:
    """Guarda una imagen ALPR (OCR o contexto) en disco.

    Devuelve la ruta relativa del fichero escrito o ``None`` si ocurre un error
    al decodificar o persistir los bytes. Está pensada para consumir
    directamente las etiquetas ``IMAGE_OCR`` / ``IMAGE_CTX`` del XML de Tattile.
    """

    plate_clean = normalize_plate(plate)

    rel_ocr, rel_ctx, full_ocr, full_ctx = build_image_paths(
        device_sn, timestamp_utc, plate_clean
    )
    target_rel, target_full = (
        (rel_ocr, full_ocr) if kind == "ocr" else (rel_ctx, full_ctx)
    )

    try:
        image_bytes = base64.b64decode(base64_data)
    except Exception as e:  # pragma: no cover - logging defensivo
        logger.error(
            "[IMAGEN][ERROR] Error decodificando imagen %s para cámara %s, matrícula=%s: %s",
            kind,
            device_sn,
            plate_clean,
            e,
        )
        return None

    try:
        target_full.write_bytes(image_bytes)
    except Exception as e:  # pragma: no cover - logging defensivo
        logger.error(
            "[IMAGEN][ERROR] Error guardando imagen %s en %s: %s",
            kind,
            target_full,
            e,
        )
        return None

    logger.info(
        "[IMAGEN] Imagen %s guardada para lectura de %s: %s",
        kind.upper(),
        device_sn,
        target_full,
    )
    return target_rel
