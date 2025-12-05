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
from zeep.transports import Transport
from zeep.wsse.signature import BinarySignature

from app.logger import logger
from app.models import AlprReading, Camera
from app.utils.images import resolve_image_path

MATRICULA_NS = "http://dgp.gencat.cat/matricules"
BINDING_QNAME = "{http://dgp.gencat.cat/matricules}MatriculesSoap11"


class SignOnlySignature(BinarySignature):
    """
    Variante de BinarySignature que sólo firma las peticiones
    y NO intenta verificar la respuesta del servidor.
    """

    def verify(self, envelope):
        # No hacemos verificación de respuesta, simplemente devolvemos el envelope
        return envelope


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

        self.client = Client(
            wsdl=wsdl_url,
            transport=transport,
            wsse=SignOnlySignature(key_file=key_path, cert_file=cert_path),
            settings=Settings(strict=True, xml_huge_tree=True),
        )
        self.service = self.client.create_service(BINDING_QNAME, endpoint_url)
        logger.info(
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
            codi_retorn = getattr(response, "codiRetorn", None)
            normalized_code = str(codi_retorn) if codi_retorn is not None else None
            success = normalized_code in ("OK", "0000", "1", "1.0")
            return MossosSendResult(
                success=success,
                http_status=200,
                codi_retorn=normalized_code,
                fault=None,
                raw_response=str(response),
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
