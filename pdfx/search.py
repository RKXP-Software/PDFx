"""Busca de texto incremental (algumas páginas por ciclo, sem travar a interface)."""

from __future__ import annotations

from PySide6.QtCore import QObject, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QToolButton, QWidget

from . import icons
from .document import Document

PAGES_PER_TICK = 6


class SearchController(QObject):
    resultsChanged = Signal()
    activeChanged = Signal(object, object)  # página, retângulo

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._tick)
        self.reset()

    def reset(self) -> None:
        self._timer.stop()
        self.doc: Document | None = None
        self.text = ""
        self.results: dict[int, list] = {}
        self.matches: list[tuple[int, object]] = []
        self.current = -1
        self._next_page = 0
        self._from_page = 0
        self.running = False

    def start(self, doc: Document | None, text: str, from_page: int = 0) -> None:
        self.reset()
        self.doc, self.text, self._from_page = doc, text.strip(), from_page
        if doc is None or not self.text:
            self.resultsChanged.emit()
            self.activeChanged.emit(None, None)
            return
        self.running = True
        self._timer.start()
        self.resultsChanged.emit()

    def stop(self) -> None:
        self.reset()
        self.resultsChanged.emit()
        self.activeChanged.emit(None, None)

    def _tick(self) -> None:
        if self.doc is None:
            self._timer.stop()
            return
        end = min(self._next_page + PAGES_PER_TICK, self.doc.page_count)
        for page in range(self._next_page, end):
            rects = self.doc.search(page, self.text)
            if rects:
                self.results[page] = rects
                self.matches.extend((page, r) for r in rects)
        self._next_page = end
        if self.current < 0:
            for i, (page, _r) in enumerate(self.matches):
                if page >= self._from_page:
                    self._set_current(i)
                    break
        if end >= self.doc.page_count:
            self._timer.stop()
            self.running = False
            if self.current < 0 and self.matches:
                self._set_current(0)
        self.resultsChanged.emit()

    def _set_current(self, index: int) -> None:
        self.current = index
        page, rect = self.matches[index]
        self.activeChanged.emit(page, rect)

    def next(self) -> None:
        if self.matches:
            self._set_current((self.current + 1) % len(self.matches))
            self.resultsChanged.emit()

    def previous(self) -> None:
        if self.matches:
            self._set_current((self.current - 1) % len(self.matches))
            self.resultsChanged.emit()

    def status_text(self) -> str:
        if not self.text:
            return ""
        if not self.matches:
            return "Buscando…" if self.running else "Nenhum resultado"
        total = f"{len(self.matches)}{'+' if self.running else ''}"
        return f"{self.current + 1} de {total}" if self.current >= 0 else f"{total} resultados"


class SearchEntry(QLineEdit):
    nextRequested = Signal()
    previousRequested = Signal()
    closeRequested = Signal()

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.previousRequested.emit()
            else:
                self.nextRequested.emit()
            return
        if key == Qt.Key.Key_Escape:
            self.closeRequested.emit()
            return
        super().keyPressEvent(event)


class SearchBar(QWidget):
    """Barra que aparece abaixo da barra de título, como o GtkSearchBar do Evince."""

    textChanged = Signal(str)
    nextRequested = Signal()
    previousRequested = Signal()
    closeRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SearchBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(self)
        row.setContentsMargins(6, 6, 6, 6)
        row.setSpacing(0)

        self.entry = SearchEntry()
        self.entry.setPlaceholderText("Buscar no documento")
        self.entry.setClearButtonEnabled(True)
        self.entry.addAction(icons.icon("search-small", "#7e8182"), QLineEdit.ActionPosition.LeadingPosition)
        self.entry.setFixedWidth(320)
        self.entry.setStyleSheet("QLineEdit { border-top-right-radius: 0px; border-bottom-right-radius: 0px; }")
        self.entry.textChanged.connect(self.textChanged)
        self.entry.nextRequested.connect(self.nextRequested)
        self.entry.previousRequested.connect(self.previousRequested)
        self.entry.closeRequested.connect(self.closeRequested)

        self.prev_button = self._button("go-up", "Resultado anterior (Shift+Enter)", "mid")
        self.next_button = self._button("go-down", "Próximo resultado (Enter)", "right")
        self.prev_button.clicked.connect(self.previousRequested)
        self.next_button.clicked.connect(self.nextRequested)

        self.count = QLabel("")
        self.count.setObjectName("SearchCount")
        self.count.setMinimumWidth(110)
        self.count.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        row.addStretch(1)
        spacer = QWidget()
        spacer.setFixedWidth(110)
        row.addWidget(spacer)
        row.addWidget(self.entry)
        row.addWidget(self.prev_button)
        row.addWidget(self.next_button)
        row.addSpacing(10)
        row.addWidget(self.count)
        row.addStretch(1)

    @staticmethod
    def _button(icon_name: str, tip: str, linked: str) -> QToolButton:
        b = QToolButton()
        b.setIcon(icons.icon(icon_name))
        b.setIconSize(QSize(16, 16))
        b.setToolTip(tip)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.setProperty("hb", True)
        b.setProperty("linked", linked)
        return b

    def set_status(self, text: str, has_matches: bool) -> None:
        self.count.setText(text)
        self.prev_button.setEnabled(has_matches)
        self.next_button.setEnabled(has_matches)
