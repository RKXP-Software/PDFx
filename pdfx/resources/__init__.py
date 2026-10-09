"""Localiza arquivos de recursos tanto rodando do código-fonte quanto empacotado (PyInstaller)."""

import os
import sys


def resource_path(name: str) -> str:
    if getattr(sys, "frozen", False):
        base = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)), "pdfx", "resources")
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, name)
