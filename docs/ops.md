# Operación y mantenimiento

## Servicios systemd (setup.sh)
`setup.sh` genera cuatro servicios:
- `tattile-api.service` → `uvicorn app.api.main:app --port 8000`
- `tattile-ingest.service` → `python -m app.ingest.main`
- `tattile-sender.service` → `python -m app.sender.main`
- `tattile-lectorvision.service` → `uvicorn app.api.lectorvision:app --port 33335`

### Comandos útiles
```bash
sudo systemctl status tattile-api.service
sudo systemctl restart tattile-ingest.service
sudo journalctl -fu tattile-sender.service
```

## CLI de administración
- Panel interactivo: `./ajustes.sh` (requiere `.venv` y `.env`).
- CLI directa: `python -m app.admin.cli`.

### Comandos principales (`app.admin.cli`)
- `delete-camera` (con flags `--keep-readings`, `--keep-images`, `--keep-queue`).
- `delete-municipality` (`--no-cascade`).
- `delete-certificate` (`--force`).
- `delete-endpoint` (`--force`).
- `wipe-readings`, `wipe-queue`, `wipe-images`, `full-wipe`.
- `list-municipalities`.
- `extract-assign-cert` (extrae PFX y asigna certificado a municipio).

## Rotación y limpieza
- Tras envío exitoso se eliminan lecturas, imágenes y mensajes de cola.
- `wipe-images` borra imágenes físicas y limpia referencias en BD.
- `wipe-readings` elimina lecturas y, opcionalmente, cola e imágenes.

## Recuperación de mensajes atascados
El sender marca como `FAILED` cualquier mensaje `SENDING` más antiguo que `SENDER_STUCK_TIMEOUT_SECONDS`, permitiendo su reintento.

## Migraciones
```bash
python -m alembic upgrade head
```

## Monitorización mínima
- `/health` devuelve conteos de cola (`pending`, `failed`, `dead`) y total de lecturas.
- Revisa logs con `LOG_LEVEL=DEBUG` durante pruebas.

## Depuración SOAP
Para activar el volcado del envelope SOAP y revisar detalles de validación:
1) Define `SOAP_DEBUG=1` y sube el nivel a `LOG_LEVEL=DEBUG` en tu `.env` o entorno.
2) Reinicia el servicio `tattile-sender` para que lea las nuevas variables.
3) Revisa los logs del sender:
   - systemd: `sudo journalctl -fu tattile-sender.service`
   - contenedor: `docker logs -f <nombre_del_contenedor_sender>`
