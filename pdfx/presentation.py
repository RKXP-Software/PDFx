"""Modo apresentação: uma página por vez, tela cheia, fundo preto (EvPresentationView)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from .document import Document


class PresentationWindow(QWidget):
    finished = Signal(int)

    def __init__(self, doc: Document, page: int, rotation: int = 0, inverted: bool = False):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Apresentação — PDFx")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._doc, self._page, self._rotation, self._inverted = doc, page, rotation, inverted
        self._white = False
        self._black = False
        self._cache: dict[tuple, QPixmap] = {}
        self._cursor_timer = QTimer(self)
        self._cursor_timer.setSingleShot(True)
        self._cursor_timer.setInterval(1500)
        self._cursor_timer.timeout.connect(lambda: self.setCursor(Qt.CursorShape.BlankCursor))
        self._cursor_timer.start()

    def _pixmap(self, page: int) -> QPixmap | None:
        if not 0 <= page < self._doc.page_count:
            return None
        w, h = self._doc.page_size(page, self._rotation)
        scale = min(self.width() / w, self.height() / h)
        dpr = self.devicePixelRatioF()
        key = (page, round(scale * dpr, 4))
        pm = self._cache.get(key)
        if pm is None:
            img = self._doc.render(page, scale * dpr, self._rotation, self._inverted)
            pm = QPixmap.fromImage(img)
            pm.setDevicePixelRatio(dpr)
            if len(self._cache) > 6:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = pm
        return pm

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("white") if self._white else QColor("black"))
        if self._black or self._white:
            return
        pm = self._pixmap(self._page)
        if pm is None:
            return
        size = pm.size().toSizeF() / pm.devicePixelRatio()
        target = QRectF((self.width() - size.width()) / 2, (self.height() - size.height()) / 2, size.width(), size.height())
        painter.drawPixmap(target, pm, QRectF(pm.rect()))
        QTimer.singleShot(0, lambda: self._pixmap(self._page + 1))  # pré-carrega a próxima

    def go(self, page: int) -> None:
        page = min(max(page, 0), self._doc.page_count - 1)
        if page != self._page:
            self._page = page
            self.update()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Escape, Qt.Key.Key_F5):
            self.close()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_PageDown, Qt.Key.Key_Space, Qt.Key.Key_Return,
                     Qt.Key.Key_N):
            self.go(self._page + 1)
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_PageUp, Qt.Key.Key_Backspace, Qt.Key.Key_P):
            self.go(self._page - 1)
        elif key == Qt.Key.Key_Home:
            self.go(0)
        elif key == Qt.Key.Key_End:
            self.go(self._doc.page_count - 1)
        elif key in (Qt.Key.Key_B, Qt.Key.Key_Period):
            self._black, self._white = not self._black, False
            self.update()
        elif key in (Qt.Key.Key_W, Qt.Key.Key_Comma):
            self._white, self._black = not self._white, False
            self.update()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.go(self._page + 1)
        elif event.button() == Qt.MouseButton.RightButton:
            self.go(self._page - 1)

    def mouseMoveEvent(self, event) -> None:
        self.unsetCursor()
        self._cursor_timer.start()

    def wheelEvent(self, event) -> None:
        self.go(self._page + (1 if event.angleDelta().y() < 0 else -1))

    def resizeEvent(self, event) -> None:
        self._cache.clear()
        super().resizeEvent(event)

    def closeEvent(self, event) -> None:
        self.finished.emit(self._page)
        super().closeEvent(event)
