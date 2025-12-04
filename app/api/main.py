"""Aplicación FastAPI mínima para TattileSender.

Expone un endpoint `/health` básico con métricas mínimas de la base de datos.
"""
from fastapi import FastAPI
from sqlalchemy import func

from app.models import AlprReading, MessageQueue, SessionLocal

app = FastAPI(title="TattileSender", version="0.1.0")


@app.get("/health")
def healthcheck() -> dict[str, int | str]:
    """Endpoint de salud y conteo mínimo de lecturas y cola."""

    session = SessionLocal()
    try:
        pending_messages = session.query(func.count(MessageQueue.id)).filter(MessageQueue.status == "PENDING").scalar()
        total_readings = session.query(func.count(AlprReading.id)).scalar()
    finally:
        session.close()

    return {
        "status": "ok",
        "pending_messages": int(pending_messages or 0),
        "total_readings": int(total_readings or 0),
    }
