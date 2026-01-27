# Arquitectura

## Componentes principales
- **Servicio de ingesta TCP** (`app.ingest.service`): escucha en `TRANSIT_PORT`, recibe XML Tattile, parsea campos y persiste lecturas en PostgreSQL junto con las imágenes decodificadas.
- **API FastAPI principal** (`app.api.main`): expone `/health` y `/ingest/lectorvision` para convertir JSON Lector Vision a XML Tattile.
- **API Lector Vision opcional** (`app.api.lectorvision`): servicio dedicado con el mismo endpoint `/ingest/lectorvision`, pensado para ejecutarse en el puerto 33335.
- **Sender worker** (`app.sender.worker`): lee `messages_queue`, firma con WS-Security (X.509) y envía al SOAP de Mossos. Gestiona reintentos, backoff y limpieza tras éxito.
- **Base de datos PostgreSQL**: tablas `municipalities`, `cameras`, `certificates`, `endpoints`, `alpr_readings`, `messages_queue`.
- **Almacenamiento de imágenes** (`IMAGES_BASE_DIR`): guarda imágenes OCR/Context como ficheros en disco.

## Flujo general (texto)
```
Tattile XML (TCP)
  └─> Ingest TCP
        └─> parse_tattile_xml
              ├─> guarda imágenes (OCR/CTX)
              ├─> inserta alpr_readings
              └─> inserta messages_queue (PENDING)

Lector Vision JSON (HTTP)
  └─> API /ingest/lectorvision
        └─> build_tattile_xml_from_lectorvision
              └─> process_tattile_payload (flujo igual al TCP)

messages_queue (PENDING/FAILED)
  └─> Sender worker
        ├─> valida cámara, municipio, certificado y endpoint
        ├─> compone SOAP matricula y firma WS-Security
        ├─> envía a Mossos
        └─> SUCCESS => borra lectura + imágenes + mensaje
             FAILED => backoff y reintento
             DEAD => se descarta por error de datos/imagen
```

## Estados de la cola (`messages_queue`)
- `PENDING`: lectura lista para enviar.
- `SENDING`: la lectura está en proceso (se recupera como `FAILED` si supera el timeout de bloqueo).
- `FAILED`: envío fallido con posibilidad de reintento.
- `DEAD`: lectura descartada (ej. sin OCR, sin certificado, error de datos).
- `SUCCESS`: estado de éxito antes de la limpieza (se elimina el registro).

## Tolerancia a fallos
- Mensajes atascados en `SENDING` se recuperan automáticamente tras `SENDER_STUCK_TIMEOUT_SECONDS`.
- Si falta OCR o el fichero de imagen no existe, la lectura se marca `DEAD` y no se reintenta.
- Errores de red o SOAP Fault generan reintentos hasta `retry_max`.

## Dependencias clave
- **FastAPI + Uvicorn** para APIs HTTP.
- **SQLAlchemy + Alembic** para persistencia.
- **Zeep + WS-Security** para SOAP con firma X.509.
