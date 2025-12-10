"""Cliente SOAP basado en Zeep con firma WS-Security X509."""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests
from zeep import Client, Settings
from zeep.exceptions import Fault, TransportError
from zeep.helpers import serialize_object
from zeep.plugins import Plugin
from zeep.transports import Transport

from app.sender.wsse import TimestampedBinarySignature

from app.logger import logger
from app.models import AlprReading, Camera
from app.utils.images import resolve_image_path

MATRICULA_NS = "http://dgp.gencat.cat/matricules"
BINDING_QNAME = "{http://dgp.gencat.cat/matricules}MatriculesSoap11"


class NoVerifySignature(TimestampedBinarySignature):
    """Firma WS-Security sin verificación de respuesta."""

    def verify(self, envelope):
        # Mossos no firma la respuesta con WS-Security.
        # No intentamos buscar <wsse:Security> ni <ds:Signature>.
        return envelope


class SoapDebugPlugin(Plugin):
    """Plugin opcional para volcar el XML final cuando SOAP_DEBUG=1."""

    def egress(self, envelope, http_headers, operation, binding_options):
        from lxml import etree

        xml = etree.tostring(envelope, pretty_print=True, encoding="unicode")
        logger.info("[MOSSOS][SOAP DEBUG] Envelope:\n%s", xml)
        return envelope, http_headers


@dataclass
class MossosSendResult:
    success: bool
    http_status: Optional[int]
    codi_retorn: Optional[str]
    fault: Optional[str]
    raw_response: Optional[str] = None

def load_image_base64(path: Optional[str]) -> bytes:
    if not path:
        raise FileNotFoundError("Ruta de imagen no disponible")

    full_path = resolve_image_path(path)
    if not full_path.is_file():
        raise FileNotFoundError(f"Fichero no encontrado en {full_path}")

    return base64.b64encode(full_path.read_bytes())


class MossosZeepClient:
    """Cliente Zeep que firma peticiones con certificado X509."""

    def __init__(
        self,
        *,
        wsdl_url: str,
        endpoint_url: str,
        cert_path: str,
        key_path: str,
        timeout: float = 5.0,
    ) -> None:
        session = requests.Session()
        session.verify = True

        if not endpoint_url:
            raise ValueError("Endpoint SOAP no configurado")

        if not os.path.isfile(cert_path):
            raise FileNotFoundError(f"Certificado cliente no encontrado: {cert_path}")
        if not os.path.isfile(key_path):
            raise FileNotFoundError(f"Clave privada no encontrada: {key_path}")

        transport = Transport(session=session, timeout=timeout)

        plugins = []
        if os.getenv("SOAP_DEBUG") == "1":
            plugins.append(SoapDebugPlugin())

        self.client = Client(
            wsdl=wsdl_url,
            transport=transport,
            wsse=NoVerifySignature(key_file=key_path, certfile=cert_path),
            settings=Settings(strict=True, xml_huge_tree=True),
            plugins=plugins or None,
        )
        self.service = self.client.create_service(BINDING_QNAME, endpoint_url)
        logger.debug(
            "[MOSSOS] WS-Security X509 Signature habilitada (endpoint=%s)",
            endpoint_url,
        )

    def _format_date_time(self, timestamp: datetime) -> tuple[str, str]:
        ts = timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        return ts.strftime("%Y-%m-%d"), ts.strftime("%H:%M:%S")

    def build_matricula_request(self, reading: AlprReading, camera: Camera):
        if not reading.timestamp_utc:
            raise ValueError("La lectura no tiene timestamp para matriculaRequest")

        data_str, hora_str = self._format_date_time(reading.timestamp_utc)
        plate = (reading.plate or "").strip().upper()[:10]
        img_ocr_b64 = load_image_base64(reading.image_ocr_path)
        img_ctx_b64 = b""
        if getattr(reading, "has_image_ctx", False) and reading.image_ctx_path:
            img_ctx_b64 = load_image_base64(reading.image_ctx_path)

        coord_x_value = camera.coord_x or (
            f"{camera.utm_x:.2f}" if camera.utm_x is not None else None
        )
        coord_y_value = camera.coord_y or (
            f"{camera.utm_y:.2f}" if camera.utm_y is not None else None
        )

        payload = {
            "codiLector": camera.codigo_lector,
            "matricula": plate,
            "dataLectura": data_str,
            "horaLectura": hora_str,
            "imgMatricula": img_ocr_b64,
            "imgContext": img_ctx_b64,
        }

        if coord_x_value is not None:
            payload["coordenadaX"] = coord_x_value
        if coord_y_value is not None:
            payload["coordenadaY"] = coord_y_value

        for attr, key in [
            ("brand", "marca"),
            ("model", "model"),
            ("color", "color"),
            ("vehicle_type", "tipusVehicle"),
            ("country_code", "pais"),
        ]:
            value = getattr(reading, attr, None)
            if value is not None:
                payload[key] = value

        logger.debug(
            "[MOSSOS][DEBUG] Enviando matricula=%s codiLector=%s fecha=%s hora=%s",
            plate,
            camera.codigo_lector,
            data_str,
            hora_str,
        )
        return payload

    def send_matricula(self, reading: AlprReading, camera: Camera) -> MossosSendResult:
        request_data = self.build_matricula_request(reading, camera)
        try:
            logger.debug("[MOSSOS][DEBUG] Payload matricula: %s", request_data)
            response = self.service.matricula(**request_data)
            serialized = serialize_object(response)
            logger.debug("[MOSSOS][DEBUG] Respuesta serializada de matricula(): %r", serialized)
            logger.debug("[MOSSOS][DEBUG] Respuesta recibida correctamente")
            if serialized in (1, "1"):
                return MossosSendResult(
                    success=True,
                    http_status=200,
                    codi_retorn=str(serialized),
                    fault=None,
                    raw_response=str(serialized),
                )
            if response is None:
                return MossosSendResult(
                    success=False,
                    http_status=200,
                    codi_retorn=None,
                    fault="RESPUESTA_VACIA",
                    raw_response=None,
                )

            codi_retorn = getattr(response, "codiRetorn", None)
            serialized_codi_retorn = None
            if isinstance(serialized, dict):
                serialized_codi_retorn = serialized.get("codiRetorn")

            normalized_code = None
            for code_candidate in (codi_retorn, serialized_codi_retorn):
                if code_candidate is not None:
                    normalized_code = str(code_candidate)
                    break

            explicit_error_code = None
            explicit_error_msg = None
            resultat_value = None
            if isinstance(serialized, dict):
                explicit_error_code = serialized.get("codiError") or serialized.get("errorCode")
                explicit_error_msg = serialized.get("error") or serialized.get("descripcio")
                resultat_value = serialized.get("resultat")
            else:
                explicit_error_code = getattr(response, "codiError", None)
                explicit_error_msg = getattr(response, "error", None)
                resultat_value = getattr(response, "resultat", None)

            error_resultat = resultat_value not in (None, "", 0, "0", "OK", "1", "1.0", 1, 1.0)

            if explicit_error_code or explicit_error_msg or error_resultat:
                error_parts = []
                if explicit_error_code:
                    error_parts.append(f"codiError={explicit_error_code}")
                if explicit_error_msg:
                    error_parts.append(str(explicit_error_msg))
                if error_resultat:
                    error_parts.append(f"resultat={resultat_value}")
                error_detail = " | ".join(error_parts) or "RESPUESTA_ERROR_DESCONOCIDO"
                return MossosSendResult(
                    success=False,
                    http_status=200,
                    codi_retorn=normalized_code,
                    fault=error_detail,
                    raw_response=str(serialized),
                )

            success_codes = ("OK", "0000", "1", "1.0")
            success = normalized_code in success_codes or normalized_code is None
            return MossosSendResult(
                success=success,
                http_status=200,
                codi_retorn=normalized_code,
                fault=None,
                raw_response=str(serialized),
            )
        except Fault as fault:
            logger.error(
                "[MOSSOS][FAULT] %s: %s", fault.code if hasattr(fault, "code") else "FAULT", fault.message
            )
            return MossosSendResult(
                success=False,
                http_status=None,
                codi_retorn=None,
                fault=f"{fault.code}: {fault.message}",
            )
        except TransportError as exc:
            logger.error("[MOSSOS][ERROR] Error de transporte: %s", exc)
            return MossosSendResult(
                success=False,
                http_status=getattr(exc, "status_code", None),
                codi_retorn=None,
                fault=str(exc),
            )
        except Exception as exc:
            logger.exception("[MOSSOS][ERROR] Error inesperado enviando lectura %s", getattr(reading, "id", None))
            return MossosSendResult(
                success=False,
                http_status=None,
                codi_retorn=None,
                fault=str(exc),
            )


__all__ = ["MossosZeepClient", "MossosSendResult", "MATRICULA_NS"]
