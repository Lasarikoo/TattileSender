# Guía básica de despliegue en VPS Ubuntu

Esta guía resume los pasos mínimos para desplegar TattileSender en un servidor limpio con Ubuntu 22.04. Adapta puertos, usuarios y contraseñas a tu entorno real.

## Requisitos del servidor
- Ubuntu 22.04 con acceso SSH.
- Puertos abiertos según necesidad: 22 (SSH), 8000 para la API si se expone, 33334 (o el configurado en `TRANSIT_PORT`) para recibir lecturas Tattile.
- Usuario con permisos de sudo.

## Instalar dependencias del sistema
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git postgresql
# Opcional
sudo apt install -y docker.io docker-compose-plugin
```

## Crear usuario de sistema (opcional)
```bash
sudo adduser --system --group tattile
sudo mkdir -p /opt/tattile-sender
sudo chown tattile:tattile /opt/tattile-sender
```

## Clonar el repositorio
```bash
sudo -u tattile git clone https://github.com/tu-org/tattile-sender.git /opt/tattile-sender
cd /opt/tattile-sender
```

## Configurar variables de entorno
```bash
cp .env.example .env
# Edita .env para reflejar valores reales de DB, rutas de certificados y puertos.
```

## Configurar PostgreSQL en el VPS
```bash
sudo -u postgres psql
CREATE USER tattile WITH PASSWORD 'cambia-esto';
CREATE DATABASE tattile_sender OWNER tattile;
GRANT ALL PRIVILEGES ON DATABASE tattile_sender TO tattile;
```

Si solo se aceptarán conexiones locales, asegúrate de mantener `DB_HOST=localhost` en el `.env` y de configurar adecuadamente `pg_hba.conf`.

## Instalar dependencias de Python
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Ejecutar migraciones Alembic
```bash
alembic upgrade head
```

## Lanzar servicios manualmente (tmux/screen)
En una primera fase se recomienda lanzar los procesos desde una sesión persistente:

```bash
# Ventana 1 - API
source .venv/bin/activate
uvicorn app.api.main:app --host 0.0.0.0 --port 8000

# Ventana 2 - Ingest Service
source .venv/bin/activate
python -m app.ingest.main
```

Comprueba que la API responde:

```bash
curl http://127.0.0.1:8000/health
```

Verifica que el servicio de ingesta escucha el puerto definido por `TRANSIT_PORT` y que puedes enviarle XML de prueba con `nc`.

## Notas de seguridad
- Configura `ufw` u otro firewall para limitar qué IPs pueden acceder al puerto del Ingest Service.
- No expongas innecesariamente el puerto de ingestión a internet abierto.
- En fases posteriores se definirán unidades `systemd` para automatizar el arranque de la API y el Ingest Service.
