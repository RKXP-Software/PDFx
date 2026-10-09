"""Gera as capturas de tela do README (docs/*.png) usando documentos de exemplo.

Usa um arquivo de configuração temporário, então não mexe nos recentes nem nas preferências reais.
Uso: .venv/Scripts/python tools/make_screenshots.py
"""

import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QSettings, QStandardPaths, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

OUT = os.path.join(ROOT, "docs")
SIZE = (1100, 720)
DOCS = ["Relatório Anual", "Manual do Usuário", "Receitas da Vovó", "Contrato de Serviços", "Artigo Científico"]


def make_docs(folder: str) -> list[str]:
    import pymupdf

    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import make_sample

    paths = []
    for title in DOCS:
        path = os.path.join(folder, f"{title}.pdf")
        make_sample.main(path)
        doc = pymupdf.open(path)
        doc.set_metadata({"title": title, "author": "PDFx"})
        doc.saveIncr()
        paths.append(path)
    return paths


def pump(qapp, ms: int) -> None:
    from PySide6.QtCore import QEventLoop

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def shot(qapp, window, name: str) -> None:
    pump(qapp, 900)
    os.makedirs(OUT, exist_ok=True)
    window.grab().save(os.path.join(OUT, name))
    print("salvo:", name)


def main() -> None:
    tmp = tempfile.mkdtemp(prefix="pdfx-shots-")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tmp)
    QStandardPaths.setTestModeEnabled(True)

    from pdfx import APP_NAME, app as appmod, theme

    appmod.sys.argv = [sys.argv[0]]
    paths = make_docs(tmp)

    qapp = QApplication(sys.argv)
    qapp.setApplicationName(APP_NAME)
    qapp.setOrganizationName(APP_NAME)
    theme.apply(qapp)
    ctx = appmod.Application(qapp)

    # abre cada documento para popular os recentes (e as miniaturas), fechando em seguida
    for p in reversed(paths):
        ctx.settings.add_recent(p)
    w = ctx.new_window()
    w.resize(*SIZE)
    w.show()
    shot(qapp, w, "recentes.png")

    w.load(paths[1])
    w.resize(*SIZE)
    shot(qapp, w, "leitura.png")

    w.set_search_visible(True)
    w.search_bar.entry.setText("conforto")
    w._start_search()
    pump(qapp, 1200)
    shot(qapp, w, "busca.png")
    w.set_search_visible(False)

    w.act_inverted.setChecked(True)
    w._set_inverted(True)
    w.sidebar.set_page(1)
    shot(qapp, w, "modo-noturno.png")
    sys.exit(0)


if __name__ == "__main__":
    main()
