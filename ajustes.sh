#!/usr/bin/env bash
# Panel interactivo para poblar datos básicos en TattileSender.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$PROJECT_DIR/.venv/bin/activate"

show_logo() {
    clear
    echo "========================================="
    echo "   ____      _   _   _ _ _      _____    "
    echo "  |  _ \\ ___| |_| |_(_) | |_   |___ /    "
    echo "  | |_) / _ \\ __| __| | | __|    |_ \\    "
    echo "  |  _ <  __/ |_| |_| | | |_    ___) |   "
    echo "  |_| \\_\\___|\\__|\\__|_|_|\\__|  |____/    "
    echo "                                         "
    echo "         TattileSender - Ajustes         "
    echo "========================================="
    echo
}

pause_screen() {
    read -rp "Pulsa ENTER para continuar..." _
}

handle_delete_menu() {
    while true; do
        clear
        echo "=== Menú eliminar datos ==="
        echo "[1] Eliminar cámara"
        echo "[2] Eliminar municipio"
        echo "[3] Eliminar certificado"
        echo "[4] Eliminar endpoint"
        echo "[5] Limpiar TODAS las lecturas"
        echo "[0] Volver"
        read -rp "Seleccione una opción: " option
        case $option in
            1)
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
                pause_screen
                ;;
            2)
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
                pause_screen
                ;;
            3)
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
                pause_screen
                ;;
            4)
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
                pause_screen
                ;;
            5)
                read -rp "Vas a eliminar TODAS las lecturas. ¿Seguro? [s/N]: " confirm
                if [[ "$confirm" == "s" || "$confirm" == "S" ]]; then
                    python -m app.admin.cli wipe-readings
                else
                    echo "Operación cancelada."
                fi
                pause_screen
                ;;
            0)
                break
                ;;
            *)
                echo "Opción no válida"
                pause_screen
                ;;
        esac
    done
}

handle_pfx_import() {
    CERTS_DIR=$(python - <<'PY'
from app.config import settings
print(settings.certs_dir)
PY
)

    if [ -z "$CERTS_DIR" ]; then
        CERTS_DIR="./certs"
    fi

    mapfile -t PFX_FILES < <(find "$CERTS_DIR" -maxdepth 1 -type f \( -iname "*.pfx" -o -iname "*.p12" \) | sort)

    if [ ${#PFX_FILES[@]} -eq 0 ]; then
        echo "[ERROR] No se han encontrado certificados PFX en $CERTS_DIR."
        pause_screen
        return
    fi

    echo "Certificados PFX encontrados en $CERTS_DIR:"
    idx=1
    for f in "${PFX_FILES[@]}"; do
        echo "  $idx) $f"
        idx=$((idx + 1))
    done

    read -rp "Selecciona un certificado por número: " selected
    if ! [[ "$selected" =~ ^[0-9]+$ ]] || [ "$selected" -lt 1 ] || [ "$selected" -gt "${#PFX_FILES[@]}" ]; then
        echo "Selección no válida."
        pause_screen
        return
    fi

    PFX_PATH="${PFX_FILES[$((selected - 1))]}"
    read -rp "Alias interno del certificado: " PFX_ALIAS
    read -s -rp "Introduce la contraseña del PFX: " PFX_PASS
    echo

    python -m app.scripts.import_certificate_from_pfx --pfx-path "$PFX_PATH" --alias "$PFX_ALIAS" --password "$PFX_PASS"
    pause_screen
}

while true; do
    show_logo
    echo "1) Añadir cámaras"
    echo "2) Añadir municipios"
    echo "3) Añadir endpoints"
    echo "4) Descomprimir certificado PFX y asignar a municipio"
    echo "5) Eliminar datos"
    echo "0) Salir"
    read -rp "Seleccione una opción: " main_option
    case $main_option in
        1)
            python -m app.scripts.add_camera
            pause_screen
            ;;
        2)
            python -m app.scripts.add_municipality
            pause_screen
            ;;
        3)
            python -m app.scripts.add_endpoint
            pause_screen
            ;;
        4)
            handle_pfx_import
            ;;
        5)
            handle_delete_menu
            ;;
        0)
            exit 0
            ;;
        *)
            echo "Opción no válida"
            pause_screen
            ;;
    esac

done
