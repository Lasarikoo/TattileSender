"""CLI administrativa para operaciones de borrado y limpieza."""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from app.admin import cleanup
from app.config import settings
from app.models import SessionLocal

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Herramientas administrativas")
    subparsers = parser.add_subparsers(dest="command", required=True)

    camera_parser = subparsers.add_parser("delete-camera", help="Eliminar una cámara")
    camera_group = camera_parser.add_mutually_exclusive_group(required=True)
    camera_group.add_argument("--id", dest="camera_id", help="ID de la cámara")
    camera_group.add_argument(
        "--serial-number", dest="serial_number", help="Número de serie de la cámara"
    )
    camera_parser.add_argument(
        "--keep-readings",
        action="store_true",
        help="Conserva lecturas asociadas (no recomendado)",
    )
    camera_parser.add_argument(
        "--keep-images",
        action="store_true",
        help="Conserva las imágenes de las lecturas",
    )
    camera_parser.add_argument(
        "--keep-queue",
        action="store_true",
        help="Conserva mensajes en cola asociados a la cámara",
    )

    municipality_parser = subparsers.add_parser(
        "delete-municipality", help="Eliminar un municipio"
    )
    municipality_group = municipality_parser.add_mutually_exclusive_group(required=True)
    municipality_group.add_argument("--id", dest="municipality_id", help="ID del municipio")
    municipality_group.add_argument(
        "--name", dest="municipality_name", help="Nombre del municipio"
    )
    municipality_parser.add_argument(
        "--no-cascade",
        action="store_true",
        help="Impide borrar cámaras y lecturas asociadas",
    )

    certificate_parser = subparsers.add_parser(
        "delete-certificate", help="Eliminar un certificado"
    )
    certificate_group = certificate_parser.add_mutually_exclusive_group(required=True)
    certificate_group.add_argument("--id", dest="certificate_id", help="ID del certificado")
    certificate_group.add_argument(
        "--alias", dest="certificate_alias", help="Alias del certificado"
    )
    certificate_group.add_argument(
        "--name", dest="certificate_name", help="Nombre del certificado"
    )
    certificate_parser.add_argument(
        "--force", action="store_true", help="Forzar borrado si está en uso"
    )

    endpoint_parser = subparsers.add_parser("delete-endpoint", help="Eliminar un endpoint")
    endpoint_group = endpoint_parser.add_mutually_exclusive_group(required=True)
    endpoint_group.add_argument("--id", dest="endpoint_id", help="ID del endpoint")
    endpoint_group.add_argument("--name", dest="endpoint_name", help="Nombre del endpoint")
    endpoint_parser.add_argument(
        "--force", action="store_true", help="Forzar borrado si está en uso"
    )

    wipe_readings_parser = subparsers.add_parser(
        "wipe-readings", help="Eliminar todas las lecturas"
    )
    wipe_readings_parser.add_argument(
        "--keep-images", action="store_true", help="Conserva las imágenes físicas"
    )
    wipe_readings_parser.add_argument(
        "--keep-queue", action="store_true", help="Conserva la cola de mensajes"
    )

    subparsers.add_parser("wipe-queue", help="Vaciar la cola de mensajes")
    subparsers.add_parser("wipe-images", help="Borrar todas las imágenes físicas")
    subparsers.add_parser("full-wipe", help="Lecturas + cola + imágenes")

    return parser.parse_args(argv)


def _open_session():
    session = SessionLocal()
    session.expire_on_commit = False
    return session


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    session = None
    try:
        if args.command in {
            "delete-camera",
            "delete-municipality",
            "delete-certificate",
            "delete-endpoint",
            "wipe-readings",
            "wipe-queue",
            "wipe-images",
            "full-wipe",
        }:
            session = _open_session()

        if args.command == "delete-camera":
            identifier = args.camera_id or args.serial_number
            summary = cleanup.delete_camera(
                session,
                identifier,
                delete_readings=not args.keep_readings,
                delete_images=not args.keep_images,
                delete_queue=not args.keep_queue,
            )
            print(
                "Cámara eliminada: {camera}. Lecturas: {readings}, "
                "mensajes: {messages}, imágenes: {images}.".format(**summary)
            )
        elif args.command == "delete-municipality":
            identifier = args.municipality_id or args.municipality_name
            summary = cleanup.delete_municipality(
                session, identifier, cascade=not args.no_cascade
            )
            print(
                "Municipio '{municipality}' eliminado. Cámaras: {cameras}, "
                "lecturas: {readings}, mensajes: {messages}, imágenes: {images}.".format(
                    **summary
                )
            )
        elif args.command == "delete-certificate":
            identifier = (
                args.certificate_id or args.certificate_alias or args.certificate_name
            )
            summary = cleanup.delete_certificate(session, identifier, force=args.force)
            print(
                "Certificado '{certificate}' eliminado. Cámaras desvinculadas: "
                f"{summary['unlinked_cameras']}."
            )
        elif args.command == "delete-endpoint":
            identifier = args.endpoint_id or args.endpoint_name
            summary = cleanup.delete_endpoint(session, identifier, force=args.force)
            print(
                "Endpoint '{endpoint}' eliminado. Cámaras desvinculadas: {unlinked_cameras}. "
                "Municipios desvinculados: {unlinked_municipalities}.".format(**summary)
            )
        elif args.command == "wipe-readings":
            summary = cleanup.wipe_all_readings(
                session,
                delete_images=not args.keep_images,
                delete_queue=not args.keep_queue,
            )
            print(
                "Se han eliminado {readings} lecturas, {messages} mensajes y "
                "{images} imágenes.".format(**summary)
            )
        elif args.command == "wipe-queue":
            deleted = cleanup.wipe_all_queue(session)
            print(f"Se han eliminado {deleted} mensajes de la cola.")
        elif args.command == "wipe-images":
            deleted = cleanup.wipe_all_images_and_unset(session)
            print(
                f"Se han eliminado {deleted} imágenes físicas en {settings.IMAGES_DIR}."
            )
        elif args.command == "full-wipe":
            summary = cleanup.full_wipe(session)
            print(
                "Limpieza total completada. Lecturas: {readings}, mensajes: {messages}, "
                "imágenes: {images}.".format(**summary)
            )
        else:
            print("Comando no reconocido")
            return 1
    except Exception as exc:  # pragma: no cover - CLI defensivo
        logger.error("Error durante la operación: %s", exc)
        return 1
    finally:
        if session:
            session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
