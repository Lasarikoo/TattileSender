# Envío a Mossos (resumen)

> **Nota:** consulta la guía completa en [`docs/soap-lectio.md`](../soap-lectio.md).

## Flujo de envío
1. Ingest guarda lectura y crea `messages_queue`.
2. Sender resuelve certificado y endpoint.
3. Sender envía `matricula` vía SOAP con firma WS-Security.
4. En éxito se limpia lectura + imágenes + mensaje.

## Certificados y endpoint
- Se usa el certificado asociado al municipio (o cámara) y sus rutas `client_cert_path`/`path` + `key_path`.
- El endpoint efectivo es `camera.endpoint` → `municipality.endpoint` → `MOSSOS_ENDPOINT_URL`.

## WS-Security
- Se firma con X.509 y se añade `Timestamp` dentro de `wsse:Security`.
- La respuesta SOAP no se verifica porque el servicio no firma el response.
