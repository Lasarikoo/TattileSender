"""Stub del worker encargado de enviar lecturas a Mossos.

Responsabilidades previstas (no implementadas aún):
- Leer la cola de mensajes pendientes (lecturas normalizadas).
- Resolver qué certificado PFX y endpoint SOAP usar según cámara/municipio.
- Construir el SOAP firmado y enviarlo a Mossos por HTTPS.
- Gestionar reintentos, estados (`PENDING`, `SENT`, `FAILED`, etc.) y trazabilidad.
"""
from logging import getLogger

logger = getLogger(__name__)


def run_sender_worker() -> None:
    """Punto de entrada del worker de envíos.

    En la Fase 0 solo se deja un marcador. La implementación real interactuará
    con la base de datos y empleará certificados PFX para firmar las peticiones
    SOAP hacia el endpoint de Mossos.
    """

    logger.info("Worker de envío (stub) inicializado. Implementar en Fase 1.")
    # TODO: implementar lectura de cola y envío SOAP con firma de certificados.
    pass
