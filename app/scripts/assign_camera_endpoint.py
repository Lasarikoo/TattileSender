"""Asigna un endpoint a una cámara concreta."""
from __future__ import annotations

from app.models import Camera, Endpoint, SessionLocal


def main() -> None:
    session = SessionLocal()
    try:
        cameras = session.query(Camera).order_by(Camera.id).all()
        endpoints = session.query(Endpoint).order_by(Endpoint.id).all()

        if not cameras or not endpoints:
            print("Debe existir al menos una cámara y un endpoint.")
            return

        print("Cámaras disponibles:")
        for cam in cameras:
            print(f"- {cam.id}: {cam.serial_number} (endpoint actual: {cam.endpoint_id})")

        camera_id = int(input("ID de la cámara a actualizar: ").strip())
        camera = session.get(Camera, camera_id)
        if not camera:
            print("Cámara no encontrada")
            return

        print("Endpoints disponibles:")
        for endpoint in endpoints:
            print(f"- {endpoint.id}: {endpoint.name} ({endpoint.url})")

        endpoint_id = int(input("ID del endpoint a asignar: ").strip())
        endpoint = session.get(Endpoint, endpoint_id)
        if not endpoint:
            print("Endpoint no encontrado")
            return

        camera.endpoint_id = endpoint.id
        session.add(camera)
        session.commit()
        print(f"Endpoint {endpoint.name} asignado a la cámara {camera.serial_number}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
