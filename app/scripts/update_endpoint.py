"""Script interactivo para modificar endpoints."""
from __future__ import annotations

from app.models import Endpoint, SessionLocal


def main() -> None:
    session = SessionLocal()
    try:
        endpoints = session.query(Endpoint).order_by(Endpoint.id).all()
        if not endpoints:
            print("[UPDATE ENDPOINT][ERROR] No hay endpoints registrados.")
            return

        print("Endpoints disponibles:")
        for endpoint in endpoints:
            print(
                f"- {endpoint.id}: {endpoint.name} ({endpoint.url}) timeout={endpoint.timeout_ms} retry={endpoint.retry_max}"
            )

        ep_id_str = input("ID del endpoint a modificar: ").strip()
        if not ep_id_str.isdigit():
            print("[UPDATE ENDPOINT][ERROR] ID inválido.")
            return

        endpoint = session.get(Endpoint, int(ep_id_str))
        if not endpoint:
            print("[UPDATE ENDPOINT][ERROR] Endpoint no encontrado.")
            return

        print("Pulsa ENTER para mantener el valor actual.")
        new_name = input(f"Nombre [{endpoint.name}]: ").strip()
        new_url = input(f"URL [{endpoint.url}]: ").strip()
        new_timeout = input(f"Timeout ms [{endpoint.timeout_ms}]: ").strip()
        new_retry_max = input(f"Reintentos [{endpoint.retry_max}]: ").strip()
        new_backoff = input(f"Backoff ms [{endpoint.retry_backoff_ms}]: ").strip()

        if new_name:
            endpoint.name = new_name
        if new_url:
            endpoint.url = new_url
        if new_timeout:
            try:
                endpoint.timeout_ms = int(new_timeout)
            except ValueError:
                print("[UPDATE ENDPOINT][ERROR] Timeout debe ser numérico.")
                return
        if new_retry_max:
            try:
                endpoint.retry_max = int(new_retry_max)
            except ValueError:
                print("[UPDATE ENDPOINT][ERROR] retry_max debe ser numérico.")
                return
        if new_backoff:
            try:
                endpoint.retry_backoff_ms = int(new_backoff)
            except ValueError:
                print("[UPDATE ENDPOINT][ERROR] backoff debe ser numérico.")
                return

        session.add(endpoint)
        session.commit()
        print(f"[UPDATE ENDPOINT] Endpoint actualizado: {endpoint.name} (id={endpoint.id})")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        print(f"[UPDATE ENDPOINT][ERROR] {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
