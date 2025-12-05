"""Entry point para lanzar el servicio de ingesta.

Ejecuta este módulo con `python -m app.ingest.main`; leerá el puerto de
`TRANSIT_PORT` definido en el `.env` y pondrá a escuchar el servicio para
recibir XML desde las cámaras Tattile.
"""
from app.logger import logger  # noqa: F401 - inicializa configuración global
from app.ingest.service import run_ingest_service


if __name__ == "__main__":
    run_ingest_service()
