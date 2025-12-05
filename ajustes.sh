#!/usr/bin/env bash
# Panel interactivo para poblar datos básicos en TattileSender.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$PROJECT_DIR/.venv/bin/activate"

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

while true; do
    clear
    echo "TattileSender - Ajustes"
    echo "1) Añadir datos"
    echo "2) Asignar relaciones"
    echo "3) Eliminar datos"
    echo "4) Modificar datos"
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
        0)
            exit 0
            ;;
        *)
            echo "Opción no válida"
            read -rp "Pulsa ENTER para continuar..." _
            ;;
    esac

done
