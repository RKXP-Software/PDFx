"""Ponto de entrada: cria a aplicação Qt e gerencia as janelas (uma por documento, como no Evince)."""

from __future__ import annotations

import os
import sys
import traceback

from PySide6.QtCore import QLibraryInfo, QLocale, QStandardPaths, Qt, QTranslator
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import APP_NAME, theme
from .resources import resource_path
from .settings import Settings, normalize


def _install_error_log() -> None:
    """No executável sem console, erros não aparecem em lugar nenhum; grava em um arquivo de log."""
    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
            os.makedirs(base, exist_ok=True)
            with open(os.path.join(base, "pdfx-erros.log"), "a", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError:
            pass
        if sys.stderr is not None:
            sys.stderr.write(text)

    sys.excepthook = hook


class Application:
    def __init__(self, qapp: QApplication):
        self.qapp = qapp
        self.settings = Settings()
        self.windows: list = []

    def new_window(self):
        from .main_window import MainWindow

        window = MainWindow(self)
        offset = 30 * len(self.windows)
        self.windows.append(window)
        window.restore_window(offset)
        return window

    def window_for(self, path: str):
        key = normalize(path)
        for w in self.windows:
            if w.doc is not None and normalize(w.doc.path) == key:
                return w
        return None

    def open(self, path: str, origin=None) -> None:
        """Abre o arquivo: reaproveita a janela vazia ou cria uma nova; se já estiver aberto, traz para frente."""
        path = os.path.abspath(path)
        existing = self.window_for(path)
        if existing is not None:
            if existing.isMinimized():
                existing.showNormal()
            existing.raise_()
            existing.activateWindow()
            return
        target = origin if origin is not None and origin.doc is None else None
        if target is None:
            target = next((w for w in self.windows if w.doc is None), None)
        if target is None:
            target = self.new_window()
        target.load(path)

    def window_closed(self, window) -> None:
        if window in self.windows:
            self.windows.remove(window)

    def recent_changed(self) -> None:
        for w in self.windows:
            w.refresh_recent()

    def quit(self) -> None:
        for w in list(self.windows):
            w.close()


def main() -> None:
    _install_error_log()
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PDFx.DocumentViewer")
        except Exception:
            pass

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    qapp = QApplication(sys.argv)
    qapp.setApplicationName(APP_NAME)
    qapp.setOrganizationName(APP_NAME)
    qapp.setWindowIcon(QIcon(resource_path("pdfx.ico")))
    translator = QTranslator(qapp)
    if translator.load(QLocale("pt_BR"), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
        qapp.installTranslator(translator)
    theme.apply(qapp)

    app = Application(qapp)
    files = [a for a in sys.argv[1:] if not a.startswith("-") and os.path.isfile(a)]
    if files:
        for path in files:
            app.open(path)
        if not app.windows:
            app.new_window()
    else:
        app.new_window()
    sys.exit(qapp.exec())
