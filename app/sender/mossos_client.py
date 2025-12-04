"""Cliente SOAP sencillo para enviar lecturas a Mossos.

El foco está en construir el envelope ``matriculaRequest`` y transmitirlo
por HTTPS usando certificados cliente en formato PEM (mTLS). Para escenarios
donde se requiera WS-Security con firma XML, el módulo deja puntos de extensión
claros y documentados sin añadir dependencias pesadas.
"""
from __future__ import annotations

import base64
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from xml.etree import ElementTree as ET

import requests
from lxml import etree as lxml_etree

from app.models import AlprReading, Camera, Municipality
from app.utils.images import resolve_image_path

logger = logging.getLogger("sender")
logger.setLevel(logging.DEBUG)
logger.propagate = True
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

SOAP_ENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"
MATRICULA_NS = "http://dgp.gencat.cat/matricules"


@dataclass
class MossosResult:
    """Resultado estandarizado de la operación ``matricula``."""

    success: bool
    code: Optional[int | str]
    error_message: Optional[str]
    raw_response: Optional[str]


class MossosClient:
    """Cliente ligero para el servicio SOAP de Mossos."""

    def __init__(
        self,
        endpoint_url: str,
        cert_full_path: str | tuple[str, str | None],
        cert_password: Optional[str] = None,
        timeout: float = 5.0,
        verify: bool = True,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.cert_full_path = cert_full_path
        self.cert_password = cert_password
        self.timeout = timeout
        self.verify = verify
        self._log_init()

    def _log_init(self) -> None:
        cert_path = self.cert_full_path
        cert_display = cert_path
        key_display = None
        if isinstance(cert_path, tuple):
            cert_display, key_display = cert_path
        logger.info("[CME] Inicializando cliente CME para endpoint=%s", self.endpoint_url)
        logger.info("[CME] Certificado usado: %s", cert_display)
        logger.info("[CME] Key usada: %s", key_display or "<no-key>")
        logger.debug("[CME] Verificación SSL: %s Timeout: %s", self.verify, self.timeout)
        if cert_display:
            logger.debug("[CME] Cert existe: %s", os.path.exists(cert_display))
        if key_display:
            logger.debug("[CME] Key existe: %s", os.path.exists(key_display))

    def _format_date_time(self, timestamp: datetime) -> tuple[str, str]:
        ts = timestamp.astimezone(timezone.utc) if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        return ts.strftime("%Y-%m-%d"), ts.strftime("%H:%M:%S")

    def _load_image_b64(self, path: Optional[str], label: str) -> str:
        full_path = resolve_image_path(path)
        if not full_path:
            raise FileNotFoundError(f"Ruta de imagen no disponible para {label}")
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"No se encontró el fichero de imagen {label}: {full_path}")
        with open(full_path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")

    def _build_xml(self, *, reading: AlprReading, camera: Camera) -> bytes:
        if not reading.timestamp_utc:
            raise ValueError("La lectura no tiene timestamp para matriculaRequest")

        data_str, hora_str = self._format_date_time(reading.timestamp_utc)

        img_ocr_b64 = None
        img_ctx_b64 = None
        try:
            img_ocr_b64 = self._load_image_b64(reading.image_ocr_path, "imgMatricula")
            img_ctx_b64 = self._load_image_b64(reading.image_ctx_path, "imgContext")
        except FileNotFoundError as exc:
            logger.error("[SENDER][MOSSOS][ERROR] %s", exc)
            raise

        if not img_ocr_b64 or not img_ctx_b64:
            raise ValueError("Missing images for matriculaRequest")

        ET.register_namespace("soapenv", SOAP_ENV_NS)
        ET.register_namespace("mat", MATRICULA_NS)

        envelope = ET.Element(ET.QName(SOAP_ENV_NS, "Envelope"))
        body = ET.SubElement(envelope, ET.QName(SOAP_ENV_NS, "Body"))
        request = ET.SubElement(body, ET.QName(MATRICULA_NS, "matriculaRequest"))

        ET.SubElement(request, ET.QName(MATRICULA_NS, "codiLector")).text = camera.codigo_lector
        ET.SubElement(request, ET.QName(MATRICULA_NS, "matricula")).text = reading.plate or ""
        ET.SubElement(request, ET.QName(MATRICULA_NS, "dataLectura")).text = data_str
        ET.SubElement(request, ET.QName(MATRICULA_NS, "horaLectura")).text = hora_str
        ET.SubElement(request, ET.QName(MATRICULA_NS, "imgMatricula")).text = img_ocr_b64
        ET.SubElement(request, ET.QName(MATRICULA_NS, "imgContext")).text = img_ctx_b64

        coord_x_value = camera.coord_x or (
            f"{camera.utm_x:.2f}" if camera.utm_x is not None else None
        )
        coord_y_value = camera.coord_y or (
            f"{camera.utm_y:.2f}" if camera.utm_y is not None else None
        )

        if coord_x_value and coord_y_value:
            ET.SubElement(request, ET.QName(MATRICULA_NS, "coordenadaX")).text = coord_x_value
            ET.SubElement(request, ET.QName(MATRICULA_NS, "coordenadaY")).text = coord_y_value
            logger.debug(
                "[CME] Coordenadas añadidas al SOAP X=%s Y=%s para cámara %s",
                coord_x_value,
                coord_y_value,
                camera.serial_number,
            )
        else:
            logger.warning(
                "[SENDER][MOSSOS][WARN] Cámara %s sin coordenadas X/Y definidas",
                camera.serial_number,
            )

        return ET.tostring(envelope, encoding="utf-8", xml_declaration=True)

    def _beautify_xml(self, xml_bytes: bytes) -> str:
        try:
            parsed = lxml_etree.fromstring(xml_bytes)
            return lxml_etree.tostring(parsed, pretty_print=True, encoding="unicode")
        except Exception:
            logger.debug("[CME] No se pudo formatear XML para logging", exc_info=True)
            return xml_bytes.decode("utf-8", errors="replace")

    def send_matricula(
        self, *, reading: AlprReading, camera: Camera, municipality: Municipality
    ) -> MossosResult:
        logger.info(
            "[CME] Generando SOAP para mensaje %s", reading.id
        )
        logger.debug(
            "[CME] Datos mensaje id=%s plate=%s ts=%s camera=%s municipio=%s",
            reading.id,
            reading.plate,
            reading.timestamp_utc,
            camera.serial_number,
            municipality.name if municipality else "?",
        )

        try:
            xml_payload = self._build_xml(reading=reading, camera=camera)
            logger.info(
                "[CME] Payload SOAP generado para lectura %s (tamaño=%s bytes)",
                reading.id,
                len(xml_payload),
            )
            logger.debug("[CME] XML Enviado:\n%s", self._beautify_xml(xml_payload))
        except Exception as exc:  # pragma: no cover - logging defensivo
            logger.exception(
                "[CME][ERROR] Error generando payload para lectura %s: %s",
                reading.id,
                exc,
            )
            return MossosResult(success=False, code=None, error_message=str(exc), raw_response=None)

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "matricula",
        }

        try:
            send_started = time.monotonic()
            response = requests.post(
                self.endpoint_url,
                data=xml_payload,
                headers=headers,
                timeout=self.timeout,
                cert=self.cert_full_path,
                verify=self.verify,
            )
            elapsed_ms = int((time.monotonic() - send_started) * 1000)
            logger.info(
                "[CME] Request SOAP completada status=%s duration_ms=%s", response.status_code, elapsed_ms
            )
            logger.debug(
                "[CME] Cabeceras respuesta: %s", dict(response.headers)
            )
            response.raise_for_status()
        except Exception as exc:  # pragma: no cover - logging defensivo
            logger.exception(
                "[CME][ERROR] Error HTTP/SSL leyendo_id=%s endpoint=%s", reading.id, self.endpoint_url
            )
            return MossosResult(success=False, code=None, error_message=str(exc), raw_response=None)

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            logger.error("[SENDER][MOSSOS][ERROR] Respuesta no parseable: %s", exc)
            logger.debug("[CME] XML Recibido bruto:\n%s", response.text)
            return MossosResult(success=False, code=None, error_message=str(exc), raw_response=response.text)

        fault = root.find(".//faultstring")
        if fault is not None:
            err_msg = fault.text or "SOAP Fault"
            logger.error("[SENDER][MOSSOS][ERROR] Fault reading_id=%s error=%s", reading.id, err_msg)
            logger.debug("[CME] XML Recibido:\n%s", self._beautify_xml(response.content))
            return MossosResult(success=False, code=None, error_message=err_msg, raw_response=response.text)

        resp_node = root.find(f".//{{{MATRICULA_NS}}}matriculaResponse")
        if resp_node is None:
            logger.error("[SENDER][MOSSOS][ERROR] Respuesta sin matriculaResponse")
            logger.debug("[CME] XML Recibido:\n%s", self._beautify_xml(response.content))
            return MossosResult(success=False, code=None, error_message="Respuesta sin matriculaResponse", raw_response=response.text)

        code_text = resp_node.findtext(f".//{{{MATRICULA_NS}}}codiRetorn")
        try:
            code_value = int(code_text) if code_text is not None else None
        except ValueError:
            code_value = code_text

        if code_value == 1:
            logger.info("[SENDER][MOSSOS] Envío OK reading_id=%s codiRetorn=1", reading.id)
            logger.debug("[CME] XML Recibido:\n%s", self._beautify_xml(response.content))
            return MossosResult(success=True, code=code_value, error_message=None, raw_response=response.text)

        error_msg = "Service not operational" if code_value == 0 else "Error en codiRetorn"
        logger.error(
            "[SENDER][MOSSOS][ERROR] reading_id=%s codiRetorn=%s", reading.id, code_value
        )
        logger.debug("[CME] XML Recibido:\n%s", self._beautify_xml(response.content))
        return MossosResult(success=False, code=code_value, error_message=error_msg, raw_response=response.text)
