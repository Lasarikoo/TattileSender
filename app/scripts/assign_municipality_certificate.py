"""Asigna un certificado a un municipio existente."""
from __future__ import annotations

from app.models import Certificate, Municipality, SessionLocal


def main() -> None:
    session = SessionLocal()
    try:
        municipalities = session.query(Municipality).order_by(Municipality.id).all()
        certificates = session.query(Certificate).order_by(Certificate.id).all()

        if not municipalities or not certificates:
            print("Debe existir al menos un municipio y un certificado activo.")
            return

        print("Municipios disponibles:")
        for m in municipalities:
            print(f"- {m.id}: {m.name} (cert actual: {m.certificate_id})")

        muni_id = int(input("ID del municipio a actualizar: ").strip())
        municipality = session.get(Municipality, muni_id)
        if not municipality:
            print("Municipio no encontrado")
            return

        print("Certificados disponibles:")
        for c in certificates:
            print(f"- {c.id}: {c.name} (path={c.path})")

        cert_id = int(input("ID del certificado a asignar: ").strip())
        certificate = session.get(Certificate, cert_id)
        if not certificate:
            print("Certificado no encontrado")
            return

        municipality.certificate_id = certificate.id
        session.add(municipality)
        session.commit()
        print(f"Certificado {certificate.name} asignado a {municipality.name}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
