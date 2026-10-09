"""Impressão pelo diálogo padrão do Windows."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import QApplication, QProgressDialog, QWidget

from .document import Document

MAX_DPI = 300


def print_document(parent: QWidget, doc: Document, current_page: int = 0) -> None:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setDocName(doc.title)
    dialog = QPrintDialog(printer, parent)
    dialog.setWindowTitle("Imprimir")
    dialog.setMinMax(1, doc.page_count)
    dialog.setOption(QPrintDialog.PrintDialogOption.PrintPageRange, True)
    dialog.setOption(QPrintDialog.PrintDialogOption.PrintCurrentPage, True)
    if dialog.exec() != QPrintDialog.DialogCode.Accepted:
        return

    mode = printer.printRange()
    if mode == QPrinter.PrintRange.PageRange:
        pages = list(range(max(1, printer.fromPage()) - 1, min(doc.page_count, printer.toPage())))
    elif mode == QPrinter.PrintRange.CurrentPage:
        pages = [current_page]
    else:
        pages = list(range(doc.page_count))
    if not pages:
        return

    progress = QProgressDialog("Imprimindo…", "Cancelar", 0, len(pages), parent)
    progress.setWindowTitle("Imprimir")
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(300)

    painter = QPainter()
    if not painter.begin(printer):
        return
    try:
        dpi = min(printer.resolution(), MAX_DPI)
        area = QRectF(painter.viewport())
        for n, page in enumerate(pages):
            if progress.wasCanceled():
                break
            if n:
                printer.newPage()
            w, h = doc.page_size(page)
            # Gira páginas em paisagem para aproveitar o papel em retrato (e vice-versa).
            rotation = 90 if (w > h) != (area.width() > area.height()) else 0
            img = doc.render(page, dpi / 72.0, rotation)
            size = img.size().toSizeF()
            size.scale(area.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRectF(area.left() + (area.width() - size.width()) / 2, area.top(), size.width(), size.height())
            painter.drawImage(target, img)
            progress.setValue(n + 1)
            QApplication.processEvents()
    finally:
        painter.end()
        progress.close()
