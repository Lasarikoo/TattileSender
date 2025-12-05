#!/usr/bin/env bash
# Panel interactivo para poblar datos básicos en TattileSender.

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$PROJECT_DIR/.venv/bin/activate"

show_add_menu() {
    while true; do
        clear
        echo "Añadir datos"
        echo "1) Añadir municipios"
        echo "2) Añadir cámaras"
        echo "3) Añadir endpoints"
        echo "4) Añadir certificados"
        echo "5) Descomprimir certificado PFX y asignar a municipio"
        echo "6) Volver al menú principal"
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
                python -m app.scripts.add_certificate
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            5)
                python -m app.scripts.import_certificate_from_pfx
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            6)
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
        echo "6) Limpiar TODA la cola de mensajes"
        echo "7) Limpiar TODAS las imágenes"
        echo "8) Limpieza total (lecturas + cola + imágenes)"
        echo "0) Volver"
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
                read -rp "Pulsa ENTER para continuar..." _
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
                read -rp "Pulsa ENTER para continuar..." _
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
                read -rp "Pulsa ENTER para continuar..." _
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
            6)
                read -rp "Vas a limpiar TODA la cola de mensajes. ¿Seguro? [s/N]: " confirm
                if [[ "$confirm" == "s" || "$confirm" == "S" ]]; then
                    python -m app.admin.cli wipe-queue
                else
                    echo "Operación cancelada."
                fi
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            7)
                read -rp "Vas a borrar TODAS las imágenes físicas. ¿Seguro? [s/N]: " confirm
                if [[ "$confirm" == "s" || "$confirm" == "S" ]]; then
                    python -m app.admin.cli wipe-images
                else
                    echo "Operación cancelada."
                fi
                read -rp "Pulsa ENTER para continuar..." _
                ;;
            8)
                read -rp "Vas a borrar lecturas, cola e imágenes. ¿Seguro? [s/N]: " confirm
                if [[ "$confirm" == "s" || "$confirm" == "S" ]]; then
                    python -m app.admin.cli full-wipe
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
