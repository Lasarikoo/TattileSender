# Operación técnica de TattileSender

Este documento amplía los aspectos operativos descritos en el README.

## Componentes y servicios
- **API (tattile-api.service)**: FastAPI/UVicorn en el puerto 8000, usa el `.env` para conectarse a PostgreSQL.
- **Ingest (tattile-ingest.service)**: socket TCP en `TRANSIT_PORT`, parsea XML Tattile y almacena lecturas e imágenes.
- **Sender (tattile-sender.service)**: procesa `messages_queue`, firma SOAP con WS-Security y elimina datos cuando `codiRetorn=1`.

Todos los servicios se ejecutan en el entorno virtual `.venv` creado por `setup.sh`.

## Puertos y firewall
- Abra `TRANSIT_PORT` solo para las IP de las cámaras Tattile.
- Mantenga la API (8000) accesible solo desde la red interna o un proxy inverso.
- PostgreSQL debe aceptar conexiones locales (`127.0.0.1`).

## Certificados y WS-Security
- Coloque los `.pfx/.p12` en `CERTS_DIR` y use `./ajustes.sh` → «Descomprimir certificado PFX y asignar a municipio».
- El asistente extrae `key.pem` (clave privada) y `privpub.pem` (certificado público) y los asocia al municipio elegido.
- El sender inyecta ambos ficheros en zeep, generando la cabecera WS-Security Timestamp + BinarySignature.

## Ciclo de vida de datos
1. **Recepción**: Ingest valida cámara registrada, guarda imágenes y crea lectura + mensaje `PENDING`.
2. **Envío**: Sender valida imágenes, selecciona certificado y endpoint; si no existen pasa a `DEAD`.
3. **Reintentos**: controlados por `SENDER_DEFAULT_RETRY_MAX`/`SENDER_DEFAULT_BACKOFF_MS` o por valores del endpoint.
4. **Éxito**: `codiRetorn` en `SUCCESS_CODES` → se borra la lectura, imágenes y mensaje.
5. **Errores permanentes**: faltan imágenes, certificado incompleto, endpoint vacío o reintentos agotados → estado `DEAD`.

## Estructura de imágenes
- Directorio base: `IMAGES_BASE_DIR` (recomendado `/data/images`).
- Ruta relativa en BD: `<SERIE_CAMARA>/YYYY/MM/DD/<timestamp>_plate-<MAT>_{ocr|ctx}.jpg`.
- Uso en sender: las rutas relativas se resuelven contra el directorio base; rutas antiguas `data/images/…` siguen siendo válidas.

## Monitoreo y soporte
- Logs en tiempo real: `journalctl -fu tattile-api.service`, `journalctl -fu tattile-ingest.service`, `journalctl -fu tattile-sender.service`.
- Métricas rápidas: usar `./ajustes.sh` → «Utilidades del sistema» para CPU/RAM/red y conteo de tablas.
- Reinicios controlados: `systemctl restart tattile-api tattile-ingest tattile-sender`.
