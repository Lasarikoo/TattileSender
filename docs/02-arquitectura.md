# Arquitectura inicial

## Componentes principales
- **Ingest Service**: escucha tráfico Tattile (TCP/UDP), parsea el XML recibido y
  encola la lectura normalizada en la base de datos.
- **Sender Worker**: consume la cola de mensajes pendientes, determina el
  certificado y endpoint apropiado resolviendo cámara → municipio → certificado
  (y endpoint) y envía la lectura mediante SOAP a Mossos.
- **Admin API (FastAPI)**: endpoints mínimos para administración (gestión de
  cámaras, certificados y consulta de estados) y métricas básicas.
- **Base de datos PostgreSQL**: almacena cámaras, municipios, certificados,
  endpoints, lecturas normalizadas y la cola de mensajes.

## Flujo general
- Tattile (XML) → Ingest → DB (`alpr_readings` + `messages_queue`) → Sender
  Worker → resolución cámara → municipio → certificado + endpoint → Mossos →
  borrado de `alpr_readings`/`messages_queue` e imágenes en éxito.
- En caso de fallo de envío, el mensaje permanece en cola y se reintenta con
  políticas configurables.

### Sender Worker
- Para cada mensaje en cola, obtiene la lectura y la cámara asociada.
- A través de la cámara resuelve el municipio y, con él, el certificado y el
  endpoint (o el endpoint específico de la cámara si lo hay).
- Con estos datos firma y envía la petición SOAP a Mossos.
- Si el envío se confirma, elimina el mensaje, la lectura y cualquier fichero de
  imagen asociado, dejando opcionalmente un log de auditoría sin matrícula.

## Consideraciones de despliegue
- Primera iteración orientada a servicios Python gestionados con systemd en VPS
  Ubuntu 22.04.
- Alternativamente se podrán ejecutar mediante Docker usando `docker-compose`
  para aislar base de datos y API.
- No se prevé orquestación compleja (Kubernetes) en etapas tempranas.

### Seguridad y privacidad
- Seguridad: proteger certificados, credenciales y accesos; uso de HTTPS y
  cifrado en reposo cuando aplique. La política de retención y eliminación
  temporal de datos se detalla en `docs/01-requisitos.md` y guía las purgas
  tras envíos exitosos.

## Estado de implementación en Fase 1
- El Ingest Service ya está implementado y escucha XML Tattile por TCP,
  normaliza la carga y la persiste.
- Las lecturas se almacenan en `alpr_readings` y se crean entradas en
  `messages_queue` con estado `PENDING`.
- El envío a Mossos y el Sender Worker real se abordarán en la Fase 2,
  incluyendo la eliminación de datos una vez completado el envío.
