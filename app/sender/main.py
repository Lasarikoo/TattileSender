"""Punto de entrada ejecutable para el sender worker."""
from __future__ import annotations

import logging
import sys

from app.sender.worker import run_sender_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    stream=sys.stdout,
)


def main() -> None:
    run_sender_worker()


if __name__ == "__main__":
    main()
