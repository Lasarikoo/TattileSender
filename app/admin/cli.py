"""CLI administrativa para operaciones de borrado y limpieza."""
from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.admin import cleanup
from app.config import settings
from app.models import Camera, Certificate, Endpoint, Municipality, SessionLocal

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

    subparsers.add_parser("list-cameras", help="Listar cámaras disponibles")
    subparsers.add_parser("list-municipalities", help="Listar municipios disponibles")
    subparsers.add_parser("list-certificates", help="Listar certificados disponibles")
    subparsers.add_parser("list-endpoints", help="Listar endpoints disponibles")

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

    extract_cert_parser = subparsers.add_parser(
        "extract-cert", help="Descomprimir certificado PFX y asignarlo a un municipio"
    )
    extract_cert_parser.add_argument(
        "--pfx-path", required=True, help="Ruta del fichero PFX/P12 a importar"
    )
    extract_cert_parser.add_argument(
        "--password", dest="pfx_password", required=True, help="Contraseña del PFX"
    )
    extract_cert_parser.add_argument("--alias", help="Alias interno del certificado")
    extract_cert_parser.add_argument(
        "--municipality-id", type=int, help="ID del municipio al que asignar"
    )

    return parser.parse_args(argv)


def _open_session():
    session = SessionLocal()
    session.expire_on_commit = False
    return session


def _list_cameras(session):
    print("ID | device_sn | nombre | municipio")
    cameras = (
        session.query(Camera)
        .outerjoin(Municipality, Camera.municipality_id == Municipality.id)
        .order_by(Camera.id)
        .all()
    )
    for camera in cameras:
        municipality_name = camera.municipality.name if camera.municipality else "-"
        description = camera.description or camera.codigo_lector
        print(
            f"{camera.id} | {camera.serial_number} | {description} | {municipality_name}"
        )


def _list_municipalities(session):
    print("ID | nombre | código")
    municipalities = session.query(Municipality).order_by(Municipality.id).all()
    for municipality in municipalities:
        code = municipality.code or "-"
        print(f"{municipality.id} | {municipality.name} | {code}")


def _list_certificates(session):
    print("ID | nombre | tipo | activo")
    certificates = session.query(Certificate).order_by(Certificate.id).all()
    for certificate in certificates:
        name = certificate.name or certificate.alias or "-"
        active = str(bool(certificate.active)).lower()
        cert_type = certificate.type or "-"
        print(f"{certificate.id} | {name} | {cert_type} | {active}")


def _list_endpoints(session):
    print("ID | nombre | URL")
    endpoints = session.query(Endpoint).order_by(Endpoint.id).all()
    for endpoint in endpoints:
        print(f"{endpoint.id} | {endpoint.name} | {endpoint.url}")


def _detect_pkcs12_cmd() -> list[str]:
    result = subprocess.run(
        ["openssl", "pkcs12", "-help"], capture_output=True, text=True, check=False
    )
    output = (result.stdout or "") + (result.stderr or "")
    if "-legacy" in output:
        return ["openssl", "pkcs12", "-legacy"]
    return ["openssl", "pkcs12"]


def _ensure_cert_dir(alias: str) -> str:
    certs_dir = settings.certs_dir or "./certs"
    alias_dir = os.path.join(certs_dir, alias)
    os.makedirs(alias_dir, exist_ok=True)
    return alias_dir


def _copy_pfx(pfx_path: str, target_dir: str) -> str:
    dest_path = os.path.join(target_dir, os.path.basename(pfx_path))
    shutil.copy2(pfx_path, dest_path)
    return dest_path


def _extract_key(pkcs12_cmd: list[str], pfx_path: str, password: str, target_dir: str) -> str:
    key_path = os.path.join(target_dir, "key.pem")
    cmd = pkcs12_cmd + [
        "-in",
        pfx_path,
        "-nocerts",
        "-out",
        key_path,
        "-nodes",
        "-passin",
        f"pass:{password}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("[CERT IMPORT][ERROR] Fallo al extraer key.pem:")
        print(result.stderr)
        raise RuntimeError("No se pudo extraer key.pem")
    return key_path


def _extract_privpub(
    pkcs12_cmd: list[str], pfx_path: str, password: str, target_dir: str
) -> str:
    privpub_path = os.path.join(target_dir, "privpub.pem")
    cmd = pkcs12_cmd + [
        "-in",
        pfx_path,
        "-out",
        privpub_path,
        "-passin",
        f"pass:{password}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("[CERT IMPORT][ERROR] Fallo al extraer privpub.pem:")
        print(result.stderr)
        raise RuntimeError("No se pudo extraer privpub.pem")
    return privpub_path


def _extract_last_cert_from_chain(privpub_path: str, target_dir: str) -> str:
    with open(privpub_path, "r", encoding="utf-8") as handler:
        content = handler.read()

    matches = re.findall(
        r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
        content,
        flags=re.DOTALL,
    )
    if not matches:
        raise RuntimeError("No se encontraron certificados en privpub.pem")

    public_cert = matches[-1]
    public_cert_path = os.path.join(target_dir, "cert_mossos_public.pem")
    with open(public_cert_path, "w", encoding="utf-8") as handler:
        handler.write(public_cert)
    return public_cert_path


def _validate_file(path: str, label: str) -> None:
    if not path or not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise RuntimeError(f"No se pudo generar {label}")


def _choose_municipality(session, municipality_id: int | None) -> Municipality | None:
    if municipality_id is not None:
        municipality = session.get(Municipality, municipality_id)
        if municipality is None:
            print(f"[CERT IMPORT][ERROR] Municipio con ID {municipality_id} no encontrado.")
        return municipality

    municipalities = session.query(Municipality).order_by(Municipality.id).all()
    if not municipalities:
        print("[CERT IMPORT][ERROR] No hay municipios dados de alta.")
        return None

    print("Municipios disponibles:")
    for municipality in municipalities:
        print(f"- {municipality.id}: {municipality.name}")

    try:
        mun_id = int(input("ID del municipio al que asignar el certificado: ").strip())
    except ValueError:
        print("[CERT IMPORT][ERROR] ID de municipio inválido.")
        return None

    municipality = session.get(Municipality, mun_id)
    if municipality is None:
        print("[CERT IMPORT][ERROR] Municipio no encontrado.")
    return municipality


def _execute(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)
    session = None
    try:
        if args.command in {
            "delete-camera",
            "delete-municipality",
            "delete-certificate",
            "delete-endpoint",
            "list-cameras",
            "list-municipalities",
            "list-certificates",
            "list-endpoints",
            "wipe-readings",
            "wipe-queue",
            "wipe-images",
            "full-wipe",
            "extract-cert",
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
        elif args.command == "list-cameras":
            _list_cameras(session)
        elif args.command == "list-municipalities":
            _list_municipalities(session)
        elif args.command == "list-certificates":
            _list_certificates(session)
        elif args.command == "list-endpoints":
            _list_endpoints(session)
        elif args.command == "extract-cert":
            if not os.path.isfile(args.pfx_path):
                print(
                    f"[CERT IMPORT][ERROR] El fichero {args.pfx_path} no existe o no es accesible."
                )
                return 1

            alias = args.alias or os.path.splitext(os.path.basename(args.pfx_path))[0]
            if not alias:
                print("[CERT IMPORT][ERROR] El alias es obligatorio.")
                return 1

            alias_slug = alias.replace(" ", "_")
            municipality = _choose_municipality(session, args.municipality_id)
            if municipality is None:
                return 1

            if municipality.certificate:
                answer = input(
                    "El municipio ya tiene un certificado asignado. ¿Desea reemplazarlo? (s/N): "
                ).strip()
                if answer.lower() not in {"s", "si", "sí", "y", "yes"}:
                    print("[CERT IMPORT] Operación cancelada por el usuario.")
                    return 1

            target_dir = _ensure_cert_dir(alias_slug)
            copied_pfx_path = _copy_pfx(args.pfx_path, target_dir)

            pkcs12_cmd = _detect_pkcs12_cmd()
            try:
                priv_key_path = _extract_key(pkcs12_cmd, copied_pfx_path, args.pfx_password, target_dir)
                privpub_path = _extract_privpub(pkcs12_cmd, copied_pfx_path, args.pfx_password, target_dir)
                public_cert_path = _extract_last_cert_from_chain(privpub_path, target_dir)
                _validate_file(priv_key_path, "key.pem")
                _validate_file(privpub_path, "privpub.pem")
                _validate_file(public_cert_path, "cert_mossos_public.pem")
            except RuntimeError as exc:
                session.rollback()
                print(f"[CERT IMPORT][ERROR] {exc}")
                return 1

            certificate = Certificate(
                alias=alias,
                name=alias,
                municipality_id=municipality.id,
                path=public_cert_path,
                public_cert_path=public_cert_path,
                key_path=priv_key_path,
                privpub_path=privpub_path,
                pfx_path=copied_pfx_path,
                type="PEM_PAIR",
                active=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(certificate)
            session.commit()

            print("[CERT IMPORT][OK] Certificado importado correctamente.")
            print(f"[CERT IMPORT] Alias: {alias}")
            print(f"[CERT IMPORT] pfx_path: {copied_pfx_path}")
            print(f"[CERT IMPORT] key.pem: {priv_key_path}")
            print(f"[CERT IMPORT] privpub.pem: {privpub_path}")
            print(f"[CERT IMPORT] cert_mossos_public.pem: {public_cert_path}")
            print(
                f"[CERT IMPORT] Asignado al municipio '{municipality.name}' (id={municipality.id})."
            )
        elif args.command == "wipe-readings":
            try:
                summary = cleanup.wipe_all_readings(
                    session,
                    delete_images=not args.keep_images,
                    delete_queue=not args.keep_queue,
                )
            except StaleDataError as exc:
                logger.error(
                    "[CLI][ERROR] Se ha producido un StaleDataError durante la "
                    "limpieza de lecturas: %s",
                    exc,
                )
                print(
                    "La limpieza de lecturas ha fallado por un conflicto interno "
                    "de sesión (StaleDataError)."
                )
                return 1
            except (IntegrityError, ValueError) as exc:
                logger.error(
                    "[CLI][ERROR] No se han podido borrar las lecturas: %s", exc
                )
                print(
                    "No se han podido borrar las lecturas porque existen referencias "
                    "en la cola de mensajes. Use --keep-queue para conservarla o "
                    "ejecute primero la limpieza de la cola."
                )
                return 1

            readings = summary.get("readings") or 0
            messages = summary.get("messages") or 0
            images = summary.get("images") or 0
            print(
                "Se han eliminado {readings} lecturas, {messages} mensajes y "
                "{images} imágenes.".format(
                    readings=readings, messages=messages, images=images
                )
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
            readings = summary.get("readings") or 0
            messages = summary.get("messages") or 0
            images = summary.get("images") or 0
            print(
                "Limpieza total completada. Lecturas: {readings}, mensajes: {messages}, "
                "imágenes: {images}.".format(
                    readings=readings, messages=messages, images=images
                )
            )
        else:
            print("Comando no reconocido")
            return 1
    finally:
        if session:
            session.close()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    try:
        return _execute(argv)
    except Exception as exc:  # pragma: no cover - CLI defensivo
        logger.error(
            "[CLI][ERROR] Error inesperado en CLI de administración: %s", exc
        )
        traceback.print_exc()
        print("[CLI][ERROR] La operación de limpieza ha fallado. Revisa la traza anterior.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
