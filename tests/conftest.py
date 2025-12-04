import os
import sys

# Asegura que el paquete app sea importable desde la raíz del repo durante los tests
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
