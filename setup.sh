#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(pwd)"
VENV_DIR="$APP_DIR/.venv"

check() {
  local message="$1"
  local cmd="$2"
  printf "→ %s… " "$message"
  if bash -c "$cmd"; then
    echo "OK"
    return 0
  else
    echo "FAILED"
    echo "✖ Error ${message,}" >&2
    exit 1
  fi
}

get_env_var() {
  local key="$1"
  local value
  value=$(grep -E "^${key}=" .env | tail -n 1 | cut -d '=' -f2-)
  value="${value%\"}"; value="${value#\"}"
  value="${value%\'}"; value="${value#\'}"
  echo "$value"
}

ensure_project_root() {
  if [[ ! -d "app" || ! -f "alembic.ini" || ! -f "requirements.txt" ]]; then
    echo "✖ Este script debe ejecutarse desde la raíz del proyecto TattileSender." >&2
    exit 1
  fi
  if [[ ! -f ".env" ]]; then
    echo "✖ No se ha encontrado .env en el directorio actual." >&2
    exit 1
  fi
}

load_env_vars() {
  echo "Cargando variables desde .env..."
  DB_NAME=$(get_env_var "DB_NAME")
  DB_USER=$(get_env_var "DB_USER")
  DB_PASSWORD=$(get_env_var "DB_PASSWORD")
  DB_HOST=$(get_env_var "DB_HOST")
  DB_PORT=$(get_env_var "DB_PORT")

  if [[ -z "${DB_NAME:-}" || -z "${DB_USER:-}" || -z "${DB_PASSWORD:-}" ]]; then
    echo "✖ DB_NAME, DB_USER o DB_PASSWORD no están definidos en .env" >&2
    exit 1
  fi
}

describe_existing_installation() {
  echo -n "→ Comprobando instalación existente… "

  local parts=()
  [[ -d "$VENV_DIR" ]] && parts+=("venv")

  local db_exists
  db_exists=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}';" 2>/dev/null || echo "")
  [[ "$db_exists" == "1" ]] && parts+=("DB")

  for svc in /etc/systemd/system/tattile-api.service /etc/systemd/system/tattile-ingest.service /etc/systemd/system/tattile-sender.service /etc/systemd/system/tattile-lectorvision.service; do
    [[ -f "$svc" ]] && parts+=("systemd") && break
  done

  if [[ ${#parts[@]} -eq 0 ]]; then
    echo "No detectada"
  else
    local unique_parts=($(printf "%s\n" "${parts[@]}" | awk '!seen[$0]++'))
    echo "Detectada (${unique_parts[*]})"
  fi
}

setup_venv() {
  if [[ ! -d "$VENV_DIR" ]]; then
    printf "→ Creando entorno virtual… "
    if python3 -m venv "$VENV_DIR" > /dev/null 2>&1; then
      echo "OK"
    else
      echo "FAILED"
      exit 1
    fi
  else
    echo "→ Usando entorno virtual existente"
  fi

  check "Instalando dependencias Python" "source '$VENV_DIR/bin/activate' && pip install --upgrade pip > /dev/null 2>&1 && pip install -r requirements.txt > /dev/null 2>&1"
}

install_system_dependencies() {
  check "Instalando dependencias del sistema" "sudo apt-get update > /dev/null 2>&1 && sudo apt-get install -y python3 python3-venv python3-pip postgresql postgresql-contrib > /dev/null 2>&1"
}

configure_postgres() {
  echo -n "→ Configurando PostgreSQL… "

  local db_exists
  db_exists=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}';" 2>/dev/null || echo "")

  if [[ "$db_exists" == "1" ]]; then
    echo "Ya existe"
    return
  fi

  if sudo -u postgres psql > /dev/null 2>&1 <<EOF
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
  then
    echo "Creada"
  else
    echo "FAILED"
    exit 1
  fi
}

run_migrations() {
  check "Ejecutando migraciones" "source '$VENV_DIR/bin/activate' && python -m alembic upgrade head > /dev/null 2>&1"
}

create_systemd_services() {
  local api_service="/etc/systemd/system/tattile-api.service"
  local ingest_service="/etc/systemd/system/tattile-ingest.service"
  local sender_service="/etc/systemd/system/tattile-sender.service"
  local lectorvision_service="/etc/systemd/system/tattile-lectorvision.service"

  local api_content="[Unit]
Description=TattileSender - API HTTP
After=network.target

[Service]
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/uvicorn app.api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
User=root
Group=root

[Install]
WantedBy=multi-user.target"

  local ingest_content="[Unit]
Description=TattileSender - Ingest Service
After=network.target

[Service]
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/python -m app.ingest.main
Restart=always
RestartSec=5
User=root
Group=root

[Install]
WantedBy=multi-user.target"

  local sender_content="[Unit]
Description=TattileSender - Worker de envío a Mossos
After=network.target

[Service]
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/python -m app.sender.main
Restart=always
RestartSec=5
User=root
Group=root

[Install]
WantedBy=multi-user.target"

  local lectorvision_content="[Unit]
Description=TattileSender - API Lector Vision
After=network.target

[Service]
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/uvicorn app.api.lectorvision:app --host 0.0.0.0 --port 33335
Restart=always
RestartSec=5
User=root
Group=root

[Install]
WantedBy=multi-user.target"

  printf "→ Instalando servicios systemd… "
  if echo "$api_content" | sudo tee "$api_service" > /dev/null \
    && echo "$ingest_content" | sudo tee "$ingest_service" > /dev/null \
    && echo "$sender_content" | sudo tee "$sender_service" > /dev/null \
    && echo "$lectorvision_content" | sudo tee "$lectorvision_service" > /dev/null \
    && sudo systemctl daemon-reload > /dev/null 2>&1 \
    && sudo systemctl enable tattile-api.service tattile-ingest.service tattile-sender.service tattile-lectorvision.service > /dev/null 2>&1; then
    echo "OK"
  else
    echo "FAILED"
    exit 1
  fi
}

start_service() {
  local display_name="$1"
  local service_name="$2"
  if sudo systemctl restart "$service_name" > /dev/null 2>&1 && sudo systemctl is-active --quiet "$service_name"; then
    echo "   ${display_name}: OK"
  else
    echo "✖ Error iniciando servicio ${display_name}" >&2
    exit 1
  fi
}

start_services() {
  echo "→ Iniciando servicios…"
  start_service "API" "tattile-api.service"
  start_service "Ingest" "tattile-ingest.service"
  start_service "Sender" "tattile-sender.service"
  start_service "Lector Vision" "tattile-lectorvision.service"
}

main() {
  ensure_project_root
  load_env_vars
  describe_existing_installation
  install_system_dependencies
  setup_venv
  configure_postgres
  run_migrations
  create_systemd_services
  start_services

  echo "\n✔ Setup completado correctamente"
  echo "================================"
  echo "TattileSender instalado"
  echo "================================"
}

main "$@"
