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

while true; do
    clear
    echo "TattileSender - Ajustes"
    echo "1) Añadir datos"
    echo "2) Asignar relaciones"
    echo "3) Salir"
    read -rp "Seleccione una opción: " main_option
    case $main_option in
        1)
            show_add_menu
            ;;
        2)
            show_assign_menu
            ;;
        3)
            exit 0
            ;;
        *)
            echo "Opción no válida"
            read -rp "Pulsa ENTER para continuar..." _
            ;;
    esac

done
