"""Asigna un certificado a una cámara concreta."""
from __future__ import annotations

from app.models import Camera, Certificate, SessionLocal


def main() -> None:
    session = SessionLocal()
    try:
        cameras = session.query(Camera).order_by(Camera.id).all()
        certificates = session.query(Certificate).order_by(Certificate.id).all()

        if not cameras or not certificates:
            print("Debe existir al menos una cámara y un certificado.")
            return

        print("Cámaras disponibles:")
        for cam in cameras:
            print(f"- {cam.id}: {cam.serial_number} (cert actual: {cam.certificate_id})")

        camera_id = int(input("ID de la cámara a actualizar: ").strip())
        camera = session.get(Camera, camera_id)
        if not camera:
            print("Cámara no encontrada")
            return

        print("Certificados disponibles:")
        for cert in certificates:
            print(f"- {cert.id}: {cert.name} (path={cert.path})")

        cert_id = int(input("ID del certificado a asignar: ").strip())
        certificate = session.get(Certificate, cert_id)
        if not certificate:
            print("Certificado no encontrado")
            return

        camera.certificate_id = certificate.id
        session.add(camera)
        session.commit()
        print(f"Certificado {certificate.name} asignado a la cámara {camera.serial_number}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
