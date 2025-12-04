# Arquitectura inicial

## Componentes principales
- **Ingest Service**: escucha tráfico Tattile (TCP/UDP), parsea el XML recibido y
  encola la lectura normalizada en la base de datos.
- **Sender Worker**: consume la cola de mensajes pendientes, determina el
  certificado y endpoint apropiado y envía la lectura mediante SOAP a Mossos.
- **Admin API (FastAPI)**: endpoints mínimos para administración (gestión de
  cámaras, certificados y consulta de estados) y métricas básicas.
- **Base de datos PostgreSQL**: almacena cámaras, certificados, endpoints,
  lecturas normalizadas y la cola de mensajes.

## Flujo general
- Tattile (XML) → Ingest → DB (cola de mensajes) → Sender Worker → Mossos.
- En caso de fallo de envío, el mensaje permanece en cola y se reintenta con
  políticas configurables.

## Consideraciones de despliegue
- Primera iteración orientada a servicios Python gestionados con systemd en VPS
  Ubuntu 22.04.
- Alternativamente se podrán ejecutar mediante Docker usando `docker-compose`
  para aislar base de datos y API.
- No se prevé orquestación compleja (Kubernetes) en etapas tempranas.
