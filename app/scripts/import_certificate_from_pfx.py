"""Importa un certificado PFX y lo asigna a un municipio.

Uso: python -m app.scripts.import_certificate_from_pfx
"""
from __future__ import annotations

import os
import subprocess
from getpass import getpass

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Certificate, Municipality, SessionLocal


def _list_municipalities(session: Session) -> list[Municipality]:
    municipalities = session.query(Municipality).order_by(Municipality.id).all()
    if not municipalities:
        print("[CERT IMPORT][ERROR] No hay municipios dados de alta.")
    else:
        print("Municipios disponibles:")
        for municipality in municipalities:
            print(f"- {municipality.id}: {municipality.name}")
    return municipalities


def _extract_pfx_to_privpub(*, pfx_path: str, pfx_password: str, target_dir: str) -> str | None:
    privpub_path = os.path.join(target_dir, "privpub.pem")
    cmd = [
        "openssl",
        "pkcs12",
        "-in",
        pfx_path,
        "-nodes",
        "-out",
        privpub_path,
        "-passin",
        f"pass:{pfx_password}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("[CERT IMPORT][ERROR] Fallo al ejecutar openssl pkcs12:")
        print(result.stderr)
        return None
    return privpub_path


def _split_pems(privpub_path: str, target_dir: str) -> tuple[str, str] | None:
    key_path = os.path.join(target_dir, "key.pem")
    cert_path = os.path.join(target_dir, "cert.pem")

    with open(privpub_path, "r") as f:
        privpub_content = f.read()

    with open(key_path, "w") as f:
        f.write(privpub_content)

    blocks = privpub_content.split("-----BEGIN CERTIFICATE-----")
    cert_blocks = [b for b in blocks if "-----END CERTIFICATE-----" in b]
    if not cert_blocks:
        print("[CERT IMPORT][ERROR] No se encontraron certificados en privpub.pem")
        return None

    last_cert_block = "-----BEGIN CERTIFICATE-----" + cert_blocks[-1]
    if "-----END CERTIFICATE-----" not in last_cert_block:
        print("[CERT IMPORT][ERROR] Último bloque de certificado está incompleto.")
        return None

    with open(cert_path, "w") as f:
        f.write(last_cert_block)

    return key_path, cert_path


def main() -> None:
    print("[CERT IMPORT] Importar certificado PFX y asignarlo a un municipio")
    pfx_path = input("Ruta del fichero .pfx: ").strip()
    cert_name = input("Nombre interno para el certificado (alias): ").strip()
    pfx_password = getpass("Contraseña del .pfx: ")

    if not os.path.isfile(pfx_path):
        print("[CERT IMPORT][ERROR] El fichero .pfx no existe o no es accesible.")
        return

    base_certs_dir = settings.CERTS_DIR
    os.makedirs(base_certs_dir, exist_ok=True)

    slug = cert_name.lower().replace(" ", "_")
    target_dir = os.path.join(base_certs_dir, slug)
    os.makedirs(target_dir, exist_ok=True)

    privpub_path = _extract_pfx_to_privpub(
        pfx_path=pfx_path, pfx_password=pfx_password, target_dir=target_dir
    )
    if privpub_path is None:
        return

    split_result = _split_pems(privpub_path, target_dir)
    if split_result is None:
        return

    key_path, cert_path = split_result
    if not (os.path.isfile(key_path) and os.path.isfile(cert_path)):
        print("[CERT IMPORT][ERROR] No se pudieron generar key.pem o cert.pem correctamente.")
        return

    session = SessionLocal()
    try:
        municipalities = _list_municipalities(session)
        if not municipalities:
            return

        mun_id_str = input("ID del municipio al que asignar el certificado: ").strip()
        try:
            mun_id = int(mun_id_str)
        except ValueError:
            print("[CERT IMPORT][ERROR] ID de municipio inválido.")
            return

        municipality = session.get(Municipality, mun_id)
        if municipality is None:
            print("[CERT IMPORT][ERROR] Municipio no encontrado.")
            return

        rel_cert_path = os.path.join(slug, "cert.pem")
        rel_key_path = os.path.join(slug, "key.pem")

        cert = Certificate(
            name=cert_name,
            path=rel_cert_path,
            key_path=rel_key_path,
            type="PEM_PAIR",
            active=True,
        )
        session.add(cert)
        session.flush()

        municipality.certificate_id = cert.id
        session.add(municipality)
        session.commit()

        print(f"[CERT IMPORT] Certificado '{cert_name}' importado correctamente.")
        print(f"[CERT IMPORT] Asignado al municipio '{municipality.name}' (id={municipality.id}).")
        print(f"[CERT IMPORT] cert.pem: {cert_path}")
        print(f"[CERT IMPORT] key.pem:  {key_path}")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        print(f"[CERT IMPORT][ERROR] {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
