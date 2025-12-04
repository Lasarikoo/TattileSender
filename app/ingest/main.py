"""Entry point para lanzar el servicio de ingesta."""
from app.ingest.service import run_ingest_service


if __name__ == "__main__":
    run_ingest_service()
