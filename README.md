# TattileSender

Servicio backend en Python diseñado para recibir lecturas ALPR de cámaras Tattile en formato XML y reenviarlas al endpoint SOAP de Mossos d'Esquadra usando certificados PFX específicos por cámara o municipio.

## Requisitos previos
- Python 3.11 o superior.
- PostgreSQL 15 o superior (puede ser local o vía Docker).
- `pip` junto a `virtualenv`/`pipenv` para gestionar entornos.
- Opcional: Docker y Docker Compose para levantar servicios rápidamente.

## Configuración del entorno (.env)
En la raíz existe un archivo `.env.example` con las variables necesarias. Cópialo y ajústalo según tu entorno:

```bash
cp .env.example .env
```

Variables principales:
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`: datos de conexión a PostgreSQL.
- `CERTS_DIR`: ruta donde se almacenan los certificados PFX en el servidor.
- `TRANSIT_PORT`: puerto en el que el servicio de ingesta escuchará las lecturas Tattile.
- `APP_ENV`: entorno de ejecución (`dev`, `prod`, etc.).

Valores habituales para desarrollo local:
- `DB_HOST=localhost`
- `DB_PORT=5432`
- `DB_NAME=tattile_sender`
- `DB_USER=tattile`
- `DB_PASSWORD=changeme`

## Instalación de dependencias
1. Crear y activar el entorno virtual:

   ```bash
   python -m venv .venv
   source .venv/bin/activate       # Linux/macOS
   .venv\Scripts\activate         # Windows
   ```

2. Instalar las dependencias del proyecto:

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

## Configurar PostgreSQL (local)
Ejemplo básico creando usuario y base de datos que coincidan con el `.env`:

```bash
sudo -u postgres psql
CREATE USER tattile WITH PASSWORD 'changeme';
CREATE DATABASE tattile_sender OWNER tattile;
GRANT ALL PRIVILEGES ON DATABASE tattile_sender TO tattile;
```

Confirma que los valores utilizados son los mismos definidos en tus variables de entorno.

## Usando Docker para PostgreSQL
El proyecto incluye un `docker-compose.yml` con un servicio `db` de PostgreSQL. Para levantar solo la base de datos:

```bash
docker compose up -d db
```

Cuando usas Docker Compose, `DB_HOST` puede ser `db` (nombre del servicio) si los procesos se ejecutan dentro de los contenedores, o `localhost` si accedes desde el host.

## Migraciones de base de datos (Alembic)
Ejecuta las migraciones antes de iniciar los servicios para crear las tablas iniciales (`municipalities`, `certificates`, `endpoints`, `cameras`, `alpr_readings`, `messages_queue`, etc.):

```bash
alembic upgrade head
```

## Lanzar la API (FastAPI)
Arranca la API en modo desarrollo con Uvicorn:

```bash
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

Prueba el endpoint de salud:

```bash
curl http://127.0.0.1:8000/health
```

La ruta `/health` devuelve el estado general, mensajes pendientes en la cola y el total de lecturas almacenadas.

## Lanzar el Ingest Service
El servicio de ingesta escucha el puerto Tattile definido en `TRANSIT_PORT`, recibe XML de lecturas, los parsea y los guarda en la base de datos.

Inícialo con:

```bash
python -m app.ingest.main
```

`TRANSIT_PORT` determina el puerto de escucha. Para simular una lectura vía `netcat`:

```bash
nc 127.0.0.1 33334 << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<root>
  <!-- XML de ejemplo aquí -->
</root>
EOF
```

## Probar el funcionamiento (local)
Secuencia sugerida:
1. Levantar PostgreSQL (local o con Docker Compose).
2. Ejecutar `alembic upgrade head` para crear el esquema.
3. Arrancar la API con `uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000`.
4. Arrancar el Ingest Service con `python -m app.ingest.main`.
5. Enviar un XML de prueba usando `nc` contra el puerto configurado.
6. Consultar la base de datos, por ejemplo:
   ```sql
   SELECT * FROM alpr_readings LIMIT 5;
   SELECT * FROM messages_queue LIMIT 5;
   ```
7. Llamar a `/health` para verificar `pending_messages` y `total_readings`.

## Despliegue básico en un VPS Ubuntu (resumen)
- Instalar Python 3, PostgreSQL, Git y dependencias del sistema.
- Clonar el repositorio y crear el archivo `.env` a partir de `.env.example` con valores reales.
- Crear el usuario y la base de datos en PostgreSQL para el proyecto.
- Instalar dependencias con `pip install -r requirements.txt`.
- Ejecutar las migraciones con `alembic upgrade head`.
- Arrancar la API y el Ingest Service inicialmente desde terminal (o `tmux/screen`).
- Configurar la cámara Tattile para enviar lecturas al puerto del VPS.
- En fases posteriores se definirán servicios `systemd` para automatizar API e ingesta.

## Estructura del proyecto
- `app/`: código fuente (configuración, API, servicios de ingesta y envío).
- `docs/`: documentación funcional, técnica y de despliegue.
- `legacy/`: artefactos heredados (binarios, capturas, logs) **sin** incluir certificados.
- `.env.example`: plantilla de variables de entorno.
- `docker-compose.yml`: base para levantar PostgreSQL y servir de referencia futura para API/ingesta.

## Notas
- No se deben almacenar certificados `.pfx` ni contraseñas reales en el repositorio.
- En producción se recomienda gestionar variables mediante el entorno del sistema o servicios de secretos.
