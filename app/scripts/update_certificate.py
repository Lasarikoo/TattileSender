"""Script interactivo para modificar alias y municipio de certificados."""
from __future__ import annotations

from app.models import Certificate, Municipality, SessionLocal


def _choose_municipality(session, current_id: int | None):
    municipalities = session.query(Municipality).order_by(Municipality.id).all()
    if not municipalities:
        print("[UPDATE CERT][ERROR] No hay municipios dados de alta.")
        return None
    print("Municipios disponibles:")
    for municipality in municipalities:
        marker = " (actual)" if municipality.id == current_id else ""
        print(f"- {municipality.id}: {municipality.name}{marker}")

    mun_input = input("Municipio ID (ENTER para mantener): ").strip()
    if not mun_input:
        return None
    if not mun_input.isdigit():
        print("[UPDATE CERT][ERROR] ID inválido.")
        return None
    return session.get(Municipality, int(mun_input))


def main() -> None:
    session = SessionLocal()
    try:
        certificates = session.query(Certificate).order_by(Certificate.id).all()
        if not certificates:
            print("[UPDATE CERT][ERROR] No hay certificados registrados.")
            return

        print("Certificados disponibles:")
        for cert in certificates:
            print(
                f"- {cert.id}: alias={cert.alias or cert.name} municipio_id={cert.municipality_id}"
            )

        cert_id_str = input("ID del certificado a modificar: ").strip()
        if not cert_id_str.isdigit():
            print("[UPDATE CERT][ERROR] ID inválido.")
            return

        certificate = session.get(Certificate, int(cert_id_str))
        if not certificate:
            print("[UPDATE CERT][ERROR] Certificado no encontrado.")
            return

        print("Pulsa ENTER para mantener el valor actual.")
        new_alias = input(f"Alias [{certificate.alias or certificate.name}]: ").strip()
        municipality = _choose_municipality(session, certificate.municipality_id)

        if new_alias:
            certificate.alias = new_alias
            certificate.name = new_alias
        if municipality:
            certificate.municipality_id = municipality.id
            municipality.certificate_id = certificate.id
            session.add(municipality)

        session.add(certificate)
        session.commit()
        print(f"[UPDATE CERT] Certificado actualizado: {certificate.alias or certificate.name}")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        print(f"[UPDATE CERT][ERROR] {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
