"""Helper para limpiar imágenes asociadas a lecturas enviadas."""
from __future__ import annotations

import logging
import os
from typing import Iterable

logger = logging.getLogger("sender")


def delete_reading_images(reading) -> None:
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
                logger.debug("[CLEANUP] Imagen no encontrada (¿ya borrada?): %s", p)
        except Exception as e:  # pragma: no cover - defensivo
            logger.warning("[CLEANUP] Error al borrar imagen %s: %s", p, e)
