"""Aplicación FastAPI mínima para TattileSender.

Arráncala en desarrollo con `uvicorn app.api.main:app --reload` (o ajusta host
y puerto según sea necesario). Expone un endpoint `/health` básico con métricas
mínimas de la base de datos.
"""
from fastapi import FastAPI, HTTPException, status
from sqlalchemy import func

from app.ingest.lectorvision import LectorVisionError, build_tattile_xml_from_lectorvision
from app.ingest.service import process_tattile_payload
from app.logger import logger
from app.models import AlprReading, MessageQueue, MessageStatus, SessionLocal

app = FastAPI(title="TattileSender", version="0.1.0")


@app.get("/health")
def healthcheck() -> dict[str, int | str]:
    """Endpoint de salud y conteo mínimo de lecturas y cola."""

    session = SessionLocal()
    try:
        pending_messages = (
            session.query(func.count(MessageQueue.id))
            .filter(MessageQueue.status == MessageStatus.PENDING)
            .scalar()
        )
        failed_messages = (
            session.query(func.count(MessageQueue.id))
            .filter(MessageQueue.status == MessageStatus.FAILED)
            .scalar()
        )
        dead_messages = (
            session.query(func.count(MessageQueue.id))
            .filter(MessageQueue.status == MessageStatus.DEAD)
            .scalar()
        )
        total_readings = session.query(func.count(AlprReading.id)).scalar()
    finally:
        session.close()

    return {
        "status": "ok",
        "pending_messages": int(pending_messages or 0),
        "failed_messages": int(failed_messages or 0),
        "dead_messages": int(dead_messages or 0),
        "total_readings": int(total_readings or 0),
    }


@app.post("/ingest/lectorvision", status_code=status.HTTP_202_ACCEPTED)
def ingest_lectorvision(payload: dict) -> dict[str, str]:
    """Ingesta payloads JSON desde Lector Vision y los convierte a XML Tattile."""

    try:
        xml_str, meta = build_tattile_xml_from_lectorvision(payload)
    except LectorVisionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    session = SessionLocal()
    try:
        process_tattile_payload(xml_str, session)
    except Exception as exc:
        logger.exception("[API][INGEST] Error procesando payload Lector Vision")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error procesando lectura",
        ) from exc
    finally:
        session.close()

    logger.info(
        "[API][INGEST] Payload Lector Vision procesado plate=%s device_sn=%s timestamp=%s",
        meta.get("plate"),
        meta.get("device_sn"),
        meta.get("timestamp"),
    )

    return {"status": "accepted", "plate": meta.get("plate", ""), "device_sn": meta.get("device_sn", "")}
