# Visión del proyecto TattileSender

## Qué es TattileSender
TattileSender es un servicio backend que actúa como puente entre las cámaras de
lectura automática de matrículas (ALPR) Tattile y el endpoint SOAP de Mossos
d'Esquadra. Recibe las lecturas en formato XML directamente en un servidor Linux
(VPS), las normaliza y las envía de forma confiable, usando certificados
específicos por cámara o municipio.

## Problema que resuelve
Actualmente existe un ejecutable Windows (MossosWSNet.exe) que procesa las
lecturas. Este enfoque presenta varios problemas: dificultad para operar en
Linux, falta de trazabilidad detallada, manejo limitado de múltiples cámaras y
certificados y errores frecuentes (por ejemplo, WSE511 cuando un certificado es
inválido). TattileSender nace para ofrecer un flujo más robusto, auditable y
escalable en entorno Linux.

## Objetivo de negocio
- Garantizar que todas las lecturas ALPR relevantes lleguen a Mossos con la
  menor pérdida posible.
- Simplificar la operación y mantenimiento en un VPS Ubuntu, reduciendo
  dependencia de entornos Windows.
- Facilitar la gestión multi-cámara y multi-certificado para distintos
  municipios, con posibilidad de incorporar métricas y alertas.

## Objetivo técnico
- Implementar un servicio de ingesta TCP/UDP capaz de recibir y validar lecturas
  Tattile en XML.
- Persistir las lecturas en una cola basada en base de datos que permita
  reintentos y trazabilidad.
- Enviar las lecturas mediante SOAP firmado con certificados PFX seleccionados
  según la cámara u origen.
- Exponer una API administrativa mínima (FastAPI) para operaciones de soporte y
  observabilidad básica.

## Alcance inicial (Fase 0 y Fase 1)
- Fase 0 (actual): preparar el scaffolding, documentación y configuración
  inicial sin lógica de negocio.
- Fase 1: recepción de lecturas Tattile, normalización, encolado persistente y
  reenvío a Mossos con certificados PFX, incluyendo reintentos y logging.

## Fuera de alcance inicial
- Interfaces de usuario complejas o paneles avanzados.
- Informes históricos o analíticos avanzados.
- Integraciones adicionales más allá de Mossos.
- Orquestadores complejos (Kubernetes); se prioriza systemd o Docker simple.

## Beneficios esperados
- Mayor resiliencia ante caídas del endpoint de Mossos.
- Capacidad de operar con 100–200 cámaras con configuración clara y central.
- Reducción de incidencias por certificados caducados o mal configurados gracias
  a una gestión explícita de certificados y logs detallados.
