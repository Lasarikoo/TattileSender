#!/usr/bin/env bash
set -euo pipefail

# Script de instalación automática para TattileSender en Ubuntu.
# Debe ejecutarse desde la raíz del proyecto con permisos de sudo.
# No modifica el archivo .env; únicamente valida su existencia y usa sus valores.

APP_DIR="$(pwd)"
VENV_DIR="$APP_DIR/.venv"

# Comprueba que estamos en la raíz del proyecto y que .env existe.
check_project_root() {
  if [[ ! -d "app" || ! -f "alembic.ini" || ! -f "requirements.txt" ]]; then
    echo "ERROR: Este script debe ejecutarse desde la raíz del proyecto TattileSender." >&2
    exit 1
  fi
  if [[ ! -f ".env" ]]; then
    echo "ERROR: No se ha encontrado .env en el directorio actual. Crea y configura .env antes de ejecutar setup.sh" >&2
    exit 1
  fi
}

# Función para leer un valor de .env (formato CLAVE=VALOR), ignorando comentarios y líneas vacías.
get_env_var() {
  local key="$1"
  local value
  value=$(grep -E "^${key}=" .env | tail -n 1 | cut -d '=' -f2-)
  # Elimina comillas simples o dobles envolventes, si existen
  value="${value%\"}"; value="${value#\"}"
  value="${value%\'}"; value="${value#\'}"
  echo "$value"
}

DB_NAME=""
DB_USER=""
DB_PASSWORD=""
DB_HOST=""
DB_PORT=""
DB_ALREADY_EXISTS="no"

load_env_vars() {
  echo "Cargando variables desde .env..."
  DB_NAME=$(get_env_var "DB_NAME")
  DB_USER=$(get_env_var "DB_USER")
  DB_PASSWORD=$(get_env_var "DB_PASSWORD")
  DB_HOST=$(get_env_var "DB_HOST")
  DB_PORT=$(get_env_var "DB_PORT")

  if [[ -z "$DB_NAME" || -z "$DB_USER" || -z "$DB_PASSWORD" ]]; then
    echo "ERROR: DB_NAME, DB_USER o DB_PASSWORD no están definidos en .env" >&2
    exit 1
  fi
}

psql_command() {
  local query="$1"
  sudo -u postgres psql -tAc "$query"
}

# Comprueba si ya existe una instalación previa.
check_existing_installation() {
  local existing_venv="no"
  local existing_db="no"
  local existing_service="no"

  [[ -d "$VENV_DIR" ]] && existing_venv="yes"

  if [[ -n "$DB_NAME" ]]; then
    local db_exists
    db_exists=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}';" || echo "")
    if [[ "$db_exists" == "1" ]]; then
      existing_db="yes"
      DB_ALREADY_EXISTS="yes"
    fi
  fi

  for svc in /etc/systemd/system/tattile-api.service /etc/systemd/system/tattile-ingest.service /etc/systemd/system/tattile-sender.service; do
    if [[ -f "$svc" ]]; then
      existing_service="yes"
      break
    fi
  done

  if [[ "$existing_venv" == "yes" || "$existing_db" == "yes" || "$existing_service" == "yes" ]]; then
    echo "Parece que ya hay una instalación existente de TattileSender (venv/DB/systemd detectados)."
    echo "Este script está pensado para instalaciones nuevas. ¿Quieres continuar de todos modos? [y/N]"
    read -r response
    if [[ "${response:-N}" != "y" && "${response:-N}" != "Y" ]]; then
      echo "Abortando a petición del usuario."
      exit 0
    fi
  fi
}

install_system_dependencies() {
  echo "Instalando dependencias del sistema..."
  sudo apt update
  sudo apt install -y python3 python3-venv python3-pip postgresql postgresql-contrib
}

setup_venv() {
  if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creando entorno virtual en $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
  else
    echo "Entorno virtual existente detectado, usando $VENV_DIR..."
  fi
  # shellcheck source=/dev/null
  source "$VENV_DIR/bin/activate"
  echo "Actualizando pip e instalando dependencias Python..."
  pip install --upgrade pip
  pip install -r requirements.txt
}

setup_postgres() {
  echo "Configurando PostgreSQL..."

  if [[ "$DB_ALREADY_EXISTS" == "yes" ]]; then
    echo "La base de datos ${DB_NAME} ya existe. Omitiendo configuración de PostgreSQL."
    return
  fi

  sudo -u postgres psql <<EOF
DO
\$do\$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}'
   ) THEN
      CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
   END IF;
END
\$do\$;

CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
EOF
}

run_migrations() {
  echo "Ejecutando migraciones Alembic..."
  # shellcheck source=/dev/null
  source "$VENV_DIR/bin/activate"
  python -m alembic upgrade head
  echo "Migraciones Alembic completadas."
}

prompt_overwrite_service() {
  local service_path="$1"
  if [[ -f "$service_path" ]]; then
    echo "Advertencia: ya existe ${service_path}. ¿Deseas sobrescribirlo? [y/N]"
    read -r overwrite
    if [[ "${overwrite:-N}" != "y" && "${overwrite:-N}" != "Y" ]]; then
      echo "Conservando ${service_path} existente."
      return 1
    fi
  fi
  return 0
}

create_service_file() {
  local service_path="$1"
  local content="$2"
  echo "Creando ${service_path}..."
  echo "$content" | sudo tee "$service_path" > /dev/null
}

create_systemd_services() {
  local api_service="/etc/systemd/system/tattile-api.service"
  local ingest_service="/etc/systemd/system/tattile-ingest.service"
  local sender_service="/etc/systemd/system/tattile-sender.service"

  echo "Creando ${api_service}..."
  sudo tee "$api_service" > /dev/null << 'EOF'
[Unit]
Description=TattileSender - API HTTP
After=network.target

[Service]
WorkingDirectory=/root/TattileSender
EnvironmentFile=/root/TattileSender/.env
ExecStart=/root/TattileSender/.venv/bin/uvicorn app.api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF

  echo "Creando ${ingest_service}..."
  sudo tee "$ingest_service" > /dev/null << 'EOF'
[Unit]
Description=TattileSender - Ingest Service
After=network.target

[Service]
WorkingDirectory=/root/TattileSender
EnvironmentFile=/root/TattileSender/.env
ExecStart=/root/TattileSender/.venv/bin/python -m app.ingest.main
Restart=always
RestartSec=5
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF

  echo "Creando ${sender_service}..."
  sudo tee "$sender_service" > /dev/null << 'EOF'
[Unit]
Description=TattileSender - Worker de envío a Mossos
After=network.target

[Service]
WorkingDirectory=/root/TattileSender
EnvironmentFile=/root/TattileSender/.env
ExecStart=/root/TattileSender/.venv/bin/python -m app.sender.main
Restart=always
RestartSec=5
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF

  for svc in tattile-api tattile-ingest tattile-sender; do
    if [ ! -s "/etc/systemd/system/${svc}.service" ]; then
      echo "ERROR: /etc/systemd/system/${svc}.service no existe o está vacío"
      exit 1
    fi
  done

  echo "Recargando systemd y habilitando servicios..."
  sudo systemctl daemon-reload
  sudo systemctl enable tattile-api.service tattile-ingest.service tattile-sender.service
  sudo systemctl status tattile-api.service --no-pager -l || true
  sudo systemctl status tattile-ingest.service --no-pager -l || true
  sudo systemctl status tattile-sender.service --no-pager -l || true
}

start_services() {
  echo "Iniciando servicios..."
  sudo systemctl start tattile-api.service tattile-ingest.service tattile-sender.service
  sudo systemctl status tattile-api.service --no-pager -l || true
  sudo systemctl status tattile-ingest.service --no-pager -l || true
  sudo systemctl status tattile-sender.service --no-pager -l || true
}

main() {
  check_project_root
  load_env_vars
  check_existing_installation
  install_system_dependencies
  setup_venv
  setup_postgres
  run_migrations
  create_systemd_services
  start_services
  echo "Setup completado."
}

main "$@"
