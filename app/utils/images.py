"""Utilidades comunes para manejo de imágenes ALPR."""
from __future__ import annotations

import base64
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterable, Optional, Tuple

from app.config import settings
from app.logger import logger


IMAGES_BASE = Path(settings.images_dir)


def normalize_plate(plate: Optional[str]) -> str:
    """Normaliza la matrícula para usarla en nombres de fichero."""

    if not plate:
        return "unknown"
    return plate.replace(" ", "").upper()


def build_image_paths(
    device_sn: str, ts: datetime, plate: str
) -> Tuple[str, str, Path, Path]:
    """Construye rutas relativas y absolutas para imágenes de una lectura."""

    date_path = ts.strftime("%Y/%m/%d")
    ts_str = ts.strftime("%Y%m%d%H%M%S")

    rel_dir = Path(device_sn) / date_path
    ocr_filename = f"{ts_str}_plate-{plate}_ocr.jpg"
    ctx_filename = f"{ts_str}_plate-{plate}_ctx.jpg"

    rel_ocr = rel_dir / ocr_filename
    rel_ctx = rel_dir / ctx_filename

    full_dir = IMAGES_BASE / rel_dir
    full_dir.mkdir(parents=True, exist_ok=True)

    full_ocr = full_dir / ocr_filename
    full_ctx = full_dir / ctx_filename

    return str(rel_ocr), str(rel_ctx), full_ocr, full_ctx


def resolve_image_path(path_from_db: Optional[str]) -> Path:
    """Normaliza la ruta de imagen guardada en base de datos."""

    if not path_from_db:
        return Path()

    p = Path(path_from_db)

    if p.is_absolute():
        return p

    raw = str(p)
    if raw.startswith("data/images/"):
        raw = raw.replace("data/images/", "", 1)
        p = Path(raw)

    return IMAGES_BASE / p


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
    rel_ocr, rel_ctx, full_ocr, full_ctx = build_image_paths(device_sn, ts, safe_plate)
    target_rel, target_full = (
        (rel_ocr, full_ocr) if kind == "ocr" else (rel_ctx, full_ctx)
    )

    try:
        image_bytes = base64.b64decode(base64_data)
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("[IMAGEN][ERROR] Error decodificando imagen %s: %s", kind, exc)
        return None

    try:
        target_full.write_bytes(image_bytes)
    except OSError as exc:  # pragma: no cover - filesystem
        logger.error(
            "[IMAGEN][ERROR] No se pudo escribir la imagen %s en %s: %s",
            kind,
            target_full,
            exc,
        )
        return None

    logger.info("[IMAGEN] Imagen %s guardada en %s", kind, target_rel)
    return str(target_rel)


def delete_reading_images(reading) -> None:
    """Elimina las imágenes asociadas a una lectura si existen."""

    paths: Iterable[Optional[str]] = (
        reading.image_ocr_path if reading else None,
        reading.image_ctx_path if reading else None,
    )
    for rel_path in paths:
        full_path = resolve_image_path(rel_path)
        if not rel_path:
            continue
        try:
            if full_path.is_file():
                full_path.unlink()
        except OSError as exc:  # pragma: no cover - defensive
            logger.warning("[CLEANUP] Error al eliminar imagen %s: %s", full_path, exc)
