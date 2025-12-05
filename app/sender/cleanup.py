"""Helper para limpiar imágenes asociadas a lecturas enviadas."""
from __future__ import annotations

import os
from typing import Iterable

from app.logger import logger


def delete_reading_images(reading) -> None:
    if reading and getattr(reading, "id", None) is not None:
        logger.info("[CLEANUP] Eliminando imágenes de lectura %s", reading.id)

    paths: Iterable[str | None] = (
        reading.image_ocr_path if reading else None,
        reading.image_ctx_path if reading else None,
    )
    for p in paths:
        if not p:
            continue
        try:
            if os.path.isfile(p):
                os.remove(p)
            else:
                logger.info("[CLEANUP] Imagen no encontrada (ya eliminada): %s", p)
        except Exception as e:  # pragma: no cover - defensivo
            logger.warning("[CLEANUP] Error al borrar imagen %s: %s", p, e)
