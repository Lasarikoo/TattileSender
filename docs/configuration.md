# Configuración

TattileSender usa `pydantic.BaseSettings` para leer variables desde entorno y, opcionalmente, desde un fichero `.env`. La prioridad es: argumentos directos → variables de entorno → `.env`.

## Variables de entorno

| Variable | Tipo | Default | Descripción |
| --- | --- | --- | --- |
| `APP_ENV` | string | `dev` | Entorno lógico (dev/prod). |
| `DB_HOST` | string | `localhost` | Host de PostgreSQL. |
| `DB_PORT` | int | `5432` | Puerto de PostgreSQL. |
| `DB_NAME` | string | `tattile_sender` | Nombre de la BD. |
| `DB_USER` | string | `tattile` | Usuario DB. |
| `DB_PASSWORD` | string | `changeme` | Password DB (placeholder). |
| `CERTS_DIR` | string | `/etc/tattile_sender/certs` | Directorio base para certificados (usado por scripts). |
| `TRANSIT_PORT` | int | `33334` | Puerto TCP del servicio de ingesta Tattile. |
| `IMAGES_BASE_DIR` / `IMAGES_DIR` | string | `/data/images` | Directorio base de imágenes. |
| `SENDER_ENABLED` | bool | `true` | Activa o desactiva el worker. |
| `SENDER_POLL_INTERVAL_SECONDS` | int | `5` | Pausa entre iteraciones sin trabajo. |
| `SENDER_MAX_BATCH_SIZE` | int | `50` | Límite de mensajes procesados por iteración. |
| `SENDER_DEFAULT_RETRY_MAX` | int | `3` | Reintentos por defecto si el endpoint no define `retry_max`. |
| `SENDER_DEFAULT_BACKOFF_MS` | int | `1000` | Backoff en ms si el endpoint no define `retry_backoff_ms`. |
| `SENDER_STUCK_TIMEOUT_SECONDS` | int | `300` | Tiempo máximo en estado `SENDING` antes de marcar como `FAILED`. |
| `MOSSOS_WSDL_URL` | string | (definido en código) | URL del WSDL de Mossos. Sustitúyela por el endpoint oficial. |
| `MOSSOS_ENDPOINT_URL` | string | `None` | Endpoint SOAP por defecto (fallback cuando no hay endpoint en BD). |
| `MOSSOS_TIMEOUT` | float | `5.0` | Timeout en segundos para SOAP. |
| `LOG_LEVEL` | string | `INFO` | Nivel de log (INFO/DEBUG). |
| `SOAP_DEBUG` | string | `0` | Si vale `1`, imprime el envelope SOAP en logs. |

> Nota: `CERTS_DIR`, `IMAGES_DIR` y `IMAGES_BASE_DIR` son aliases; el código usa `images_dir` y `certs_dir` internamente.

## Ejemplo seguro de `.env`
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

MOSSOS_WSDL_URL=https://example.invalid/matricules.wsdl
MOSSOS_ENDPOINT_URL=https://example.invalid/matr-ws
MOSSOS_TIMEOUT=5.0
SOAP_DEBUG=0
```

## Notas de seguridad
- No guardes `.env` con secretos en el repo.
- Los ficheros `key.pem`, `client.pem`, `.pfx` deben vivir fuera del repo y con permisos restringidos.
- El sender lee rutas de certificados desde la base de datos (`Certificate.path`/`client_cert_path` y `key_path`).
