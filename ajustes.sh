#!/usr/bin/env bash
# Panel interactivo para poblar datos básicos en TattileSender.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$PROJECT_DIR/.venv/bin/activate"

if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

list_cameras() {
    python - <<'PY'
from app.models import Camera, SessionLocal


def main():
    session = SessionLocal()
    try:
        cameras = session.query(Camera).order_by(Camera.id).all()
        if not cameras:
            print("No hay cámaras registradas.")
            return
        print("Cámaras disponibles:")
        for cam in cameras:
            print(
                f"- {cam.id}: {cam.serial_number} "
                f"(municipio_id={cam.municipality_id}, endpoint_id={cam.endpoint_id}, cert_id={cam.certificate_id})"
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()
PY
}

list_municipalities() {
    python - <<'PY'
from app.models import Municipality, SessionLocal


def main():
    session = SessionLocal()
    try:
        municipalities = session.query(Municipality).order_by(Municipality.id).all()
        if not municipalities:
            print("No hay municipios registrados.")
            return
        print("Municipios disponibles:")
        for mun in municipalities:
            print(
                f"- {mun.id}: {mun.name} "
                f"(endpoint_id={mun.endpoint_id}, active={mun.active})"
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()
PY
}

list_certificates() {
    python - <<'PY'
from app.models import Certificate, SessionLocal


def main():
    session = SessionLocal()
    try:
        certificates = session.query(Certificate).order_by(Certificate.id).all()
        if not certificates:
            print("No hay certificados registrados.")
            return
        print("Certificados disponibles:")
        for cert in certificates:
            alias = f" alias={cert.alias}" if cert.alias else ""
            print(
                f"- {cert.id}: {cert.name}{alias} (municipio_id={cert.municipality_id})"
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()
PY
}

extract_pfx_and_assign() {
    CERTS_DIR=$(python -c "from app.config import settings; print(settings.certs_dir)" 2>/dev/null)
    if [ -z "$CERTS_DIR" ]; then
        CERTS_DIR="./certs"
    fi

    mapfile -t PFX_FILES < <(find "$CERTS_DIR" -maxdepth 1 -type f \( -iname "*.pfx" -o -iname "*.p12" \) | sort)

    if [ ${#PFX_FILES[@]} -eq 0 ]; then
        echo "No se han encontrado certificados PFX/P12 en $CERTS_DIR."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi

    echo "Certificados PFX encontrados:"
    idx=1
    for f in "${PFX_FILES[@]}"; do
        echo "  $idx) $f"
        idx=$((idx+1))
    done

    read -p "Selecciona un certificado por número: " SELECTED
    if ! [[ "$SELECTED" =~ ^[0-9]+$ ]] || [ "$SELECTED" -lt 1 ] || [ "$SELECTED" -gt ${#PFX_FILES[@]} ]; then
        echo "Selección inválida."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi

    PFX_PATH="${PFX_FILES[$((SELECTED-1))]}"

    read -s -p "Introduce la contraseña del PFX: " PFX_PASS
    echo

    python -m app.admin.cli list-municipalities
    read -p "Introduce el ID del municipio al que quieres asignar este certificado: " MUNICIPALITY_ID
    if [ -z "$MUNICIPALITY_ID" ]; then
        echo "El ID de municipio es obligatorio."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi
    if ! [[ "$MUNICIPALITY_ID" =~ ^[0-9]+$ ]]; then
        echo "El ID del municipio debe ser numérico."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi

    python -m app.admin.cli extract-assign-cert \
        --pfx-path "$PFX_PATH" \
        --password "$PFX_PASS" \
        --municipality-id "$MUNICIPALITY_ID"

    if [ $? -ne 0 ]; then
        echo "Ha ocurrido un error durante la extracción o asignación del certificado."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi

    echo "Certificado descomprimido y asignado correctamente a municipio $MUNICIPALITY_ID."
    read -p "Pulsa ENTER para continuar..." _
}

list_endpoints() {
    python - <<'PY'
from app.models import Endpoint, SessionLocal


def main():
    session = SessionLocal()
    try:
        endpoints = session.query(Endpoint).order_by(Endpoint.id).all()
        if not endpoints:
            print("No hay endpoints registrados.")
            return
        print("Endpoints disponibles:")
        for ep in endpoints:
            print(f"- {ep.id}: {ep.name} ({ep.url})")
    finally:
        session.close()


if __name__ == "__main__":
    main()
PY
}

show_add_menu() {
    while true; do
        clear
        echo "Añadir datos"
        echo "1) Añadir municipios"
        echo "2) Añadir cámaras"
        echo "3) Añadir endpoints"
        echo "4) Descomprimir certificado PFX y asignar a municipio"
        echo "5) Volver al menú principal"
        read -rp "Seleccione una opción: " option
        case $option in
            1)
                python -m app.scripts.add_municipality
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            2)
                python -m app.scripts.add_camera
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            3)
                python -m app.scripts.add_endpoint
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            4)
                extract_pfx_and_assign
                ;;
            5)
                break
                ;;
            *)
                echo "Opción no válida"
                read -rp "Pulsa ENTER para continuar..." _
                ;;
        esac
    done
}

show_assign_menu() {
    while true; do
        clear
        echo "Asignar relaciones"
        echo "1) Asignar certificado a municipio"
        echo "2) Asignar endpoint a municipio"
        echo "3) Asignar certificado a cámara"
        echo "4) Asignar endpoint a cámara"
        echo "5) Volver al menú principal"
        read -rp "Seleccione una opción: " option
        case $option in
            1)
                python -m app.scripts.assign_municipality_certificate
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            2)
                python -m app.scripts.assign_municipality_endpoint
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            3)
                python -m app.scripts.assign_camera_certificate
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            4)
                python -m app.scripts.assign_camera_endpoint
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            5)
                break
                ;;
            *)
                echo "Opción no válida"
                read -rp "Pulsa ENTER para continuar..." _
                ;;
        esac
    done
}

show_delete_menu() {
    while true; do
        clear
        echo "Eliminar datos"
        echo "1) Eliminar cámara"
        echo "2) Eliminar municipio"
        echo "3) Eliminar certificado"
        echo "4) Eliminar endpoint"
        echo "5) Limpiar TODAS las lecturas"
        echo "0) Volver"
        read -rp "Seleccione una opción: " option
        case $option in
            1)
                list_cameras
                read -rp "ID o número de serie de la cámara: " cam_id
                read -rp "Vas a eliminar la cámara y sus datos asociados. ¿Seguro? [s/N]: " confirm
                if [[ "$confirm" != "s" && "$confirm" != "S" ]]; then
                    echo "Operación cancelada."
                else
                    if [[ $cam_id =~ ^[0-9]+$ ]]; then
                        python -m app.admin.cli delete-camera --id "$cam_id"
                    else
                        python -m app.admin.cli delete-camera --serial-number "$cam_id"
                    fi
                fi
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            2)
                list_municipalities
                read -rp "ID o nombre del municipio: " mun_id
                read -rp "Se borrará el municipio y datos asociados. ¿Seguro? [s/N]: " confirm
                if [[ "$confirm" != "s" && "$confirm" != "S" ]]; then
                    echo "Operación cancelada."
                else
                    if [[ $mun_id =~ ^[0-9]+$ ]]; then
                        python -m app.admin.cli delete-municipality --id "$mun_id"
                    else
                        python -m app.admin.cli delete-municipality --name "$mun_id"
                    fi
                fi
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            3)
                list_certificates
                read -rp "ID, alias o nombre del certificado: " cert_id
                read -rp "¿Forzar borrado si está en uso? [s/N]: " force_cert
                read -rp "Vas a borrar un certificado. ¿Seguro? [s/N]: " confirm
                if [[ "$confirm" != "s" && "$confirm" != "S" ]]; then
                    echo "Operación cancelada."
                else
                    force_flag=""
                    if [[ "$force_cert" == "s" || "$force_cert" == "S" ]]; then
                        force_flag="--force"
                    fi
                    if [[ $cert_id =~ ^[0-9]+$ ]]; then
                        python -m app.admin.cli delete-certificate --id "$cert_id" $force_flag
                    else
                        python -m app.admin.cli delete-certificate --alias "$cert_id" $force_flag
                    fi
                fi
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            4)
                list_endpoints
                read -rp "ID o nombre del endpoint: " endpoint_id
                read -rp "¿Forzar borrado si está en uso? [s/N]: " force_ep
                read -rp "Vas a borrar un endpoint. ¿Seguro? [s/N]: " confirm
                if [[ "$confirm" != "s" && "$confirm" != "S" ]]; then
                    echo "Operación cancelada."
                else
                    force_flag=""
                    if [[ "$force_ep" == "s" || "$force_ep" == "S" ]]; then
                        force_flag="--force"
                    fi
                    if [[ $endpoint_id =~ ^[0-9]+$ ]]; then
                        python -m app.admin.cli delete-endpoint --id "$endpoint_id" $force_flag
                    else
                        python -m app.admin.cli delete-endpoint --name "$endpoint_id" $force_flag
                    fi
                fi
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            5)
                read -rp "Vas a eliminar TODAS las lecturas. ¿Seguro? [s/N]: " confirm
                if [[ "$confirm" == "s" || "$confirm" == "S" ]]; then
                    python -m app.admin.cli wipe-readings
                else
                    echo "Operación cancelada."
                fi
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            0)
                break
                ;;
            *)
                echo "Opción no válida"
                read -rp "Pulsa ENTER para continuar..." _
                ;;
        esac
    done
}

show_update_menu() {
    while true; do
        clear
        echo "Modificar datos"
        echo "1) Modificar municipios"
        echo "2) Modificar cámaras"
        echo "3) Modificar endpoints"
        echo "4) Modificar certificados"
        echo "5) Volver"
        read -rp "Seleccione una opción: " option
        case $option in
            1)
                python -m app.scripts.update_municipality
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            2)
                python -m app.scripts.update_camera
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            3)
                python -m app.scripts.update_endpoint
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            4)
                python -m app.scripts.update_certificate
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            5)
                break
                ;;
            *)
                echo "Opción no válida"
                read -rp "Pulsa ENTER para continuar..." _
                ;;
        esac
    done
}

mostrar_uso_sistema() {
    get_cpu_usage() {
        local cpu_line1 cpu_line2 idle1 idle2 total1 total2 i
        read -r cpu_line1 < /proc/stat
        sleep 0.1
        read -r cpu_line2 < /proc/stat

        read -ra cpu1 <<< "$cpu_line1"
        read -ra cpu2 <<< "$cpu_line2"

        idle1=${cpu1[4]}
        idle2=${cpu2[4]}
        total1=0
        total2=0

        for i in "${cpu1[@]:1}"; do
            total1=$((total1 + i))
        done
        for i in "${cpu2[@]:1}"; do
            total2=$((total2 + i))
        done

        local total_diff=$((total2 - total1))
        local idle_diff=$((idle2 - idle1))
        awk "BEGIN {if ($total_diff==0) print 0; else printf \"%.1f\", (100 * ($total_diff - $idle_diff) / $total_diff)}"
    }

    get_net_totals() {
        awk 'NR>2 {rx+=$2; tx+=$10} END {print rx, tx}' /proc/net/dev
    }

    read -r prev_rx prev_tx < <(get_net_totals)

    while true; do
        clear

        local uptime_info cpu_usage mem_total mem_used mem_percent bar_length filled empty disk_info
        local curr_rx curr_tx rx_rate tx_rate

        uptime_info=$(uptime)
        cpu_usage=$(get_cpu_usage)

        mem_total=$(free -m | awk '/Mem:/ {print $2}')
        mem_used=$(free -m | awk '/Mem:/ {print $3}')
        if [[ -z "$mem_total" || "$mem_total" -eq 0 ]]; then
            mem_percent=0
            filled=0
        else
            mem_percent=$(awk "BEGIN {printf \"%.1f\", ($mem_used/$mem_total)*100}")
            bar_length=30
            filled=$(( (mem_used * bar_length) / mem_total ))
        fi
        bar_length=${bar_length:-30}
        empty=$((bar_length - filled))

        read -r curr_rx curr_tx < <(get_net_totals)
        rx_rate=$(awk "BEGIN {printf \"%.1f\", ($curr_rx - $prev_rx)/1024}")
        tx_rate=$(awk "BEGIN {printf \"%.1f\", ($curr_tx - $prev_tx)/1024}")
        prev_rx=$curr_rx
        prev_tx=$curr_tx

        disk_info=$(df -h / | awk 'NR==2 {print $4" libres de "$2" ("$5" usado)"}')

        printf "%-30s %s\n" "Uptime y carga:" "$uptime_info"
        printf "%-30s %s%%\n" "CPU uso total:" "$cpu_usage"

        printf "%-30s %s MiB / %s MiB (%s%%)\n" "RAM:" "$mem_used" "$mem_total" "$mem_percent"
        printf "%-30s [%s%s]\n" "" "$(printf '%*s' "$filled" '' | tr ' ' '#')" "$(printf '%*s' "$empty" '' | tr ' ' '-')"

        printf "%-30s %s\n" "Disco disponible (/)" "$disk_info"
        printf "%-30s RX: %s KB/s | TX: %s KB/s\n" "Tráfico de red:" "$rx_rate" "$tx_rate"

        echo
        echo "== TOP 5 PROCESOS POR CPU =="
        ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -n 6

        echo
        echo "== TOP 5 PROCESOS POR MEMORIA =="
        ps -eo pid,comm,%cpu,%mem --sort=-%mem | head -n 6

        echo
        echo "Pulsa Q para salir"
        read -t 1 -n 1 key && [[ $key == "q" || $key == "Q" ]] && break
    done
}

mostrar_estadisticas_bd() {
    clear

    if [[ -z "$DB_NAME" || -z "$DB_USER" ]]; then
        echo "ERROR: Variables DB_NAME o DB_USER no cargadas."
        read -rp "Pulsa Enter para volver..." _
        return
    fi

    echo "== TOTAL DE DATOS EN BASE DE DATOS =="
    local query
    query=$(cat <<'SQL'
SELECT 
 (SELECT COUNT(*) FROM alpr_readings) AS readings,
 (SELECT COUNT(*) FROM messages_queue) AS queue,
 (SELECT COUNT(*) FROM cameras) AS cameras,
 (SELECT COUNT(*) FROM municipalities) AS municipalities;
SQL
)

    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -c "$query"

    echo
    read -rp "Pulsa Enter para volver al menú de utilidades..." _
}

run_psql() {
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" "$@"
}

sanitize_utf8() {
    local value="$1"
    if command -v iconv >/dev/null 2>&1; then
        printf '%s' "$value" | iconv -f UTF-8 -t UTF-8//IGNORE 2>/dev/null
        return
    fi
    printf '%s' "$value"
}

escape_sql_literal() {
    local value="$1"
    value=${value//\'/\'\'}
    echo "$value"
}

ensure_db_env() {
    if [[ -z "$DB_NAME" || -z "$DB_USER" ]]; then
        echo "ERROR: Variables DB_NAME o DB_USER no cargadas."
        read -rp "Pulsa Enter para volver..." _
        return 1
    fi
    return 0
}

get_limit_input() {
    local prompt="$1"
    local default_limit="$2"
    local limit
    read -rp "$prompt [$default_limit]: " limit
    limit=${limit:-$default_limit}
    if ! [[ "$limit" =~ ^[0-9]+$ ]]; then
        limit="$default_limit"
    fi
    echo "$limit"
}

consultar_registros_almacenados() {
    clear
    ensure_db_env || return
    local limit
    limit=$(get_limit_input "¿Cuántos registros quieres ver?" "20")
    run_psql -c "
SELECT
    r.id,
    r.plate,
    r.timestamp_utc,
    r.created_at,
    c.id AS camera_id,
    c.serial_number,
    m.name AS municipality
FROM alpr_readings r
JOIN cameras c ON r.camera_id = c.id
JOIN municipalities m ON c.municipality_id = m.id
ORDER BY r.created_at DESC
LIMIT $limit;"
    echo
    read -rp "Pulsa Enter para volver..." _
}

consultar_registros_cola() {
    clear
    ensure_db_env || return
    echo "Estados disponibles: PENDING, SENDING, SUCCESS, FAILED, DEAD, ALL"
    read -rp "Introduce el estado (o ALL para todos): " status
    status=${status:-ALL}
    status=$(sanitize_utf8 "$status")
    case "$status" in
        PENDING|SENDING|SUCCESS|FAILED|DEAD|ALL)
            ;;
        *)
            echo "Estado no válido, se usarán todos."
            status="ALL"
            ;;
    esac
    local limit
    limit=$(get_limit_input "¿Cuántos registros quieres ver?" "20")

    if [[ "$status" == "ALL" ]]; then
        run_psql -c "
SELECT
    q.id,
    q.status,
    q.attempts,
    q.created_at,
    q.updated_at,
    q.last_error,
    r.plate,
    c.serial_number,
    m.name AS municipality
FROM messages_queue q
JOIN alpr_readings r ON q.reading_id = r.id
JOIN cameras c ON r.camera_id = c.id
JOIN municipalities m ON c.municipality_id = m.id
ORDER BY q.updated_at DESC
LIMIT $limit;"
    else
        run_psql -c "
SELECT
    q.id,
    q.status,
    q.attempts,
    q.created_at,
    q.updated_at,
    q.last_error,
    r.plate,
    c.serial_number,
    m.name AS municipality
FROM messages_queue q
JOIN alpr_readings r ON q.reading_id = r.id
JOIN cameras c ON r.camera_id = c.id
JOIN municipalities m ON c.municipality_id = m.id
WHERE q.status = '$(escape_sql_literal "$status")'
ORDER BY q.updated_at DESC
LIMIT $limit;"
    fi

    echo
    read -rp "Pulsa Enter para volver..." _
}

consultar_registros_por_camara() {
    clear
    ensure_db_env || return
    list_cameras
    echo
    read -rp "Introduce el ID o número de serie de la cámara: " camera_value
    camera_value=$(sanitize_utf8 "$camera_value")
    if [[ -z "$camera_value" ]]; then
        echo "Cámara no indicada."
        read -rp "Pulsa Enter para volver..." _
        return
    fi
    local limit
    limit=$(get_limit_input "¿Cuántos registros quieres ver?" "20")
    if [[ "$camera_value" =~ ^[0-9]+$ ]]; then
        run_psql -c "
SELECT
    r.id,
    r.plate,
    r.timestamp_utc,
    r.created_at,
    c.serial_number,
    m.name AS municipality
FROM alpr_readings r
JOIN cameras c ON r.camera_id = c.id
JOIN municipalities m ON c.municipality_id = m.id
WHERE c.id = $camera_value
ORDER BY r.created_at DESC
LIMIT $limit;"
    else
        run_psql -c "
SELECT
    r.id,
    r.plate,
    r.timestamp_utc,
    r.created_at,
    c.serial_number,
    m.name AS municipality
FROM alpr_readings r
JOIN cameras c ON r.camera_id = c.id
JOIN municipalities m ON c.municipality_id = m.id
WHERE c.serial_number = '$(escape_sql_literal "$camera_value")'
ORDER BY r.created_at DESC
LIMIT $limit;"
    fi
    echo
    read -rp "Pulsa Enter para volver..." _
}

consultar_registros_por_municipio() {
    clear
    ensure_db_env || return
    list_municipalities
    echo
    read -rp "Introduce el ID o nombre del municipio: " mun_value
    mun_value=$(sanitize_utf8 "$mun_value")
    if [[ -z "$mun_value" ]]; then
        echo "Municipio no indicado."
        read -rp "Pulsa Enter para volver..." _
        return
    fi
    local limit
    limit=$(get_limit_input "¿Cuántos registros quieres ver?" "20")
    if [[ "$mun_value" =~ ^[0-9]+$ ]]; then
        run_psql -c "
SELECT
    r.id,
    r.plate,
    r.timestamp_utc,
    r.created_at,
    c.serial_number,
    m.name AS municipality
FROM alpr_readings r
JOIN cameras c ON r.camera_id = c.id
JOIN municipalities m ON c.municipality_id = m.id
WHERE m.id = $mun_value
ORDER BY r.created_at DESC
LIMIT $limit;"
    else
        run_psql -c "
SELECT
    r.id,
    r.plate,
    r.timestamp_utc,
    r.created_at,
    c.serial_number,
    m.name AS municipality
FROM alpr_readings r
JOIN cameras c ON r.camera_id = c.id
JOIN municipalities m ON c.municipality_id = m.id
WHERE m.name ILIKE '%' || '$(escape_sql_literal "$mun_value")' || '%'
ORDER BY r.created_at DESC
LIMIT $limit;"
    fi
    echo
    read -rp "Pulsa Enter para volver..." _
}

consultar_registros_con_fallos() {
    clear
    ensure_db_env || return
    local limit
    limit=$(get_limit_input "¿Cuántos registros quieres ver?" "20")
    run_psql -c "
SELECT
    q.id,
    q.status,
    q.attempts,
    q.updated_at,
    q.last_error,
    r.plate,
    c.serial_number,
    m.name AS municipality
FROM messages_queue q
JOIN alpr_readings r ON q.reading_id = r.id
JOIN cameras c ON r.camera_id = c.id
JOIN municipalities m ON c.municipality_id = m.id
WHERE q.status IN ('FAILED', 'DEAD') OR q.last_error IS NOT NULL
ORDER BY q.updated_at DESC
LIMIT $limit;"
    echo
    read -rp "Pulsa Enter para volver..." _
}

consultar_ultimo_envio_camara() {
    clear
    ensure_db_env || return
    list_cameras
    echo
    read -rp "Introduce el ID o número de serie de la cámara: " camera_value
    camera_value=$(sanitize_utf8 "$camera_value")
    if [[ -z "$camera_value" ]]; then
        echo "Cámara no indicada."
        read -rp "Pulsa Enter para volver..." _
        return
    fi
    if [[ "$camera_value" =~ ^[0-9]+$ ]]; then
        run_psql -c "
SELECT
    c.id,
    c.serial_number,
    COALESCE(
        GREATEST(
            c.last_sent_at,
            MAX(COALESCE(q.last_sent_at, q.sent_at))
        ),
        c.last_sent_at,
        MAX(COALESCE(q.last_sent_at, q.sent_at))
    ) AS last_sent_at
FROM cameras c
LEFT JOIN alpr_readings r ON r.camera_id = c.id
LEFT JOIN messages_queue q ON q.reading_id = r.id
WHERE c.id = $camera_value
GROUP BY c.id, c.serial_number, c.last_sent_at;"
    else
        run_psql -c "
SELECT
    c.id,
    c.serial_number,
    COALESCE(
        GREATEST(
            c.last_sent_at,
            MAX(COALESCE(q.last_sent_at, q.sent_at))
        ),
        c.last_sent_at,
        MAX(COALESCE(q.last_sent_at, q.sent_at))
    ) AS last_sent_at
FROM cameras c
LEFT JOIN alpr_readings r ON r.camera_id = c.id
LEFT JOIN messages_queue q ON q.reading_id = r.id
WHERE c.serial_number = '$(escape_sql_literal "$camera_value")'
GROUP BY c.id, c.serial_number, c.last_sent_at;"
    fi
    echo
    read -rp "Pulsa Enter para volver..." _
}

menu_consultas_bd() {
    while true; do
        clear
        echo "=== CONSULTAS DE BASE DE DATOS ==="
        echo "1) Ver registros almacenados"
        echo "2) Ver registros en cola"
        echo "3) Ver registros por cámara"
        echo "4) Ver registros por municipio"
        echo "5) Ver registros con warnings o fallos"
        echo "6) Ver último envío por cámara"
        echo "7) Volver al menú de utilidades"
        read -rp "Selecciona una opción: " opt
        case "$opt" in
            1)
                consultar_registros_almacenados
                ;;
            2)
                consultar_registros_cola
                ;;
            3)
                consultar_registros_por_camara
                ;;
            4)
                consultar_registros_por_municipio
                ;;
            5)
                consultar_registros_con_fallos
                ;;
            6)
                consultar_ultimo_envio_camara
                ;;
            7)
                break
                ;;
            *)
                echo "Opción no válida"
                read -rp "Pulsa ENTER para continuar..." _
                ;;
        esac
    done
}

reiniciar_servicios_tattile() {
    clear
    read -rp "Esto reiniciará tattile-api, tattile-ingest y tattile-sender. ¿Quieres continuar? [y/N] " confirm
    case "$confirm" in
        y|Y)
            ;;
        *)
            echo "Operación cancelada."
            return
            ;;
    esac

    echo "Reiniciando servicios..."
    sudo systemctl restart tattile-api tattile-ingest tattile-sender || {
        echo "Error al reiniciar alguno de los servicios."
    }

    echo
    echo "== ESTADO DE LOS SERVICIOS =="
    for service in tattile-api tattile-ingest tattile-sender; do
        printf "%s: %s\n" "$service" "$(systemctl is-active "$service")"
    done

    echo
    read -rp "Pulsa Enter para volver al menú de utilidades..." _
}

ver_logs_tiempo_real() {
    get_estado_servicio() {
        local service_name="$1"
        if systemctl is-active --quiet "$service_name"; then
            echo "activo"
        else
            echo "inactivo"
        fi
    }

    while true; do
        clear
        local estado_api estado_ingest estado_sender
        estado_api=$(get_estado_servicio "tattile-api.service")
        estado_ingest=$(get_estado_servicio "tattile-ingest.service")
        estado_sender=$(get_estado_servicio "tattile-sender.service")

        echo "=== LOGS EN TIEMPO REAL ==="
        echo "Servicios detectados:"
        echo
        echo "1) tattile-api.service   ($estado_api)"
        echo "2) tattile-ingest.service ($estado_ingest)"
        echo "3) tattile-sender.service ($estado_sender)"
        echo "4) Volver al menú de utilidades"
        echo
        read -rp "Selecciona un servicio: " opt_log

        case "$opt_log" in
            1)
                clear
                echo "Mostrando logs en tiempo real de tattile-api.service (Ctrl+C para salir)..."
                journalctl -u tattile-api.service -n 50 -f
                echo
                read -rp "Pulsa Enter para volver al menú de logs..." _
                ;;
            2)
                clear
                echo "Mostrando logs en tiempo real de tattile-ingest.service (Ctrl+C para salir)..."
                journalctl -u tattile-ingest.service -n 50 -f
                echo
                read -rp "Pulsa Enter para volver al menú de logs..." _
                ;;
            3)
                clear
                echo "Mostrando logs en tiempo real de tattile-sender.service (Ctrl+C para salir)..."
                journalctl -u tattile-sender.service -n 50 -f
                echo
                read -rp "Pulsa Enter para volver al menú de logs..." _
                ;;
            4)
                break
                ;;
            *)
                echo "Opción no válida"
                read -rp "Pulsa ENTER para continuar..." _
                ;;
        esac
    done
}

menu_utilidades_sistema() {
    while true; do
        clear
        echo "=== UTILIDADES DEL SISTEMA ==="
        echo "1) Ver uso del sistema y recursos"
        echo "2) Ver total de datos en base de datos"
        echo "3) Consultas y búsquedas en base de datos"
        echo "4) Reiniciar todos los servicios TattileSender"
        echo "5) Ver logs en tiempo real de servicios"
        echo "6) Volver al menú principal"
        read -rp "Selecciona una opción: " opt
        case "$opt" in
            1)
                mostrar_uso_sistema
                ;;
            2)
                mostrar_estadisticas_bd
                ;;
            3)
                menu_consultas_bd
                ;;
            4)
                reiniciar_servicios_tattile
                ;;
            5)
                ver_logs_tiempo_real
                ;;
            6)
                clear
                break
                ;;
            *)
                echo "Opción no válida"
                ;;
        esac
    done
}

while true; do
    clear
    echo "TattileSender - Ajustes"
    echo "1) Añadir datos"
    echo "2) Asignar relaciones"
    echo "3) Eliminar datos"
    echo "4) Modificar datos"
    echo "5) Utilidades del sistema"
    echo "0) Salir"
    read -rp "Seleccione una opción: " main_option
    case $main_option in
        1)
            show_add_menu
            ;;
        2)
            show_assign_menu
            ;;
        3)
            show_delete_menu
            ;;
        4)
            show_update_menu
            ;;
        5)
            menu_utilidades_sistema
            ;;
        0)
            exit 0
            ;;
        *)
            echo "Opción no válida"
            read -rp "Pulsa ENTER para continuar..." _
            ;;
    esac

done
