# TattileSender

Servicio backend en Python diseñado para recibir lecturas ALPR de cámaras
Tattile en formato XML y reenviarlas al endpoint SOAP de Mossos d'Esquadra usando
certificados PFX específicos por cámara o municipio.

## Estado actual
Fase 0: solo scaffolding, documentación y configuración inicial. La lógica de
negocio (ingesta, cola, envíos SOAP) se implementará en fases posteriores.

## Tecnologías previstas
- Python 3.11+
- FastAPI para la API HTTP de administración
- SQLAlchemy + Alembic sobre PostgreSQL
- Worker/servicio de ingesta y sender en procesos Python
- Gestión de configuración por variables de entorno y `.env`

## Estructura del proyecto
- `app/`: código fuente (configuración, API, servicios de ingesta y envío).
- `docs/`: documentación funcional, técnica y de legado.
- `legacy/`: artefactos heredados (binarios, capturas, logs) **sin** incluir
  certificados.
- `.env.example`: plantilla de variables de entorno.
- `docker-compose.yml`: base para levantar PostgreSQL y la API en el futuro.

## Puesta en marcha rápida (desarrollo)
1. Crear y activar entorno virtual (ejemplo con `venv`):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Copiar `.env.example` a `.env` y ajustar valores según entorno local.
4. (Opcional) Lanzar la API de prueba con FastAPI/uvicorn:
   ```bash
   uvicorn app.api.main:app --reload
   ```
   El endpoint `/health` responderá con el estado básico del servicio.

## Notas
- No se deben almacenar certificados `.pfx` ni contraseñas en el repositorio.
- En producción se recomienda gestionar variables mediante el entorno del
  sistema o servicios de secretos.
