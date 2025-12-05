"""Punto de entrada ejecutable para el sender worker."""
from __future__ import annotations

from app.logger import logger  # noqa: F401 - inicializa configuración global
from app.sender.worker import run_sender_worker


def main() -> None:
    run_sender_worker()


if __name__ == "__main__":
    main()
