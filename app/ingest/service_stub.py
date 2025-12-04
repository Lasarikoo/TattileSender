"""Stub del servicio de ingesta de lecturas Tattile.

Responsabilidades previstas (no implementadas aún):
- Escuchar en un puerto TCP/UDP (por ejemplo, 33334) los mensajes XML enviados
  por las cámaras Tattile.
- Parsear el XML y convertirlo en un objeto interno `ALPRReading`.
- Insertar la lectura en una cola persistente (base de datos) para que otro
  proceso la envíe hacia Mossos.
"""
from logging import getLogger

logger = getLogger(__name__)


def run_ingest_service() -> None:
    """Punto de entrada del servicio de ingesta.

    En la Fase 0 solo se deja un marcador. La implementación real abrirá sockets
    TCP/UDP, validará los payloads XML y escribirá en la cola de mensajes.
    """

    logger.info("Servicio de ingesta (stub) inicializado. Implementar en Fase 1.")
    # TODO: implementar servidor TCP/UDP que reciba y procese lecturas ALPR.
    pass
