"""Aplicación FastAPI mínima para TattileSender.

En fases posteriores se añadirán endpoints de administración, métricas y
observabilidad. Por ahora solo se expone `/health` para validar que la API se
levanta correctamente.
"""
from fastapi import FastAPI

app = FastAPI(title="TattileSender", version="0.0.0")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    """Devuelve el estado mínimo de la API."""
    return {"status": "ok", "service": "tattile-sender"}
