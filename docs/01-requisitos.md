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
- El sistema debe ser multi-municipio: cada cámara se asocia a un municipio y
  cada municipio puede tener su certificado PFX (y configuración de endpoint)
  para Mossos, permitiendo compartir certificado entre varias cámaras a través
  de su municipio.
- Cada lectura ALPR se vincula a una cámara y, por extensión, al municipio y
  certificado que se deben usar en el envío a Mossos en el momento de construir
  la petición.
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

### Retención y eliminación de datos
- Las lecturas (matrículas, metadatos, XML e imágenes) se guardarán solo el
  tiempo estrictamente necesario para completar el envío al endpoint de Mossos.
- Tras un envío exitoso, el sistema eliminará la lectura, sus fotos y las
  entradas de cola asociadas.
- Opcionalmente se podrá conservar un registro de auditoría sin datos
  personales (sin matrícula ni imagen), con información agregada como cámara,
  municipio, fecha y resultado.
