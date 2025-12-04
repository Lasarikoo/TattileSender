"""Parser del XML enviado por cámaras Tattile."""
from __future__ import annotations

from datetime import datetime, timezone
from xml.etree import ElementTree as ET


class TattileParseError(ValueError):
    """Error específico para problemas de parseo de XML Tattile."""


def _get_text(root: ET.Element, tag: str) -> str | None:
    element = root.find(tag)
    if element is None:
        return None
    if element.text is None:
        return None
    return element.text.strip()


def parse_tattile_xml(xml_str: str) -> dict:
    """
    Recibe el XML bruto de Tattile y devuelve un dict con los campos normalizados
    para construir un AlprReading.
    """

    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as exc:  # pragma: no cover - defensive
        raise TattileParseError(f"XML inválido: {exc}") from exc

    plate = _get_text(root, "PLATE_STRING")
    device_sn = _get_text(root, "DEVICE_SN")

    if not plate:
        raise TattileParseError("Campo obligatorio PLATE_STRING ausente o vacío")
    if not device_sn:
        raise TattileParseError("Campo obligatorio DEVICE_SN ausente o vacío")

    date_str = _get_text(root, "DATE")
    time_str = _get_text(root, "TIME")
    timestamp_utc = None
    if date_str and time_str:
        try:
            date_obj = datetime.fromisoformat(date_str).date()
            time_parts = time_str.split("-")
            if len(time_parts) == 4:
                hours, minutes, seconds, millis = map(int, time_parts)
                timestamp_utc = datetime(
                    year=date_obj.year,
                    month=date_obj.month,
                    day=date_obj.day,
                    hour=hours,
                    minute=minutes,
                    second=seconds,
                    microsecond=millis * 1000,
                    tzinfo=timezone.utc,
                )
            else:  # pragma: no cover - defensive
                raise ValueError("Formato TIME inesperado")
        except Exception as exc:  # pragma: no cover - defensive
            raise TattileParseError(f"Error procesando fecha/hora: {exc}") from exc
    # Asumimos que la cámara ya entrega el tiempo en UTC para Fase 1.

    bbox_min_x = _get_text(root, "ORIG_PLATE_MIN_X")
    bbox_min_y = _get_text(root, "ORIG_PLATE_MIN_Y")
    bbox_max_x = _get_text(root, "ORIG_PLATE_MAX_X")
    bbox_max_y = _get_text(root, "ORIG_PLATE_MAX_Y")
    char_height = _get_text(root, "CHAR_HEIGHT") or _get_text(root, "PLATE_CHAR_HEIGHT")

    image_ocr_b64 = _get_text(root, "IMAGE_OCR")
    image_ctx_b64 = _get_text(root, "IMAGE_CTX")

    parsed = {
        "plate": plate,
        "timestamp_utc": timestamp_utc,
        "device_sn": device_sn,
        "direction": _get_text(root, "DIRECTION"),
        "lane_id": int(_get_text(root, "LANE_ID")) if _get_text(root, "LANE_ID") else None,
        "lane_descr": _get_text(root, "LANE_DESCR"),
        "ocr_score": int(_get_text(root, "OCRSCORE")) if _get_text(root, "OCRSCORE") else None,
        "country_code": _get_text(root, "PLATE_COUNTRY_CODE"),
        "country": _get_text(root, "PLATE_COUNTRY"),
        "bbox_min_x": int(bbox_min_x) if bbox_min_x else None,
        "bbox_min_y": int(bbox_min_y) if bbox_min_y else None,
        "bbox_max_x": int(bbox_max_x) if bbox_max_x else None,
        "bbox_max_y": int(bbox_max_y) if bbox_max_y else None,
        "char_height": int(char_height) if char_height else None,
        "has_image_ocr": bool(image_ocr_b64),
        "has_image_ctx": bool(image_ctx_b64),
        "image_ocr_b64": image_ocr_b64,
        "image_ctx_b64": image_ctx_b64,
        "raw_xml": xml_str,
    }

    return parsed
