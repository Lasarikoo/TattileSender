"""Conversión de payloads JSON de Lector Vision a XML Tattile."""
from __future__ import annotations

from datetime import datetime
from typing import Mapping, MutableMapping, Any
from xml.etree import ElementTree as ET


class LectorVisionError(ValueError):
    """Errores de validación o conversión de payload Lector Vision."""


IMAGE_OCR_KEYS = (
    "ImageOcr",
    "ImageOCR",
    "ImageOcrBase64",
    "ImageOCRBase64",
    "ImageOcrB64",
)
IMAGE_CTX_KEYS = (
    "ImageCtx",
    "ImageCTX",
    "ImageCtxBase64",
    "ImageCTXBase64",
    "ImageCtxB64",
)
CHAR_HEIGHT_KEYS = (
    "CharHeight",
    "PlateCharHeight",
    "PlateCharheight",
)


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_first(payload: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        raw = _as_str(payload.get(key))
        if raw:
            return raw
    return ""


def _require_payload_string(payload: Mapping[str, Any], key: str) -> str:
    value = _as_str(payload.get(key))
    if not value:
        raise LectorVisionError(f"Campo obligatorio ausente o vacío: {key}")
    return value


def parse_lectorvision_timestamp(timestamp_str: str) -> tuple[str, str]:
    """Convierte el timestamp de Lector Vision a DATE y TIME Tattile."""
    try:
        parsed = datetime.strptime(timestamp_str, "%Y/%m/%d %H:%M:%S.%f")
    except ValueError as exc:
        raise LectorVisionError(
            "TimeStamp inválido. Formato esperado: YYYY/MM/DD HH:MM:SS.mmm"
        ) from exc

    date_str = parsed.strftime("%Y-%m-%d")
    millis = int(parsed.microsecond / 1000)
    time_str = f"{parsed:%H-%M-%S}-{millis:03d}"
    return date_str, time_str


def build_tattile_xml_from_lectorvision(payload: Mapping[str, Any]) -> tuple[str, dict[str, str]]:
    """Genera el XML Tattile compatible a partir de un payload Lector Vision."""
    plate = _require_payload_string(payload, "Plate")
    device_sn = _as_str(payload.get("SerialNumber")) or _as_str(payload.get("IdDevice"))
    if not device_sn:
        raise LectorVisionError("Campo obligatorio ausente o vacío: SerialNumber/IdDevice")

    timestamp_raw = _require_payload_string(payload, "TimeStamp")
    date_str, time_str = parse_lectorvision_timestamp(timestamp_raw)

    root = ET.Element("root")

    def add_child(tag: str, value: Any | None) -> None:
        if value is None:
            return
        element = ET.SubElement(root, tag)
        element.text = str(value)

    add_child("PLATE_STRING", plate)
    add_child("DEVICE_SN", device_sn)
    add_child("DATE", date_str)
    add_child("TIME", time_str)

    image_ocr = _extract_first(payload, IMAGE_OCR_KEYS)
    image_ctx = _extract_first(payload, IMAGE_CTX_KEYS)
    add_child("IMAGE_OCR", image_ocr)
    add_child("IMAGE_CTX", image_ctx)

    ocr_score = _optional_int(payload.get("Fiability"))
    if ocr_score is not None:
        add_child("OCRSCORE", f"{ocr_score:03d}")

    add_child("DIRECTION", _as_str(payload.get("Direction")))

    lane_id = _optional_int(payload.get("LaneNumber"))
    if lane_id is not None:
        add_child("LANE_ID", lane_id)
    add_child("LANE_DESCR", _as_str(payload.get("LaneName")))

    plate_coord = payload.get("PlateCoord")
    if isinstance(plate_coord, (list, tuple)) and len(plate_coord) >= 4:
        coord_values = [_optional_int(value) for value in plate_coord[:4]]
        tags = (
            "ORIG_PLATE_MIN_X",
            "ORIG_PLATE_MIN_Y",
            "ORIG_PLATE_MAX_X",
            "ORIG_PLATE_MAX_Y",
        )
        for tag, value in zip(tags, coord_values):
            if value is not None:
                add_child(tag, value)

    country_code = _as_str(payload.get("Country"))
    if country_code:
        add_child("PLATE_COUNTRY_CODE", country_code)
        try:
            country_code_int = int(country_code)
        except ValueError:
            country_code_int = None
        add_child("PLATE_COUNTRY", "ES" if country_code_int == 724 else "")

    char_height = None
    for key in CHAR_HEIGHT_KEYS:
        char_height = _optional_int(payload.get(key))
        if char_height is not None:
            break
    if char_height is not None:
        add_child("CHAR_HEIGHT", char_height)

    xml_bytes = ET.tostring(root, encoding="utf-8")
    xml_str = xml_bytes.decode("utf-8")

    meta: MutableMapping[str, str] = {
        "plate": plate,
        "device_sn": device_sn,
        "timestamp": timestamp_raw,
    }
    return xml_str, dict(meta)
