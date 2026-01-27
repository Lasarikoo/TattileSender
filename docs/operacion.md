# Operación técnica (resumen)

> **Nota:** consulta la guía completa en [`docs/ops.md`](ops.md).

## Servicios
- `tattile-api.service` → API principal (`/health`, `/ingest/lectorvision`).
- `tattile-ingest.service` → servicio TCP en `TRANSIT_PORT`.
- `tattile-sender.service` → envío SOAP con reintentos.
- `tattile-lectorvision.service` → API Lector Vision en 33335 (opcional).

## Certificados
- Usa `./ajustes.sh` o `python -m app.admin.cli extract-assign-cert` para extraer certificados.
- El sender necesita `client.pem` + `key.pem` con permisos restringidos.

## Logs
```bash
journalctl -fu tattile-ingest.service
journalctl -fu tattile-sender.service
```
