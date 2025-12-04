"""Script interactivo para crear municipios.

Uso: python -m app.scripts.add_municipality
"""
from app.models import Municipality, SessionLocal


def main() -> None:
    print("=== Añadir municipio ===")
    name = input("Nombre: ").strip()
    code_input = input("Código (opcional): ").strip()
    code = code_input if code_input else None

    session = SessionLocal()
    try:
        municipality = Municipality(name=name, code=code, active=True)
        session.add(municipality)
        session.commit()
        session.refresh(municipality)
        print(f"Municipio creado con ID={municipality.id}")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        print(f"Error al crear el municipio: {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
