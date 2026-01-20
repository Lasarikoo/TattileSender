# TattileSender

Plataforma backend en Python para recibir lecturas ALPR de cámaras Tattile, almacenarlas con sus imágenes y reenviarlas con SOAP y WS-Security al endpoint de Mossos d'Esquadra.

## 1️⃣ Introducción
**¿Qué es?** Sistema compuesto por una API, un servicio de ingesta TCP y un worker de envío que procesa lecturas ALPR.

**Problema que soluciona**: centraliza la recepción de XML Tattile, persiste lecturas + imágenes y las entrega firmadas mediante certificados municipales al servicio SOAP de Mossos, con control de reintentos, limpieza y trazabilidad.

**Flujo completo**
1. Las cámaras Tattile envían XML + imágenes en Base64 al servicio **Ingest**.
2. **Ingest** decodifica el XML, guarda las imágenes en disco, registra la lectura en PostgreSQL y añade un mensaje a la cola `messages_queue`.
3. **Sender** lee la cola, carga el certificado del municipio, genera la petición SOAP con firma WS-Security y la envía a Mossos.
4. Mossos responde con `codiRetorn`.
   - Si `codiRetorn=1`: limpieza automática (se eliminan lectura, imágenes y mensaje de cola).
   - Si hay error: se reintenta según configuración; si no hay imagen OCR disponible el mensaje pasa a `DEAD` sin reintentos.

## 2️⃣ Requisitos del servidor
- Ubuntu 22.04 o 24.04 (compatible con 20.04 de forma opcional).
- Python 3.12.
- PostgreSQL accesible localmente.
- Certificados municipales en **PFX/P12 convertidos a PEM** (par `key.pem` + `privpub.pem`).
- Puertos:
  - API HTTP: **8000**.
  - Ingest: definido en `.env` con `TRANSIT_PORT`.
  - PostgreSQL accesible en localhost.

## 3️⃣ Instalación del proyecto
### 3.1 Clonar repositorio (ruta obligatoria)
Siempre clona en `/opt/TattileSender/`:
```bash
cd /opt
git clone <URL_PRIVADO_REPO> TattileSender
cd TattileSender
```

### 3.2 Preparar entorno
1. Copia la plantilla de variables: `cp .env.example .env`.
2. Revisa la sección de configuración y ajusta `.env` antes de ejecutar scripts.

## 4️⃣ Configuración del archivo .env
Variables principales:
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`: credenciales PostgreSQL.
- `DB_HOST`, `DB_PORT`: normalmente `localhost` y `5432`.
- `TRANSIT_PORT`: puerto TCP donde escucha Ingest (ej. `33334`).
- `IMAGES_BASE_DIR`: directorio base para imágenes (recomendado `/data/images`).
- `CERTS_DIR`: ruta de certificados PEM (por defecto `/etc/tattile_sender/certs`).
- `LOG_LEVEL`: `INFO` o `DEBUG`.
- Opciones `SENDER_*`: controlan worker de envío (`SENDER_ENABLED`, `SENDER_POLL_INTERVAL_SECONDS`, `SENDER_MAX_BATCH_SIZE`, `SENDER_DEFAULT_RETRY_MAX`, `SENDER_DEFAULT_BACKOFF_MS`).
  - `SENDER_STUCK_TIMEOUT_SECONDS`: tiempo máximo en `SENDING` antes de reintentar automáticamente (por defecto 300s).

Ejemplo completo:
```env
APP_ENV=prod
DB_HOST=localhost
DB_PORT=5432
DB_NAME=tattile_sender_prod
DB_USER=tattile_prod
DB_PASSWORD=pon_aqui_la_password
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
```

## 5️⃣ Ejecución de `setup.sh`
`./setup.sh` automatiza la puesta en marcha (requiere sudo):
- Detecta instalaciones existentes (venv, DB, servicios systemd) antes de crear nada.
- Instala dependencias del sistema.
- Crea o reutiliza la base de datos PostgreSQL definida en `.env` y asigna permisos.
- Instala dependencias Python en `.venv` y ejecuta migraciones Alembic.
- Genera y habilita los servicios `systemd`:
  - `tattile-api.service`
  - `tattile-ingest.service`
  - `tattile-sender.service`
- Arranca los servicios y muestra su estado. Comprueba que todo está activo con:
```bash
systemctl status tattile-api.service
```

## 6️⃣ Estructura del proyecto
- `app/api`: API FastAPI/UVicorn.
- `app/ingest`: servicio TCP que recibe XML + imágenes de cámaras.
- `app/sender`: worker que consume la cola y envía a Mossos con WS-Security.
- `data/images`: carpeta recomendada (montaje) para imágenes ALPR.
- `etc/tattile_sender/certs`: ubicación recomendada de certificados PEM.
- `ajustes.sh`: panel interactivo de administración.
- `setup.sh`: instalación y despliegue automatizados en servidor.
- `alembic/`: migraciones de base de datos.
- `docs/`: documentación adicional.

## 7️⃣ Uso del panel de administración `ajustes.sh`
Ejecuta `./ajustes.sh` (con `.venv` presente) y usa los menús interactivos:

### Añadir datos
- **Añadir municipios**.
- **Añadir cámaras** (por número de serie).
- **Añadir endpoints** (URL SOAP de cada municipio).
- **Descomprimir certificado PFX y asignar a municipio** (crea `key.pem` + `privpub.pem` y lo asocia).

### Asignar relaciones
- Cámara → municipio.
- Municipio → endpoint.
- Municipio → certificado.
- Cámara → certificado o endpoint (para casos específicos).

### Eliminar datos
- Cámaras, municipios, endpoints y certificados (con confirmación y opción de forzado).
- Limpieza total de lecturas (incluye cola e imágenes).
- Limpieza de cola.
- Limpieza de imágenes en disco.

### Modificar datos
- Editar municipios, cámaras, endpoints y certificados existentes.

### Utilidades del sistema
- Ver uso del sistema en tiempo real (CPU, RAM, red, top procesos).
- Ver estadísticas de base de datos (conteos de lecturas, cola, cámaras, municipios).
- Reiniciar servicios `tattile-api`, `tattile-ingest`, `tattile-sender`.
- Ver logs en tiempo real seleccionando uno de los servicios anteriores.

## 8️⃣ Funcionamiento de las imágenes
- Las cámaras envían imágenes Base64 (OCR y contexto) dentro del XML.
- Se guardan en `/data/images/<CAMERA_SN>/YYYY/MM/DD/<timestamp>_plate-<PLATE>_{ocr|ctx}.jpg`.
- En BD se almacena la ruta **relativa** al directorio base y los flags `has_image_ocr` / `has_image_ctx`.
- El sender resuelve rutas relativas contra `IMAGES_BASE_DIR` y no envía lecturas sin imagen OCR presente.
- Cuando Mossos devuelve `codiRetorn=1`, se eliminan lectura, imágenes y mensaje de cola asociados.

## 9️⃣ Funcionamiento del servicio de ingesta
- Escucha en `TRANSIT_PORT` (TCP) configurado en `.env`.
- Espera XML con etiquetas Tattile estándar y campos `IMAGE_OCR`/`IMAGE_CTX` en Base64.
- Ejemplo de log: `[INGEST] Lectura recibida (3060LFW) de (2001008851)`.

## 🔟 Funcionamiento del sender
- Lee mensajes `PENDING`/`FAILED` de la cola.
- Busca certificado asignado al municipio (o cámara) y endpoint SOAP.
- Construye SOAP con **zeep**, firma WS-Security con `key.pem` + `privpub.pem` y adjunta imágenes.
- Verifica existencia de imágenes; si falta la OCR el mensaje pasa a `DEAD` y no se reintenta.
- Reintentos con backoff según `SENDER_*` o ajustes de endpoint.
- Ejemplos de logs:
  - `[SENDER] Enviando lectura (6080JYH)`
  - `[SENDER] Reintento de lectura (6080JYH)`
  - `[SENDER] Lectura (6080JYH) enviada correctamente a Mossos`

## 1️⃣1️⃣ Cómo añadir una cámara real al sistema
1. Añadir municipio con `./ajustes.sh` → «Añadir municipios».
2. Añadir certificado municipal: coloca el `.pfx` en `CERTS_DIR`, usa «Descomprimir certificado PFX y asignar a municipio» para generar `key.pem` + `privpub.pem` y vincularlos automáticamente.
3. Añadir endpoint SOAP del municipio.
4. Añadir cámara (número de serie Tattile) y relacionarla con el municipio.
5. Configurar la cámara Tattile apuntando al servidor (`IP` del servidor, puerto `TRANSIT_PORT`).
6. Probar ingesta desde el menú (simulación) o con la propia cámara.
7. Verificar que el sender entrega a Mossos y recibe `codiRetorn=1`.

## 1️⃣2️⃣ Ejemplo de lectura completa funcionando
1. XML recibido en `TRANSIT_PORT` con `IMAGE_OCR` y `IMAGE_CTX` Base64.
2. Imágenes decodificadas y guardadas en `/data/images/<SN>/YYYY/MM/DD/...jpg`.
3. Inserción en `alpr_readings` con rutas relativas y flags `has_image_*`.
4. Creación del mensaje en `messages_queue` con estado `PENDING`.
5. Sender toma el mensaje, valida imágenes, firma SOAP y lo envía.
6. Mossos responde `codiRetorn=1` → log de éxito.
7. Limpieza automática: se borra la lectura, las imágenes y la entrada de cola.

## 1️⃣3️⃣ Troubleshooting
- **Permisos en `/data/images`**: asegúrate de que el usuario de servicio puede escribir; corrige con `chown -R root:root /data/images` o permisos adecuados.
- **Systemd no arranca**: revisa `.env`, ejecuta `systemctl status tattile-api tattile-ingest tattile-sender` y `journalctl -fu tattile-api.service`.
- **Certificado mal asignado**: verifica rutas en `CERTS_DIR`, re-extrae con `ajustes.sh` y confirma que `key.pem` y `privpub.pem` existen.
- **Error WS-Security**: habilita `LOG_LEVEL=DEBUG` y revisa `journalctl -fu tattile-sender.service`; comprueba que la pareja cert/clave corresponda.
- **No se reciben lecturas**: confirma puerto `TRANSIT_PORT`, firewall abierto y que la cámara esté registrada en BD.
- Logs útiles:
  - `journalctl -fu tattile-ingest.service`
  - `journalctl -fu tattile-sender.service`
  - `journalctl -fu tattile-api.service`

---
Para detalles técnicos ampliados revisa `docs/`.
