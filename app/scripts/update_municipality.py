"""Script interactivo para modificar municipios."""
from __future__ import annotations

from app.models import Municipality, SessionLocal


def main() -> None:
    session = SessionLocal()
    try:
        municipalities = session.query(Municipality).order_by(Municipality.id).all()
        if not municipalities:
            print("[UPDATE MUNICIPIO][ERROR] No hay municipios registrados.")
            return

        print("Municipios disponibles:")
        for municipality in municipalities:
            print(f"- {municipality.id}: {municipality.name} (código: {municipality.code})")

        mun_id_str = input("ID del municipio a modificar: ").strip()
        if not mun_id_str.isdigit():
            print("[UPDATE MUNICIPIO][ERROR] ID inválido.")
            return

        municipality = session.get(Municipality, int(mun_id_str))
        if not municipality:
            print("[UPDATE MUNICIPIO][ERROR] Municipio no encontrado.")
            return

        print("Pulsa ENTER para mantener el valor actual.")
        new_name = input(f"Nombre [{municipality.name}]: ").strip()
        new_code = input(f"Código [{municipality.code or ''}]: ").strip()

        if new_name:
            municipality.name = new_name
        if new_code:
            municipality.code = new_code

        session.add(municipality)
        session.commit()
        print(f"[UPDATE MUNICIPIO] Municipio actualizado: {municipality.name} (id={municipality.id})")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        print(f"[UPDATE MUNICIPIO][ERROR] {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
