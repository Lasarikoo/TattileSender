"""Asigna un endpoint a un municipio existente."""
from __future__ import annotations

from app.models import Endpoint, Municipality, SessionLocal


def main() -> None:
    session = SessionLocal()
    try:
        municipalities = session.query(Municipality).order_by(Municipality.id).all()
        endpoints = session.query(Endpoint).order_by(Endpoint.id).all()

        if not municipalities or not endpoints:
            print("Debe existir al menos un municipio y un endpoint.")
            return

        print("Municipios disponibles:")
        for m in municipalities:
            print(f"- {m.id}: {m.name} (endpoint actual: {m.endpoint_id})")

        muni_id = int(input("ID del municipio a actualizar: ").strip())
        municipality = session.get(Municipality, muni_id)
        if not municipality:
            print("Municipio no encontrado")
            return

        print("Endpoints disponibles:")
        for e in endpoints:
            print(f"- {e.id}: {e.name} ({e.url})")

        endpoint_id = int(input("ID del endpoint a asignar: ").strip())
        endpoint = session.get(Endpoint, endpoint_id)
        if not endpoint:
            print("Endpoint no encontrado")
            return

        municipality.endpoint_id = endpoint.id
        session.add(municipality)
        session.commit()
        print(f"Endpoint {endpoint.name} asignado a {municipality.name}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
