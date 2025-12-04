# Requisitos

## Requisitos funcionales
- Recepción de lecturas ALPR desde cámaras Tattile por TCP/UDP en puerto
  configurable (ej. 33334).
- Normalización de cada lectura a un modelo interno `ALPRReading`.
- Encolado persistente de las lecturas para garantizar entrega diferida.
- Reenvío de las lecturas al endpoint de Mossos mediante SOAP sobre HTTPS.
- Firma de las peticiones SOAP con certificados PFX, seleccionados según la
  cámara/municipio.
- Soporte para múltiples cámaras y certificados independientes.
- Registro de logs y estados de cada lectura (`PENDING`, `SENT`, `FAILED`, etc.).

## Requisitos no funcionales
- Robustez: no perder lecturas si el endpoint de Mossos está caído; soportar
  reintentos con backoff configurable.
- Escalabilidad: capacidad objetivo de 100–200 cámaras concurrentes con consumo
  eficiente de recursos.
- Seguridad: protección de certificados y credenciales; mínimo acceso SSH
  restringido y almacenamiento de secretos fuera del repo.
- Observabilidad: logs estructurados y métricas básicas (conteo de lecturas
  recibidas, encoladas, enviadas, fallidas).
- Despliegue: orientado a VPS Ubuntu 22.04, con servicios gestionados por
  systemd o contenedores simples.
