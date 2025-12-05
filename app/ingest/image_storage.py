"""Helpers para guardar imágenes ALPR en disco."""
from __future__ import annotations

import base64
import os
from datetime import datetime

from app.config import settings
from app.logger import logger


def save_reading_image_base64(
    plate: str,
    device_sn: str,
    timestamp_utc: datetime,
    kind: str,
    base64_data: str,
) -> str | None:
    """Guarda una imagen ALPR (OCR o contexto) en disco.

    Devuelve la ruta absoluta del fichero escrito o ``None`` si ocurre un error
    al decodificar o persistir los bytes. Está pensada para consumir
    directamente las etiquetas ``IMAGE_OCR`` / ``IMAGE_CTX`` del XML de Tattile.
    """

    plate_clean = (plate or "").replace(" ", "").upper()

    base_dir = settings.IMAGES_DIR
    date_part = timestamp_utc.strftime("%Y/%m/%d")
    target_dir = os.path.join(base_dir, device_sn, date_part)
    os.makedirs(target_dir, exist_ok=True)

    ts_str = timestamp_utc.strftime("%Y%m%d%H%M%S")
    filename = f"{ts_str}_plate-{plate_clean}_{kind}.jpg"
    full_path = os.path.join(target_dir, filename)

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
        with open(full_path, "wb") as f:
            f.write(image_bytes)
    except Exception as e:  # pragma: no cover - logging defensivo
        logger.error(
            "[IMAGEN][ERROR] Error guardando imagen %s en %s: %s",
            kind,
            full_path,
            e,
        )
        return None

    logger.info("[IMAGEN] Imagen %s guardada para lectura de %s: %s", kind.upper(), device_sn, full_path)
    return full_path
