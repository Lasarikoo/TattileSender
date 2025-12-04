"""Permite modificar datos de cámaras existentes."""
from __future__ import annotations

from app.models import Camera, Endpoint, Municipality, SessionLocal


COORD_PROMPT = "Debe ser numérico con punto o coma y exactamente dos decimales (máx. 8 enteros)."


def _validate_coord(raw: str) -> tuple[str, float] | None:
    normalized = raw.replace(",", ".")
    parts = normalized.split(".")
    if len(parts) != 2 or len(parts[1]) != 2 or not all(part.isdigit() for part in parts):
        print(f"[UPDATE CAMARA][ERROR] {COORD_PROMPT}")
        return None
    try:
        as_float = float(normalized)
    except ValueError:
        print(f"[UPDATE CAMARA][ERROR] {COORD_PROMPT}")
        return None
    integer_part = parts[0].lstrip("-")
    if len(integer_part) > 8:
        print(f"[UPDATE CAMARA][ERROR] {COORD_PROMPT}")
        return None
    return f"{as_float:.2f}", as_float


def _choose_municipality(session):
    municipalities = session.query(Municipality).order_by(Municipality.id).all()
    if not municipalities:
        print("[UPDATE CAMARA][ERROR] No hay municipios disponibles.")
        return None
    print("Municipios disponibles:")
    for municipality in municipalities:
        print(f"- {municipality.id}: {municipality.name}")

    mun_input = input("Municipio ID (ENTER para mantener): ").strip()
    if not mun_input:
        return None
    if not mun_input.isdigit():
        print("[UPDATE CAMARA][ERROR] ID de municipio inválido.")
        return None
    return session.get(Municipality, int(mun_input))


def _choose_endpoint(session):
    endpoints = session.query(Endpoint).order_by(Endpoint.id).all()
    if not endpoints:
        print("[UPDATE CAMARA] No hay endpoints dados de alta (puede quedar vacío).")
        return None
    print("Endpoints disponibles:")
    for endpoint in endpoints:
        print(f"- {endpoint.id}: {endpoint.name} ({endpoint.url})")

    ep_input = input("Endpoint ID (ENTER para mantener / vacío para ninguno): ").strip()
    if not ep_input:
        return None
    if not ep_input.isdigit():
        print("[UPDATE CAMARA][ERROR] ID de endpoint inválido.")
        return None
    return session.get(Endpoint, int(ep_input))


def main() -> None:
    session = SessionLocal()
    try:
        cameras = session.query(Camera).order_by(Camera.id).all()
        if not cameras:
            print("[UPDATE CAMARA][ERROR] No hay cámaras registradas.")
            return

        print("Cámaras disponibles:")
        for camera in cameras:
            print(
                f"- {camera.id}: {camera.serial_number} (lector: {camera.codigo_lector}, municipio: {camera.municipality_id})"
            )

        cam_id_str = input("ID de la cámara a modificar: ").strip()
        if not cam_id_str.isdigit():
            print("[UPDATE CAMARA][ERROR] ID inválido.")
            return

        camera = session.get(Camera, int(cam_id_str))
        if not camera:
            print("[UPDATE CAMARA][ERROR] Cámara no encontrada.")
            return

        print("Pulsa ENTER para mantener el valor actual.")
        new_serial = input(f"Serial [{camera.serial_number}]: ").strip()
        new_code = input(f"Código lector [{camera.codigo_lector}]: ").strip()
        new_desc = input(f"Descripción [{camera.description or ''}]: ").strip()
        new_coord_x = input(
            f"Coordenada X (actual {camera.coord_x or camera.utm_x}) [{COORD_PROMPT}]: "
        ).strip()
        new_coord_y = input(
            f"Coordenada Y (actual {camera.coord_y or camera.utm_y}) [{COORD_PROMPT}]: "
        ).strip()

        municipality = _choose_municipality(session)
        endpoint = _choose_endpoint(session)

        if new_serial:
            camera.serial_number = new_serial
        if new_code:
            camera.codigo_lector = new_code
        if new_desc:
            camera.description = new_desc
        if new_coord_x:
            validated = _validate_coord(new_coord_x)
            if not validated:
                return
            camera.coord_x, camera.utm_x = validated
        if new_coord_y:
            validated = _validate_coord(new_coord_y)
            if not validated:
                return
            camera.coord_y, camera.utm_y = validated
        if municipality:
            camera.municipality_id = municipality.id
        if endpoint is not None:
            camera.endpoint_id = endpoint.id if endpoint else None

        session.add(camera)
        session.commit()
        print(f"[UPDATE CAMARA] Cámara actualizada: {camera.serial_number} (id={camera.id})")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        print(f"[UPDATE CAMARA][ERROR] {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
