"""Herramientas administrativas para gestión de certificados."""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Certificate, Municipality


@dataclass
class ExtractResult:
    municipality: Municipality
    certificate: Certificate
    key_path: str
    client_path: str
    privpub_path: str | None


def _slugify(value: str) -> str:
    value = value.strip().lower().replace(" ", "_")
    value = re.sub(r"[^a-z0-9_]+", "", value)
    return value or "municipio"


def _detect_pkcs12_cmd() -> list[str]:
    result = subprocess.run(
        ["openssl", "pkcs12", "-help"], capture_output=True, text=True, check=False
    )
    output = (result.stdout or "") + (result.stderr or "")
    if "-legacy" in output:
        return ["openssl", "pkcs12", "-legacy"]
    return ["openssl", "pkcs12"]


def _ensure_output_dir(slug: str) -> str:
    base_dir = settings.certs_dir or "./certs"
    output_dir = os.path.join(base_dir, slug)
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def _run_openssl(cmd: list[str], error_prefix: str) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{error_prefix}: {result.stderr.strip() or result.stdout.strip()}")


def _extract_key(pkcs12_cmd: list[str], pfx_path: str, password: str, output_dir: str) -> str:
    key_path = os.path.join(output_dir, "key.pem")
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
    _run_openssl(cmd, "Fallo al extraer key.pem")
    if os.path.exists(key_path):
        try:
            os.chmod(key_path, 0o600)
        except PermissionError:
            pass
    return key_path


def _extract_client_cert(
    pkcs12_cmd: list[str], pfx_path: str, password: str, output_dir: str
) -> str:
    client_only_path = os.path.join(output_dir, "client_only.pem")
    cmd = pkcs12_cmd + [
        "-in",
        pfx_path,
        "-clcerts",
        "-nokeys",
        "-out",
        client_only_path,
        "-passin",
        f"pass:{password}",
    ]
    _run_openssl(cmd, "Fallo al extraer certificado de cliente")
    return client_only_path


def _extract_ca_chain(
    pkcs12_cmd: list[str], pfx_path: str, password: str, output_dir: str
) -> str:
    ca_chain_path = os.path.join(output_dir, "ca_chain.pem")
    cmd = pkcs12_cmd + [
        "-in",
        pfx_path,
        "-cacerts",
        "-nokeys",
        "-out",
        ca_chain_path,
        "-passin",
        f"pass:{password}",
    ]
    _run_openssl(cmd, "Fallo al extraer cadena de CAs")
    return ca_chain_path


def _extract_privpub(
    pkcs12_cmd: list[str], pfx_path: str, password: str, output_dir: str
) -> str:
    privpub_path = os.path.join(output_dir, "privpub.pem")
    cmd = pkcs12_cmd + [
        "-in",
        pfx_path,
        "-out",
        privpub_path,
        "-passin",
        f"pass:{password}",
    ]
    _run_openssl(cmd, "Fallo al extraer privpub.pem")
    return privpub_path


def _concat_client_pem(client_only_path: str, ca_chain_path: str, output_dir: str) -> str:
    client_path = os.path.join(output_dir, "client.pem")
    with open(client_path, "wb") as target:
        for candidate in (client_only_path, ca_chain_path):
            if candidate and os.path.exists(candidate) and os.path.getsize(candidate) > 0:
                with open(candidate, "rb") as handler:
                    target.write(handler.read())
    return client_path


def _openssl_modulus_hash(path: str, kind: str) -> str:
    if kind not in {"rsa", "x509"}:
        raise ValueError("kind debe ser 'rsa' o 'x509'")

    cmd = ["openssl", kind, "-noout", "-modulus", "-in", path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"No se pudo obtener el modulus de {path}: {result.stderr.strip() or result.stdout.strip()}"
        )

    output = (result.stdout or "").strip()
    modulus = output.split("=", 1)[-1].strip() if output else ""
    if not modulus:
        raise RuntimeError(f"No se pudo leer el modulus de {path}")

    import hashlib

    return hashlib.md5(modulus.encode("utf-8")).hexdigest()


def _verify_key_matches_cert(key_path: str, client_path: str, municipality: Municipality) -> None:
    key_md5 = _openssl_modulus_hash(key_path, "rsa")
    cert_md5 = _openssl_modulus_hash(client_path, "x509")

    if key_md5 != cert_md5:
        raise RuntimeError(
            "KEY_VALUES_MISMATCH: key.pem no corresponde con el primer certificado en "
            f"client.pem para el municipio {municipality.name} (id={municipality.id})."
        )


def extract_and_assign_cert(
    session: Session, *, pfx_path: str, password: str, municipality_id: int
) -> ExtractResult:
    if not pfx_path or not os.path.isfile(pfx_path):
        raise FileNotFoundError(f"El fichero PFX no existe o no es accesible: {pfx_path}")

    municipality = session.get(Municipality, municipality_id)
    if not municipality:
        raise RuntimeError(f"Municipio con id={municipality_id} no encontrado")

    slug_source = municipality.code or municipality.name or "municipio"
    slug = _slugify(slug_source)
    output_dir = _ensure_output_dir(slug)

    pkcs12_cmd = _detect_pkcs12_cmd()

    key_path = _extract_key(pkcs12_cmd, pfx_path, password, output_dir)
    client_only_path = _extract_client_cert(pkcs12_cmd, pfx_path, password, output_dir)
    ca_chain_path = _extract_ca_chain(pkcs12_cmd, pfx_path, password, output_dir)
    client_path = _concat_client_pem(client_only_path, ca_chain_path, output_dir)
    privpub_path = _extract_privpub(pkcs12_cmd, pfx_path, password, output_dir)

    for label, path in ("key.pem", key_path), ("client.pem", client_path):
        if not path or not os.path.isfile(path) or os.path.getsize(path) == 0:
            raise RuntimeError(f"No se pudo generar {label} en {output_dir}")

    _verify_key_matches_cert(key_path, client_path, municipality)

    cert_name = f"MOSSOS_{slug}"
    existing = (
        session.query(Certificate)
        .filter(Certificate.name == cert_name, Certificate.type == "PEM")
        .one_or_none()
    )

    if existing:
        certificate = existing
        certificate.path = os.path.abspath(client_path)
        certificate.client_cert_path = os.path.abspath(client_path)
        certificate.key_path = os.path.abspath(key_path)
        certificate.type = "PEM"
        certificate.active = True
        certificate.municipality_id = municipality.id
        certificate.pfx_path = os.path.abspath(pfx_path)
        certificate.privpub_path = os.path.abspath(privpub_path)
    else:
        certificate = Certificate(
            name=cert_name,
            type="PEM",
            path=os.path.abspath(client_path),
            client_cert_path=os.path.abspath(client_path),
            key_path=os.path.abspath(key_path),
            pfx_path=os.path.abspath(pfx_path),
            privpub_path=os.path.abspath(privpub_path),
            municipality_id=municipality.id,
            active=True,
        )
        session.add(certificate)
        session.flush()

    municipality.certificate = certificate
    session.add(municipality)
    session.commit()

    return ExtractResult(
        municipality=municipality,
        certificate=certificate,
        key_path=os.path.abspath(key_path),
        client_path=os.path.abspath(client_path),
        privpub_path=os.path.abspath(privpub_path),
    )


__all__ = ["extract_and_assign_cert", "ExtractResult"]
