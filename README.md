# TattileSender

Plataforma backend en Python para recibir lecturas ALPR (XML Tattile), almacenar imágenes y reenviar las lecturas al servicio SOAP de Mossos d'Esquadra con firma WS-Security X.509. Incluye un servicio TCP de ingesta, APIs FastAPI para healthcheck y conversión de payloads Lector Vision, y un worker de envío con control de reintentos.

## 1️⃣ Introducción
**¿Qué es?** Un sistema compuesto por:
- Servicio **Ingest** (TCP) que recibe XML Tattile, parsea el contenido, guarda imágenes en disco y encola lecturas en PostgreSQL.
- **API FastAPI** con `/health` y endpoint `/ingest/lectorvision` para convertir JSON Lector Vision a XML Tattile.
- **Sender worker** que consume la cola `messages_queue`, firma y envía lecturas al servicio SOAP, y limpia datos en éxito.

**Flujo de alto nivel**
1. Las cámaras Tattile envían XML + imágenes en Base64 al servicio **Ingest** (TCP).
2. **Ingest** guarda imágenes, crea el registro `alpr_readings` y encola el mensaje `messages_queue` en `PENDING`.
3. **Sender** toma mensajes `PENDING`/`FAILED`, construye el SOAP `matricula`, firma con WS-Security y envía a Mossos.
4. En éxito (`codiRetorn` con código OK) elimina lectura + imágenes + mensaje. En error aplica backoff y reintentos.

Para detalles técnicos completos consulta la documentación en [`docs/`](docs/).

## 2️⃣ Requisitos
- **Python 3.10+** (recomendado 3.11).
- **PostgreSQL 13+** accesible desde el host.
- **OpenSSL** para extraer certificados de PFX/P12.
- Acceso a certificados X.509 (cliente) y clave privada en formato PEM.

Puertos por defecto:
- API HTTP principal: **8000**.
- API Lector Vision (opcional, servicio separado): **33335**.
- Ingest TCP Tattile: **TRANSIT_PORT** (por defecto **33334**).

## 3️⃣ Instalación rápida (desarrollo local)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edita .env con tus valores
python -m alembic upgrade head
```

### 3.1 Arranque manual
- Ingest TCP:
  ```bash
  python -m app.ingest.main
  ```
- API principal:
  ```bash
  uvicorn app.api.main:app --host 0.0.0.0 --port 8000
  ```
- API Lector Vision (opcional):
  ```bash
  uvicorn app.api.lectorvision:app --host 0.0.0.0 --port 33335
  ```
- Sender worker:
  ```bash
  python -m app.sender.main
  ```

### 3.2 Instalación automatizada en VPS
`./setup.sh` crea `.venv`, instala dependencias, ejecuta migraciones y genera servicios systemd:
- `tattile-api.service`
- `tattile-ingest.service`
- `tattile-sender.service`
- `tattile-lectorvision.service`

> **Nota:** `setup.sh` exige un `.env` válido y usa los valores de DB para crear la base de datos si no existe.

## 4️⃣ Configuración (`.env`)
Las variables se leen con Pydantic (`app/config.py`) y se pueden definir en `.env` o en el entorno. Ejemplo seguro:

```env
APP_ENV=prod
DB_HOST=localhost
DB_PORT=5432
DB_NAME=tattile_sender
DB_USER=tattile_user
DB_PASSWORD=change_me
CERTS_DIR=/etc/tattile_sender/certs
IMAGES_BASE_DIR=/data/images
TRANSIT_PORT=33334
LOG_LEVEL=INFO

SENDER_ENABLED=true
SENDER_POLL_INTERVAL_SECONDS=5
SENDER_MAX_BATCH_SIZE=50
SENDER_DEFAULT_RETRY_MAX=3
SENDER_DEFAULT_BACKOFF_MS=1000
SENDER_STUCK_TIMEOUT_SECONDS=300

# SOAP
MOSSOS_WSDL_URL=https://example.invalid/matricules.wsdl
MOSSOS_ENDPOINT_URL=https://example.invalid/matr-ws
MOSSOS_TIMEOUT=5.0
SOAP_DEBUG=0
```

Descripción detallada de cada variable en [`docs/configuration.md`](docs/configuration.md).

## 5️⃣ Estructura de carpetas relevantes
- `app/api`: API FastAPI (`/health`, `/ingest/lectorvision`).
- `app/ingest`: servicio TCP de ingesta.
- `app/sender`: worker de envío SOAP.
- `app/admin` + `app/scripts`: utilidades CLI y scripts interactivos.
- `alembic/`: migraciones.
- `docs/`: documentación técnica.
- `data/images/`: almacenamiento recomendado para imágenes (configurable con `IMAGES_BASE_DIR`).

## 6️⃣ Operación básica
- **Logs:** se controlan con `LOG_LEVEL` (por defecto `INFO`).
- **Healthcheck API:** `GET /health` devuelve métricas mínimas (`pending`, `failed`, `dead`, `total_readings`).
- **Imágenes:** se almacenan como rutas relativas en BD y se resuelven contra `IMAGES_BASE_DIR`.
- **Reintentos:** el sender aplica backoff con `SENDER_DEFAULT_BACKOFF_MS` o con los valores definidos en cada endpoint.

## 7️⃣ Lector Vision (JSON → XML Tattile)
Endpoint HTTP:
- Ruta: `POST /ingest/lectorvision`
- Respuesta: `202 Accepted` si se encola la lectura.
- Campos obligatorios: `Plate`, `TimeStamp`, `SerialNumber` (o `IdDevice`).

Ejemplo de `curl`:
```bash
curl -X POST http://localhost:33335/ingest/lectorvision \
  -H 'Content-Type: application/json' \
  -d '{
    "Plate": "1234ABC",
    "TimeStamp": "2026/01/23 09:25:57.000",
    "SerialNumber": "LV-01",
    "Fiability": 87,
    "LaneNumber": 2,
    "LaneName": "Carril 2",
    "Direction": "IN",
    "PlateCoord": [10, 20, 110, 220],
    "Country": 724
  }'
```

> La lectura se acepta solo si la cámara existe en la BD (`cameras.serial_number`).

## 8️⃣ Troubleshooting rápido
- **No se reciben lecturas TCP:** revisa `TRANSIT_PORT`, firewall y que la cámara esté registrada.
- **Errores de SOAP/WS-Security:** valida que `key.pem` y `client.pem` correspondan y que `MOSSOS_ENDPOINT_URL` sea correcto.
- **Lecturas sin imagen OCR:** el sender descarta la lectura (`DEAD`).
- **Stuck en SENDING:** se recuperan automáticamente tras `SENDER_STUCK_TIMEOUT_SECONDS`.

## 9️⃣ Roadmap corto
- Validar y persistir atributos extra del vehículo (marca, color, tipo) para incluirlos en el SOAP.
- Añadir métricas estructuradas (Prometheus) para estado de cola y último envío por cámara.

---
Documentación técnica adicional:
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/configuration.md`](docs/configuration.md)
- [`docs/data-formats.md`](docs/data-formats.md)
- [`docs/soap-lectio.md`](docs/soap-lectio.md)
- [`docs/ops.md`](docs/ops.md)
