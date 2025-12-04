"""Script interactivo para registrar certificados.

Uso: python -m app.scripts.add_certificate
"""
from app.models import Certificate, SessionLocal


def main() -> None:
    print("=== Añadir certificado ===")
    name = input("Nombre interno (ej. LAGRANADA_PFX): ").strip()
    path = input("Nombre de fichero dentro de CERTS_DIR (ej. lagranada.pfx): ").strip()
    type_input = input("Tipo (PFX o PEM, por defecto PFX): ").strip()
    cert_type = type_input if type_input else "PFX"

    session = SessionLocal()
    try:
        # El worker combinará settings.CERTS_DIR con certificate.path (os.path.join).
        certificate = Certificate(
            name=name,
            path=path,
            type=cert_type,
            active=True,
        )
        session.add(certificate)
        session.commit()
        session.refresh(certificate)
        print(f"Certificado creado con ID={certificate.id}")
        print(
            "Nota: el worker de envío usará CERTS_DIR del .env y certificate.path "
            "para construir la ruta absoluta al archivo."
        )
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        print(f"Error al crear el certificado: {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
