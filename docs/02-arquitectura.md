# Arquitectura (resumen)

> **Nota:** la documentación técnica completa está en [`docs/architecture.md`](architecture.md).

## Componentes principales (actual)
- **Ingest TCP**: recibe XML Tattile y persiste lecturas + imágenes.
- **API FastAPI**: expone `/health` y `/ingest/lectorvision`.
- **Sender Worker**: consume `messages_queue`, firma SOAP con WS-Security y gestiona reintentos.
- **PostgreSQL**: tablas de cámaras, municipios, certificados, endpoints, lecturas y cola.

## Flujo resumido
Tattile XML → Ingest → `alpr_readings` + `messages_queue` → Sender → SOAP Mossos → limpieza de lectura/imagenes en éxito.
