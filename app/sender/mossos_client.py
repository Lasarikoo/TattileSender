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
from zeep.wsse.signature import Signature

from app.logger import logger
from app.models import AlprReading, Camera
from app.utils.images import resolve_image_path

MATRICULA_NS = "http://dgp.gencat.cat/matricules"
BINDING_QNAME = "{http://dgp.gencat.cat/matricules}MatriculesSoap11"


@dataclass
class MossosSendResult:
    success: bool
    http_status: Optional[int]
    codi_retorn: Optional[str]
    fault: Optional[str]
    raw_response: Optional[str] = None


def _encode_image_base64(path: Optional[str], label: str) -> bytes:
    if not path:
        raise FileNotFoundError(f"Ruta de imagen no disponible para {label}")

    full_path = resolve_image_path(path)
    if not full_path.is_file():
        raise FileNotFoundError(f"{label}: fichero no encontrado en {full_path}")

    return base64.b64encode(full_path.read_bytes())


class MossosZeepClient:
    """Cliente Zeep que firma peticiones con certificado X509."""

    def __init__(
        self,
        wsdl_url: str,
        endpoint_url: str | None,
        cert_path: str,
        key_path: str,
        timeout: float = 5.0,
    ) -> None:
        session = requests.Session()
        session.verify = True

        if not os.path.isfile(cert_path):
            raise FileNotFoundError(f"Certificado cliente no encontrado: {cert_path}")
        if not os.path.isfile(key_path):
            raise FileNotFoundError(f"Clave privada no encontrada: {key_path}")

        transport = Transport(session=session, timeout=timeout)

        self.client = Client(
            wsdl=wsdl_url,
            transport=transport,
            wsse=Signature(key_path, cert_path),
            settings=Settings(strict=True, xml_huge_tree=True),
        )
        self.service = (
            self.client.create_service(BINDING_QNAME, endpoint_url)
            if endpoint_url
            else self.client.service
        )
        self.matricula_request_element = self.client.get_element(
            "{http://dgp.gencat.cat/matricules}matriculaRequest"
        )
        logger.info("[MOSSOS] WS-Security X509 Signature habilitada (endpoint=%s)", endpoint_url)

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
        img_ocr_b64 = _encode_image_base64(reading.image_ocr_path, "imgMatricula")
        img_ctx_b64 = b""
        if getattr(reading, "has_image_ctx", False) and reading.image_ctx_path:
            img_ctx_b64 = _encode_image_base64(reading.image_ctx_path, "imgContext")

        coord_x_value = camera.coord_x or (
            f"{camera.utm_x:.2f}" if camera.utm_x is not None else None
        )
        coord_y_value = camera.coord_y or (
            f"{camera.utm_y:.2f}" if camera.utm_y is not None else None
        )

        matricula_el = self.matricula_request_element(
            codiLector=camera.codigo_lector,
            matricula=reading.plate or "",
            dataLectura=data_str,
            horaLectura=hora_str,
            imgMatricula=img_ocr_b64,
            imgContext=img_ctx_b64,
            coordenadaX=coord_x_value,
            coordenadaY=coord_y_value,
            marca=getattr(reading, "brand", None),
            model=getattr(reading, "model", None),
            color=getattr(reading, "color", None),
            tipusVehicle=getattr(reading, "vehicle_type", None),
            pais=getattr(reading, "country_code", None),
        )

        logger.debug(
            "[MOSSOS][DEBUG] Solicitud matriculaRequest construida para lectura %s",
            getattr(reading, "id", None),
        )
        return matricula_el

    def send_matricula(self, reading: AlprReading, camera: Camera) -> MossosSendResult:
        request_el = self.build_matricula_request(reading, camera)
        try:
            response = self.service.matricula(matriculaRequest=request_el)
            codi_retorn = getattr(response, "codiRetorn", None)
            success = codi_retorn in ("OK", "0000", "1")
            return MossosSendResult(
                success=success,
                http_status=200,
                codi_retorn=codi_retorn,
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
