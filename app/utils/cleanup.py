"""Rutinas compartidas de limpieza."""
from __future__ import annotations

import logging
import os
from typing import Iterable

logger = logging.getLogger(__name__)


def delete_reading_images(reading) -> int:
    """Elimina las imágenes asociadas a una lectura.

    Devuelve cuántos ficheros se eliminaron.
    """

    deleted = 0
    paths: Iterable[str | None] = (
        reading.image_ocr_path if reading else None,
        reading.image_ctx_path if reading else None,
    )
    for path in paths:
        if not path:
            continue
        try:
            if os.path.isfile(path):
                os.remove(path)
                deleted += 1
            else:
                logger.debug("[CLEANUP] Imagen no encontrada (¿ya borrada?): %s", path)
        except Exception as exc:  # pragma: no cover - defensivo
            logger.warning("[CLEANUP] Error al borrar imagen %s: %s", path, exc)
    return deleted
