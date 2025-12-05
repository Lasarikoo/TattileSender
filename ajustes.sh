#!/usr/bin/env bash
# Panel interactivo para poblar datos básicos en TattileSender.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$PROJECT_DIR/.venv/bin/activate"

show_logo() {
    clear
    echo "=============================================="
    echo " _________        _     _    _   __          ______                        __                "
    echo "|  _   _  |      / |_  / |_ (_) [  |       .' ____ \\                      |  ]               "
    echo "|_/ | | \\_|,--. `| |-'`| |-'__   | | .---. | (___ \\_| .---.  _ .--.   .--.| | .---.  _ .--.  "
    echo "    | |   `'_\\ : | |   | | [  |  | |/ /__\\ _.____`. / /__\\[ `.-. |/ /'`\\' |/ /__\\[ `/'`\\] "
    echo "   _| |_  // | |,| |,  | |, | |  | || \\__.,| \\____) || \\__., | | | || \\__/  || \\__., | |     "
    echo "  |_____| \\-;__/\\__/  \\__/[___][___]'.__.' \\______.' '.__.'[___||__]'.__.;__]'.__.'[___]    "
    echo
    echo "          TattileSender - Ajustes             "
    echo "=============================================="
    echo
}

anadir_camaras() {
    python -m app.scripts.add_camera
    read -p "Pulsa ENTER para continuar..." _
}

anadir_municipios() {
    python -m app.scripts.add_municipality
    read -p "Pulsa ENTER para continuar..." _
}

anadir_endpoints() {
    python -m app.scripts.add_endpoint
    read -p "Pulsa ENTER para continuar..." _
}

descomprimir_certificado_pfx() {
    CERTS_DIR=$(python -c "from app.config import settings; print(settings.certs_dir)" 2>/dev/null)
    if [ -z "$CERTS_DIR" ]; then
        CERTS_DIR="./certs"
    fi

    mapfile -t PFX_FILES < <(find "$CERTS_DIR" -maxdepth 1 -type f \( -iname "*.pfx" -o -iname "*.p12" \) | sort)

    if [ ${#PFX_FILES[@]} -eq 0 ]; then
        echo "No se han encontrado certificados PFX en $CERTS_DIR."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi

    echo "Certificados PFX encontrados en $CERTS_DIR:"
    idx=1
    for f in "${PFX_FILES[@]}"; do
        echo "  $idx) $f"
        idx=$((idx + 1))
    done

    read -p "Selecciona un certificado por número: " selected

    if ! [[ "$selected" =~ ^[0-9]+$ ]] || [ "$selected" -lt 1 ] || [ "$selected" -gt "${#PFX_FILES[@]}" ]; then
        echo "Selección no válida."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi

    PFX_PATH="${PFX_FILES[$((selected - 1))]}"

    read -s -p "Introduce la contraseña del PFX: " PFX_PASS
    echo

    python -m app.admin.cli extract-cert --pfx-path "$PFX_PATH" --password "$PFX_PASS"
    echo "Operación de certificado completada (revisa posibles errores en consola)."
    read -p "Pulsa ENTER para continuar..." _
}

eliminar_camara_interactivo() {
    clear
    echo "=== Eliminar cámara ==="
    echo
    echo "Listado de cámaras:"
    python -m app.admin.cli list-cameras
    echo
    read -p "Introduce el ID de la cámara a eliminar: " CAM_ID
    if [ -z "$CAM_ID" ]; then
        echo "ID no válido."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi

    read -p "Vas a eliminar la cámara con ID $CAM_ID. ¿Seguro? [s/N]: " CONFIRM
    if [ "$CONFIRM" != "s" ] && [ "$CONFIRM" != "S" ]; then
        echo "Operación cancelada."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi

    python -m app.admin.cli delete-camera --id "$CAM_ID"
    read -p "Pulsa ENTER para continuar..." _
}

eliminar_municipio_interactivo() {
    clear
    echo "=== Eliminar municipio ==="
    echo
    echo "Listado de municipios:"
    python -m app.admin.cli list-municipalities
    echo
    read -p "Introduce el ID del municipio a eliminar: " MUNI_ID
    if [ -z "$MUNI_ID" ]; then
        echo "ID no válido."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi

    read -p "Vas a eliminar el municipio con ID $MUNI_ID (posible borrado en cascada). ¿Seguro? [s/N]: " CONFIRM
    if [ "$CONFIRM" != "s" ] && [ "$CONFIRM" != "S" ]; then
        echo "Operación cancelada."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi

    python -m app.admin.cli delete-municipality --id "$MUNI_ID"
    read -p "Pulsa ENTER para continuar..." _
}

eliminar_certificado_interactivo() {
    clear
    echo "=== Eliminar certificado ==="
    echo
    echo "Listado de certificados:"
    python -m app.admin.cli list-certificates
    echo
    read -p "Introduce el ID del certificado a eliminar: " CERT_ID
    if [ -z "$CERT_ID" ]; then
        echo "ID no válido."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi

    read -p "Vas a eliminar el certificado con ID $CERT_ID. ¿Seguro? [s/N]: " CONFIRM
    if [ "$CONFIRM" != "s" ] && [ "$CONFIRM" != "S" ]; then
        echo "Operación cancelada."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi

    python -m app.admin.cli delete-certificate --id "$CERT_ID"
    read -p "Pulsa ENTER para continuar..." _
}

eliminar_endpoint_interactivo() {
    clear
    echo "=== Eliminar endpoint ==="
    echo
    echo "Listado de endpoints:"
    python -m app.admin.cli list-endpoints
    echo
    read -p "Introduce el ID del endpoint a eliminar: " ENDPOINT_ID
    if [ -z "$ENDPOINT_ID" ]; then
        echo "ID no válido."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi

    read -p "Vas a eliminar el endpoint con ID $ENDPOINT_ID. ¿Seguro? [s/N]: " CONFIRM
    if [ "$CONFIRM" != "s" ] && [ "$CONFIRM" != "S" ]; then
        echo "Operación cancelada."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi

    python -m app.admin.cli delete-endpoint --id "$ENDPOINT_ID"
    read -p "Pulsa ENTER para continuar..." _
}

limpiar_lecturas_interactivo() {
    clear
    echo "=== Limpiar TODAS las lecturas ==="
    read -p "Vas a eliminar TODAS las lecturas. ¿Seguro? [s/N]: " CONFIRM
    if [ "$CONFIRM" != "s" ] && [ "$CONFIRM" != "S" ]; then
        echo "Operación cancelada."
        read -p "Pulsa ENTER para continuar..." _
        return
    fi

    python -m app.admin.cli wipe-readings
    read -p "Pulsa ENTER para continuar..." _
}

menu_eliminar_datos() {
    while true; do
        clear
        echo "====== Eliminar datos ======"
        echo "1) Eliminar cámara"
        echo "2) Eliminar municipio"
        echo "3) Eliminar certificado"
        echo "4) Eliminar endpoint"
        echo "5) Limpiar TODAS las lecturas"
        echo "0) Volver"
        echo
        read -p "Seleccione una opción: " SUBOPCION
        case "$SUBOPCION" in
            1)
                eliminar_camara_interactivo
                ;;
            2)
                eliminar_municipio_interactivo
                ;;
            3)
                eliminar_certificado_interactivo
                ;;
            4)
                eliminar_endpoint_interactivo
                ;;
            5)
                limpiar_lecturas_interactivo
                ;;
            0)
                break
                ;;
            *)
                echo "Opción no válida."
                read -p "Pulsa ENTER para continuar..." _
                ;;
        esac
    done
}

while true; do
    show_logo
    echo "1) Añadir cámaras"
    echo "2) Añadir municipios"
    echo "3) Añadir endpoints"
    echo "4) Descomprimir certificado PFX y asignar a municipio"
    echo "5) Eliminar datos"
    echo "0) Salir"
    echo
    read -p "Seleccione una opción: " OPCION
    case "$OPCION" in
        1)
            anadir_camaras
            ;;
        2)
            anadir_municipios
            ;;
        3)
            anadir_endpoints
            ;;
        4)
            descomprimir_certificado_pfx
            ;;
        5)
            menu_eliminar_datos
            ;;
        0)
            echo "Saliendo..."
            exit 0
            ;;
        *)
            echo "Opción no válida."
            read -p "Pulsa ENTER para continuar..." _
            ;;
    esac
done
