# TattileSender

Servicio backend en Python diseñado para recibir lecturas ALPR de cámaras Tattile en formato XML y reenviarlas al endpoint SOAP de Mossos d'Esquadra usando certificados PFX específicos por cámara o municipio.

## Despliegue en servidor Ubuntu (producción sencilla)
El flujo recomendado asume un VPS Ubuntu protegido, sin contenedores para la aplicación principal.

### 1. Instalar dependencias del sistema
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip postgresql postgresql-contrib git
```

### 2. Clonar el repositorio privado
```bash
cd /opt
git clone <URL_PRIVADA_REPO> TattileSender
cd TattileSender
```

### 3. Crear y activar entorno virtual en el VPS
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Crear base de datos y usuario en PostgreSQL para producción
```bash
sudo -u postgres psql
CREATE USER tattile_prod WITH PASSWORD 'cambia_est0';
CREATE DATABASE tattile_sender_prod OWNER tattile_prod;
GRANT ALL PRIVILEGES ON DATABASE tattile_sender_prod TO tattile_prod;
\q
```

### 5. Configurar el archivo `.env`
Copia la plantilla y ajusta valores reales:
```bash
cp .env.example .env
```
Edita `.env` con las credenciales creadas en el paso anterior, rutas seguras para los certificados y define `IMAGES_DIR` en una ubicación con espacio suficiente para binarios temporales (por defecto `data/images`).

### 6. Ejecutar migraciones Alembic usando SIEMPRE el venv
Activa el entorno virtual y lanza las migraciones:
```bash
source .venv/bin/activate  # si aún no está activado
python -m alembic upgrade head
```
Asegúrate de que `which alembic` apunte a `.venv/bin/alembic` y no a `/usr/bin/alembic`.

### 7. Lanzar la API en modo producción simple
```bash
source .venv/bin/activate
uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```
Para producción final, conviene situar Uvicorn detrás de un proxy inverso (Nginx) o definir un servicio `systemd`, aunque no es obligatorio para la puesta en marcha inicial.

### 8. Lanzar el Ingest Service en el VPS
```bash
source .venv/bin/activate
python -m app.ingest.main
```
El servicio escucha en el puerto definido por `TRANSIT_PORT` en `.env`, que debe coincidir con el configurado en las cámaras Tattile.

### 9. Lanzar el Sender Worker (Fase 2)
```bash
source .venv/bin/activate
python -m app.sender.main
```
El worker consulta la tabla `messages_queue` y envía lecturas al endpoint SOAP
configurado por municipio o cámara. Respeta los parámetros de reintentos
definidos en BD (`retry_max`, `retry_backoff_ms`) o, en su defecto, las
variables de entorno `SENDER_*`.

Ejemplo de unidad `systemd` mínima:
```
[Unit]
Description=TattileSender - Worker Mossos
After=network.target

[Service]
WorkingDirectory=/opt/TattileSender
EnvironmentFile=/opt/TattileSender/.env
ExecStart=/opt/TattileSender/.venv/bin/python -m app.sender.main
Restart=always

[Install]
WantedBy=multi-user.target
```
Recuerda ejecutar `daemon-reload` y `enable --now` tras crear la unidad.

### 10. Pruebas básicas en producción
- Probar la API:
  ```bash
  curl http://127.0.0.1:8000/health
  ```
- Simular una lectura desde el propio servidor (ajusta `<TRANSIT_PORT>` con el valor real):
  ```bash
  nc 127.0.0.1 <TRANSIT_PORT> << 'EOF'
  <?xml version="1.0" encoding="UTF-8"?>
  <root>
    <!-- XML de ejemplo aquí -->
  </root>
  EOF
  ```
- Verificar datos en PostgreSQL:
  ```bash
  psql -h localhost -U tattile_prod -d tattile_sender_prod
  SELECT * FROM alpr_readings ORDER BY id DESC LIMIT 5;
  SELECT * FROM messages_queue ORDER BY id DESC LIMIT 5;
  ```

## Uso de Docker (opcional / desarrollo)
`docker-compose.yml` sirve como ayuda para levantar rápidamente PostgreSQL en un entorno de pruebas. No es el camino principal para producción.

Para iniciar solo la base de datos con Docker Compose v1 (comando clásico):
```bash
docker-compose up -d db
```
Si tu instalación soporta el comando moderno `docker compose`, también funcionará, pero la compatibilidad con `docker-compose` es la opción segura en la mayoría de VPS.

Cuando uses Docker, `DB_HOST` puede ser `db` si ejecutas procesos en contenedores y `localhost` si accedes desde el host. La API y el Ingest Service se ejecutan desde el entorno virtual de Python según las instrucciones anteriores.

## Estructura del proyecto
- `app/`: código fuente (configuración, API, servicios de ingesta y envío).
- `alembic/`: migraciones de base de datos.
- `docs/`: documentación funcional, técnica y de despliegue.
- `legacy/`: artefactos heredados (binarios, capturas, logs) **sin** incluir certificados.
- `.env.example`: plantilla de variables de entorno orientada a producción.
- `docker-compose.yml`: apoyo opcional para disponer de PostgreSQL en pruebas.

## Panel de ajustes y certificados
- El directorio de certificados se define con `CERTS_DIR` en `.env` (por defecto `/etc/tattile_sender/certs`).
- Copia los ficheros de certificados al servidor (por ejemplo con `scp`) dentro de ese directorio.
- Convierte previamente los `.pfx` entregados por Mossos a PEM (cert + clave) siguiendo las notas en `docs/mossos/README.md`.
- Para registrar municipios, cámaras, endpoints y certificados en BD usa:
  ```bash
  ./ajustes.sh
  ```
  y sigue las opciones de menú.

## Notas
- No almacenes certificados `.pfx` ni contraseñas reales en el repositorio.
- En producción se recomienda gestionar variables de entorno mediante el sistema o un servicio de secretos.
- Para automatizar la puesta en marcha se pueden crear unidades `systemd` que activen el entorno virtual y arranquen Uvicorn y el servicio de ingesta.

## Gestión de imágenes ALPR
- Las cámaras pueden adjuntar imágenes base64 de matrícula (`IMAGE_OCR` → `imgMatricula`) y contexto (`IMAGE_CTX` → `imgContext`).
- El servicio de ingesta decodifica y guarda las imágenes en `IMAGES_DIR` (por defecto `data/images`), organizado por cámara y fecha: `<IMAGES_DIR>/<DEVICE_SN>/YYYY/MM/DD/<timestamp>_plate-<PLATE>_{ocr|ctx}.jpg`.
- En la tabla `alpr_readings` se almacenan:
  - `has_image_ocr` / `image_ocr_path`
  - `has_image_ctx` / `image_ctx_path`
- El sender **solo envía** mensajes con imágenes válidas (rutas presentes en disco). Las lecturas sin imágenes o con rutas rotas se marcan como `DEAD` y no se reintentan.
- Tras recibir `codiRetorn=1` de Mossos se eliminan la entrada en `messages_queue`, la lectura en `alpr_readings` y los ficheros de imagen asociados.
- En despliegues productivos usa un `IMAGES_DIR` absoluto (p. ej. `/var/lib/tattilesender/images`) y garantiza permisos de escritura del usuario que ejecuta ingest y sender.
