"""Importa un certificado PFX y lo asigna a un municipio.

Uso: python -m app.scripts.import_certificate_from_pfx
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from getpass import getpass

from sqlalchemy.orm import Session

from app.models import Certificate, Municipality, SessionLocal

BASE_CERTS_DIR = "/root/tattilesender/certs"


def _list_municipalities(session: Session) -> list[Municipality]:
    municipalities = session.query(Municipality).order_by(Municipality.id).all()
    if not municipalities:
        print("[CERT IMPORT][ERROR] No hay municipios dados de alta.")
    else:
        print("Municipios disponibles:")
        for municipality in municipalities:
            print(f"- {municipality.id}: {municipality.name}")
    return municipalities


def _detect_pkcs12_cmd() -> list[str]:
    """Detecta si la versión de OpenSSL necesita el flag ``-legacy``."""

    result = subprocess.run(
        ["openssl", "pkcs12", "-help"], capture_output=True, text=True, check=False
    )
    output = (result.stdout or "") + (result.stderr or "")
    if "-legacy" in output:
        return ["openssl", "pkcs12", "-legacy"]
    return ["openssl", "pkcs12"]


def _ensure_cert_dir(alias: str) -> str:
    alias_dir = os.path.join(BASE_CERTS_DIR, alias)
    os.makedirs(alias_dir, exist_ok=True)
    return alias_dir


def _copy_pfx(pfx_path: str, target_dir: str) -> str:
    dest_path = os.path.join(target_dir, os.path.basename(pfx_path))
    shutil.copy2(pfx_path, dest_path)
    return dest_path


def _extract_key(pkcs12_cmd: list[str], pfx_path: str, password: str, target_dir: str) -> str | None:
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
        return None
    return key_path


def _extract_privpub(
    pkcs12_cmd: list[str], pfx_path: str, password: str, target_dir: str
) -> str | None:
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
        return None
    return privpub_path


def _extract_last_cert_from_chain(privpub_path: str, target_dir: str) -> str | None:
    with open(privpub_path, "r", encoding="utf-8") as handler:
        content = handler.read()

    matches = re.findall(
        r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
        content,
        flags=re.DOTALL,
    )
    if not matches:
        print("[CERT IMPORT][ERROR] No se encontraron certificados en privpub.pem")
        return None

    public_cert = matches[-1]
    public_cert_path = os.path.join(target_dir, "cert_mossos_public.pem")
    with open(public_cert_path, "w", encoding="utf-8") as handler:
        handler.write(public_cert)
    return public_cert_path


def _validate_file(path: str, label: str) -> bool:
    if not path or not os.path.isfile(path) or os.path.getsize(path) == 0:
        print(f"[CERT IMPORT][ERROR] No se pudo generar {label}")
        return False
    return True


def _choose_municipality(session: Session) -> Municipality | None:
    municipalities = _list_municipalities(session)
    if not municipalities:
        return None

    mun_id_str = input("ID del municipio al que asignar el certificado: ").strip()
    try:
        mun_id = int(mun_id_str)
    except ValueError:
        print("[CERT IMPORT][ERROR] ID de municipio inválido.")
        return None

    municipality = session.get(Municipality, mun_id)
    if municipality is None:
        print("[CERT IMPORT][ERROR] Municipio no encontrado.")
        return None
    return municipality


def main() -> None:
    print("[CERT IMPORT] Importar certificado PFX y asignarlo a un municipio")

    pfx_path = input("Ruta del fichero .pfx: ").strip()
    alias = input("Alias interno del certificado (ej. \"LaGranada\"): ").strip()
    pfx_password = getpass("Contraseña del .pfx: ")

    if not os.path.isfile(pfx_path):
        print("[CERT IMPORT][ERROR] El fichero .pfx no existe o no es accesible.")
        return
    if not alias:
        print("[CERT IMPORT][ERROR] El alias es obligatorio.")
        return

    alias_slug = alias.replace(" ", "_")
    target_dir = _ensure_cert_dir(alias_slug)
    copied_pfx_path = _copy_pfx(pfx_path, target_dir)

    pkcs12_cmd = _detect_pkcs12_cmd()
    priv_key_path = _extract_key(pkcs12_cmd, copied_pfx_path, pfx_password, target_dir)
    privpub_path = _extract_privpub(pkcs12_cmd, copied_pfx_path, pfx_password, target_dir)
    public_cert_path = None
    if privpub_path:
        public_cert_path = _extract_last_cert_from_chain(privpub_path, target_dir)

    if not all(
        [
            _validate_file(priv_key_path or "", "key.pem"),
            _validate_file(privpub_path or "", "privpub.pem"),
            _validate_file(public_cert_path or "", "cert_mossos_public.pem"),
        ]
    ):
        return

    session = SessionLocal()
    try:
        municipality = _choose_municipality(session)
        if municipality is None:
            return

        if municipality.certificate:
            existing = municipality.certificate
            answer = input(
                "El municipio ya tiene un certificado asignado. ¿Desea reemplazarlo? (s/N): "
            ).strip()
            if answer.lower() not in {"s", "si", "sí", "y", "yes"}:
                print("[CERT IMPORT] Operación cancelada por el usuario.")
                return

        certificate = Certificate(
            alias=alias,
            name=alias,
            municipality_id=municipality.id,
            path=public_cert_path,
            client_cert_path=public_cert_path,
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
        session.flush()

        session.refresh(municipality)
        session.commit()

        print("[CERT IMPORT][OK] Certificado importado correctamente.")
        print(f"[CERT IMPORT] Alias: {alias}")
        print(f"[CERT IMPORT] pfx_path: {copied_pfx_path}")
        print(f"[CERT IMPORT] key.pem: {priv_key_path}")
        print(f"[CERT IMPORT] privpub.pem: {privpub_path}")
        print(f"[CERT IMPORT] cert_mossos_public.pem: {public_cert_path}")
        print(f"[CERT IMPORT] Asignado al municipio '{municipality.name}' (id={municipality.id}).")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        print(f"[CERT IMPORT][ERROR] {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
