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
                python -m app.scripts.add_certificate
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
    echo "2) Salir"
    read -rp "Seleccione una opción: " main_option
    case $main_option in
        1)
            show_add_menu
            ;;
        2)
            exit 0
            ;;
        *)
            echo "Opción no válida"
            read -rp "Pulsa ENTER para continuar..." _
            ;;
    esac

done
