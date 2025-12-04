"""Script interactivo para crear endpoints.

Uso: python -m app.scripts.add_endpoint
"""
from app.models import Endpoint, SessionLocal


def main() -> None:
    print("=== Añadir endpoint ===")
    name = input("Nombre (ej. MOSSOS_PROD): ").strip()
    url = input("URL SOAP: ").strip()

    timeout_input = input("Timeout (ms, por defecto 5000): ").strip()
    retry_max_input = input("Reintentos máximos (por defecto 3): ").strip()
    retry_backoff_input = input("Backoff (ms, por defecto 1000): ").strip()

    timeout_ms = int(timeout_input) if timeout_input else 5000
    retry_max = int(retry_max_input) if retry_max_input else 3
    retry_backoff_ms = int(retry_backoff_input) if retry_backoff_input else 1000

    session = SessionLocal()
    try:
        endpoint = Endpoint(
            name=name,
            url=url,
            timeout_ms=timeout_ms,
            retry_max=retry_max,
            retry_backoff_ms=retry_backoff_ms,
        )
        session.add(endpoint)
        session.commit()
        session.refresh(endpoint)
        print(f"Endpoint creado con ID={endpoint.id}")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        print(f"Error al crear el endpoint: {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
