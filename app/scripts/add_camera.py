"""Script interactivo para crear cámaras.

Uso: python -m app.scripts.add_camera
"""
from sqlalchemy.orm import Session

from app.models import Camera, Endpoint, Municipality, SessionLocal


def select_municipality(session: Session) -> Municipality | None:
    municipalities = session.query(Municipality).all()
    if not municipalities:
        print("No hay municipios registrados. Por favor, crea uno primero.")
        return None

    print("Municipios disponibles:")
    for municipality in municipalities:
        print(
            f"- ID={municipality.id} | Nombre={municipality.name} | Código={municipality.code}"
        )

    municipality_id = input("Municipality ID: ").strip()
    if not municipality_id.isdigit():
        print("ID de municipio inválido.")
        return None

    municipality = session.get(Municipality, int(municipality_id))
    if municipality is None:
        print("Municipio no encontrado.")
    return municipality


def select_endpoint(session: Session) -> Endpoint | None:
    endpoints = session.query(Endpoint).all()
    if not endpoints:
        print("No hay endpoints registrados. Puedes dejarlo vacío.")
        return None

    print("Endpoints disponibles:")
    for endpoint in endpoints:
        print(f"- ID={endpoint.id} | Nombre={endpoint.name} | URL={endpoint.url}")

    endpoint_input = input("Endpoint ID (ENTER para ninguno): ").strip()
    if not endpoint_input:
        return None
    if not endpoint_input.isdigit():
        print("ID de endpoint inválido.")
        return None

    endpoint = session.get(Endpoint, int(endpoint_input))
    if endpoint is None:
        print("Endpoint no encontrado.")
    return endpoint


def main() -> None:
    print("=== Añadir cámara ===")
    serial_number = input("Serial number (DEVICE_SN): ").strip()
    codigo_lector = input("Código lector: ").strip()
    utm_x_str = input(
        "Coordenada X (UTM31N - ETRS89, exactamente con dos decimales): "
    ).strip()
    utm_y_str = input(
        "Coordenada Y (UTM31N - ETRS89, exactamente con dos decimales): "
    ).strip()

    def _validate_coord(raw: str, label: str) -> tuple[str, float] | None:
        if not raw:
            print(f"[ADD CAMERA][ERROR] {label} es obligatorio.")
            return None
        normalized = raw.replace(",", ".")
        parts = normalized.split(".")
        if len(parts) != 2 or len(parts[1]) != 2 or not all(part.isdigit() for part in parts):
            print(
                f"[ADD CAMERA][ERROR] {label} debe ser numérico y contener exactamente dos decimales."
            )
            return None
        try:
            as_float = float(normalized)
        except ValueError:
            print(f"[ADD CAMERA][ERROR] {label} debe ser numérico y con formato decimal.")
            return None
        integer_part = parts[0].lstrip("-")
        if len(integer_part) > 8:
            print(f"[ADD CAMERA][ERROR] {label} supera las 8 cifras enteras permitidas.")
            return None
        return f"{as_float:.2f}", as_float

    validated_x = _validate_coord(utm_x_str, "Coordenada X")
    validated_y = _validate_coord(utm_y_str, "Coordenada Y")
    if not validated_x or not validated_y:
        return

    session = SessionLocal()
    try:
        municipality = select_municipality(session)
        if municipality is None:
            return

        endpoint = select_endpoint(session)

        coord_x, utm_x = validated_x
        coord_y, utm_y = validated_y

        camera = Camera(
            serial_number=serial_number,
            codigo_lector=codigo_lector,
            municipality_id=municipality.id,
            endpoint_id=endpoint.id if endpoint else None,
            coord_x=coord_x,
            coord_y=coord_y,
            utm_x=utm_x,
            utm_y=utm_y,
            active=True,
        )
        session.add(camera)
        session.commit()
        session.refresh(camera)
        print(f"Cámara creada con ID={camera.id}, serial={camera.serial_number}")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        print(f"Error al crear la cámara: {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
