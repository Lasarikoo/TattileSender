"""Cliente SOAP sencillo para enviar lecturas a Mossos.

El foco está en construir el envelope ``matriculaRequest`` y transmitirlo
por HTTPS usando certificados cliente en formato PEM (mTLS). Para escenarios
donde se requiera WS-Security con firma XML, el módulo deja puntos de extensión
claros y documentados sin añadir dependencias pesadas.
"""
from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from xml.etree import ElementTree as ET

import requests
from lxml import etree as lxml_etree
from sqlalchemy.orm import Session

from app.logger import logger
from app.models import AlprReading, Camera, Municipality
from app.utils.images import resolve_image_path

SOAP_ENV_NS = "http://schemas.xmlsoap.org/soap/envelope/"
MATRICULA_NS = "http://dgp.gencat.cat/matricules"


@dataclass
class FaultInfo:
    faultcode: Optional[str]
    faultstring: Optional[str]
    detail: Optional[str] = None


@dataclass
class MatriculaRetInfo:
    codi_retorn: Optional[str]
    descripcion: Optional[str] = None


@dataclass
class MossosSendResult:
    success: bool
    http_status: Optional[int]
    error_message: Optional[str]
    fault: Optional[FaultInfo]
    matricula_ret: Optional[MatriculaRetInfo]
    raw_response_snippet: Optional[str]


@dataclass
class CertPair:
    cert_path: str
    key_path: str


def resolve_cert_pair_for_municipality(
    session: Session, municipality_id: int
) -> CertPair:
    municipality = session.get(Municipality, municipality_id)
    if not municipality:
        raise RuntimeError(f"Municipio no encontrado (id={municipality_id})")

    certificate = municipality.certificate
    if not certificate:
        raise RuntimeError(
            f"Municipio {municipality.name} sin certificado configurado"
        )

    if (
        certificate.type != "PEM"
        or not certificate.path
        or not certificate.key_path
    ):
        raise RuntimeError(
            f"Certificado mal configurado para municipio {municipality.name}: "
            f"type={certificate.type}, path={certificate.path}, key_path={certificate.key_path}. "
            "Debes descomprimir el PFX y asignar los PEM desde ajustes.sh."
        )

    cert_path = certificate.path
    key_path = certificate.key_path

    if not os.path.isfile(cert_path):
        raise RuntimeError(
            f"Certificado PEM no encontrado en disco para municipio {municipality.name}: {cert_path}"
        )
    if not os.path.isfile(key_path):
        raise RuntimeError(
            f"Clave privada no encontrada en disco para municipio {municipality.name}: {key_path}"
        )

    return CertPair(cert_path=cert_path, key_path=key_path)


class MossosClient:
    """Cliente ligero para el servicio SOAP de Mossos."""

    def __init__(
        self,
        endpoint_url: str,
        cert_full_path: str | tuple[str, str | None] | None = None,
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
        logger.info("[MOSSOS] Usando endpoint: %s", self.endpoint_url)
        logger.debug("[MOSSOS][DEBUG] Verificación SSL=%s Timeout=%s", self.verify, self.timeout)

    def _format_date_time(self, timestamp: datetime) -> tuple[str, str]:
        ts = timestamp.astimezone(timezone.utc) if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        return ts.strftime("%Y-%m-%d"), ts.strftime("%H:%M:%S")

    def _load_image_b64(self, path: Optional[str], label: str) -> str:
        if not path:
            raise FileNotFoundError(f"Ruta de imagen no disponible para {label}")

        full_path = resolve_image_path(path)
        if not full_path.is_file():
            raise FileNotFoundError(
                f"{label}: fichero no encontrado en {full_path}"
            )

        with open(full_path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")

    def _build_xml(self, *, reading: AlprReading, camera: Camera) -> bytes:
        if not reading.timestamp_utc:
            raise ValueError("La lectura no tiene timestamp para matriculaRequest")

        data_str, hora_str = self._format_date_time(reading.timestamp_utc)

        img_ctx_b64 = ""
        try:
            img_ocr_b64 = self._load_image_b64(reading.image_ocr_path, "imgMatricula")
            if reading.image_ctx_path:
                img_ctx_b64 = self._load_image_b64(
                    reading.image_ctx_path, "imgContext"
                )
        except FileNotFoundError as exc:
            logger.error("[MOSSOS][ERROR] %s", exc)
            raise

        if not img_ocr_b64:
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
                "[MOSSOS][DEBUG] Coordenadas añadidas al SOAP X=%s Y=%s para cámara %s",
                coord_x_value,
                coord_y_value,
                camera.serial_number,
            )
        else:
            logger.warning(
                "[MOSSOS][ADVERTENCIA] Cámara %s sin coordenadas X/Y definidas",
                camera.serial_number,
            )

        return ET.tostring(envelope, encoding="utf-8", xml_declaration=True)

    def _beautify_xml(self, xml_bytes: bytes) -> str:
        try:
            parsed = lxml_etree.fromstring(xml_bytes)
            return lxml_etree.tostring(parsed, pretty_print=True, encoding="unicode")
        except Exception:
            logger.debug("[MOSSOS][DEBUG] No se pudo formatear XML para logging", exc_info=True)
            return xml_bytes.decode("utf-8", errors="replace")

    def send_matricula(
        self,
        *,
        reading: AlprReading,
        camera: Camera,
        municipality: Municipality,
        session: Session,
    ) -> MossosSendResult:
        logger.info(
            "[MOSSOS] Generando SOAP para lectura %s, matrícula=%s",
            reading.id,
            reading.plate,
        )
        logger.debug(
            "[MOSSOS][DEBUG] Datos lectura id=%s ts=%s cámara=%s municipio=%s",
            reading.id,
            reading.timestamp_utc,
            camera.serial_number,
            municipality.name if municipality else "?",
        )

        try:
            xml_payload = self._build_xml(reading=reading, camera=camera)
            logger.info(
                "[MOSSOS] Payload SOAP generado para lectura %s (tamaño=%s bytes)",
                reading.id,
                len(xml_payload),
            )
            logger.debug("[MOSSOS][DEBUG] XML Enviado:\n%s", self._beautify_xml(xml_payload))
        except Exception as exc:  # pragma: no cover - logging defensivo
            logger.exception(
                "[MOSSOS][ERROR] Error generando SOAP para lectura %s: %s",
                reading.id,
                exc,
            )
            return MossosSendResult(
                success=False,
                http_status=None,
                error_message=str(exc),
                fault=None,
                matricula_ret=None,
                raw_response_snippet=None,
            )

        cert_pair = resolve_cert_pair_for_municipality(session, municipality.id)

        logger.info(
            "[CERT] Usando certificado PEM=%s key=%s",
            cert_pair.cert_path,
            cert_pair.key_path,
        )

        response = self._perform_request(
            xml_payload=xml_payload, cert_pair=cert_pair, reading_id=reading.id
        )
        if response is None:
            return MossosSendResult(
                success=False,
                http_status=None,
                error_message="Error de transporte",
                fault=None,
                matricula_ret=None,
                raw_response_snippet=None,
            )

        response_body = response.text
        status = response.status_code
        snippet = response_body[:2000]
        logger.info(
            "[MOSSOS][RESP_BODY] %s",
            snippet,
        )

        if status != 200:
            fault_info, matricula_info = self._parse_error_response(response_body)
            if fault_info:
                logger.error(
                    "[MOSSOS][FAULT] faultcode=%s faultstring=%s detail=%s",
                    fault_info.faultcode,
                    fault_info.faultstring,
                    fault_info.detail,
                )
            if matricula_info:
                logger.error(
                    "[MOSSOS][CODI_RETORN] codiRetorn=%s descr=%s",
                    matricula_info.codi_retorn,
                    matricula_info.descripcion,
                )
            if not fault_info and not matricula_info:
                logger.error("[MOSSOS][ERROR] Respuesta HTTP %s no parseable como SOAP", status)

            return MossosSendResult(
                success=False,
                http_status=status,
                error_message=f"HTTP {status}",
                fault=fault_info,
                matricula_ret=matricula_info,
                raw_response_snippet=snippet,
            )

        ret_info = self._parse_success_response(response_body)
        if ret_info:
            logger.info(
                "[MOSSOS][CODI_RETORN] codiRetorn=%s descr=%s",
                ret_info.codi_retorn,
                ret_info.descripcion,
            )
        else:
            logger.warning("[MOSSOS][ADVERTENCIA] Respuesta 200 sin codiRetorn identificable")

        success = ret_info is not None and (
            ret_info.codi_retorn in ("1", "0000")
        )

        return MossosSendResult(
            success=success,
            http_status=status,
            error_message=None if success else "Respuesta con error de negocio",
            fault=None,
            matricula_ret=ret_info,
            raw_response_snippet=snippet,
        )

    def _perform_request(
        self, *, xml_payload: bytes, cert_pair: CertPair, reading_id: int
    ) -> requests.Response | None:
        try:
            send_started = time.monotonic()
            response = requests.post(
                self.endpoint_url,
                data=xml_payload,
                headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": "matricula",
                },
                timeout=self.timeout,
                cert=(cert_pair.cert_path, cert_pair.key_path),
                verify=self.verify,
            )
            elapsed_ms = int((time.monotonic() - send_started) * 1000)
            logger.info(
                "[MOSSOS] Request completada status=%s duración_ms=%s",
                response.status_code,
                elapsed_ms,
            )
            logger.debug(
                "[MOSSOS][DEBUG] Cabeceras respuesta: %s", dict(response.headers)
            )
            return response
        except Exception as exc:  # pragma: no cover - logging defensivo
            logger.exception(
                "[MOSSOS][ERROR] Error HTTP/SSL para lectura %s: %s",
                reading_id,
                exc,
            )
            return None

    def _parse_error_response(
        self, xml_text: str
    ) -> tuple[FaultInfo | None, MatriculaRetInfo | None]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.error("[MOSSOS][ERROR] Respuesta no parseable como XML: %s", exc)
            logger.debug("[MOSSOS][DEBUG] XML bruto no parseable:\n%s", xml_text[:2000])
            return None, None

        fault_node = root.find(
            f".//{{{SOAP_ENV_NS}}}Fault"
        ) or root.find(".//faultcode")
        fault_info = None
        if fault_node is not None:
            faultcode = fault_node.findtext("faultcode") if fault_node.tag != "faultcode" else fault_node.text
            faultstring = (
                fault_node.findtext("faultstring")
                if fault_node.tag != "faultstring"
                else fault_node.text
            )
            detail = None
            detail_node = fault_node.find("detail") if fault_node.tag != "detail" else fault_node
            if detail_node is not None:
                detail = detail_node.text
            fault_info = FaultInfo(
                faultcode=faultcode,
                faultstring=faultstring,
                detail=detail,
            )

        matricula_info = self._parse_matricula_response(root)
        return fault_info, matricula_info

    def _parse_success_response(self, xml_text: str) -> MatriculaRetInfo | None:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.error("[MOSSOS][ERROR] Respuesta 200 no parseable: %s", exc)
            logger.debug("[MOSSOS][DEBUG] XML bruto:\n%s", xml_text[:2000])
            return None

        return self._parse_matricula_response(root)

    def _parse_matricula_response(self, root: ET.Element) -> MatriculaRetInfo | None:
        resp_node = root.find(f".//{{{MATRICULA_NS}}}matriculaResponse")
        if resp_node is None:
            return None

        codi_retorn = resp_node.findtext(f".//{{{MATRICULA_NS}}}codiRetorn")
        descripcion = (
            resp_node.findtext(f".//{{{MATRICULA_NS}}}descripcioRetorn")
            or resp_node.findtext(f".//{{{MATRICULA_NS}}}descripcio")
        )

        return MatriculaRetInfo(codi_retorn=codi_retorn, descripcion=descripcion)
