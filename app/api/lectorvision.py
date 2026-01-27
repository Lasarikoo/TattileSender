"""Aplicación FastAPI para ingesta de lecturas Lector Vision."""
from fastapi import FastAPI, HTTPException, status

from app.ingest.lectorvision import LectorVisionError, build_tattile_xml_from_lectorvision
from app.ingest.service import process_tattile_payload
from app.logger import logger
from app.models import Camera, SessionLocal

app = FastAPI(title="TattileSender Lector Vision", version="0.1.0")


@app.post("/ingest/lectorvision", status_code=status.HTTP_202_ACCEPTED)
def ingest_lectorvision(payload: dict) -> dict[str, str]:
    """Ingesta payloads JSON desde Lector Vision y los convierte a XML Tattile."""

    try:
        xml_str, meta = build_tattile_xml_from_lectorvision(payload)
    except LectorVisionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    session = SessionLocal()
    try:
        device_sn = meta.get("device_sn")
        camera = session.query(Camera).filter(Camera.serial_number == device_sn).first()
        if not camera:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cámara no registrada",
            )

        process_tattile_payload(xml_str, session)
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        logger.exception("[LECTORVISION] Error procesando payload")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error procesando lectura",
        ) from exc
    finally:
        session.close()

    logger.info(
        "[LECTORVISION] Payload procesado plate=%s device_sn=%s timestamp=%s",
        meta.get("plate"),
        meta.get("device_sn"),
        meta.get("timestamp"),
    )

    return {"status": "accepted", "plate": meta.get("plate", ""), "device_sn": meta.get("device_sn", "")}
