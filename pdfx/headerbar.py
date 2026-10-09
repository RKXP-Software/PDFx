"""Barra de título no estilo GNOME (GtkHeaderBar), com os controles do Evince."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QFontMetrics, QIntValidator
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, QSizePolicy, QToolButton, QVBoxLayout,
    QWidget,
)

from . import icons

HEADER_HEIGHT = 46
ZOOM_PRESETS = (0.5, 0.7, 0.85, 1.0, 1.25, 1.5, 1.75, 2.0, 3.0, 4.0, 8.0)


def hb_button(icon_name: str | None, tooltip: str = "", checkable: bool = False) -> QToolButton:
    b = QToolButton()
    if icon_name:
        b.setIcon(icons.icon(icon_name))
    b.setIconSize(QSize(16, 16))
    b.setToolTip(tooltip)
    b.setCheckable(checkable)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    b.setProperty("hb", True)
    b.setFixedHeight(34)
    b.setMinimumWidth(34)
    return b


class PageEntry(QFrame):
    """Campo "[ 3 | de 14 ]" do Evince."""

    pageRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LinkedEntry")
        self.setFixedHeight(34)
        row = QHBoxLayout(self)
        row.setContentsMargins(1, 1, 1, 1)
        row.setSpacing(0)
        self.edit = QLineEdit()
        self.edit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.edit.setValidator(QIntValidator(1, 999999, self))
        self.edit.returnPressed.connect(self._submit)
        self.edit.editingFinished.connect(self._restore)
        self.label = QLabel("de 0")
        self.label.setObjectName("PageOf")
        self.label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        row.addWidget(self.edit)
        row.addWidget(self.label)
        self._current, self._total = 0, 0

    def set_page(self, current: int, total: int) -> None:
        self._current, self._total = current, total
        digits = max(2, len(str(total)))
        fm = QFontMetrics(self.edit.font())
        self.edit.setFixedWidth(fm.horizontalAdvance("9" * digits) + 18)
        self.label.setText(f"de {total}")
        if not self.edit.hasFocus():
            self.edit.setText(str(current + 1))

    def focus(self) -> None:
        self.edit.setFocus()
        self.edit.selectAll()

    def _submit(self) -> None:
        try:
            page = int(self.edit.text()) - 1
        except ValueError:
            self._restore()
            return
        if 0 <= page < self._total:
            self.pageRequested.emit(page)
        self.edit.clearFocus()
        self._restore()

    def _restore(self) -> None:
        self.edit.setText(str(self._current + 1))


class ZoomEntry(QFrame):
    """Campo de zoom "103% ▾" com o menu de ajustes do Evince."""

    zoomRequested = Signal(float)
    fitRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LinkedEntry")
        self.setFixedHeight(34)
        row = QHBoxLayout(self)
        row.setContentsMargins(1, 1, 1, 1)
        row.setSpacing(0)
        self.edit = QLineEdit()
        self.edit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.edit.setFixedWidth(64)
        self.edit.returnPressed.connect(self._submit)
        self.arrow = QToolButton()
        self.arrow.setObjectName("ZoomArrow")
        self.arrow.setIcon(icons.icon("pan-down"))
        self.arrow.setIconSize(QSize(16, 16))
        self.arrow.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.arrow.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.arrow.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        row.addWidget(self.edit)
        row.addWidget(self.arrow)

        menu = QMenu(self)
        group = QActionGroup(self)
        self.fit_width = QAction("Ajustar à largura", self, checkable=True)
        self.fit_page = QAction("Ajustar à página", self, checkable=True)
        for action, mode in ((self.fit_width, "width"), (self.fit_page, "page")):
            group.addAction(action)
            action.triggered.connect(lambda _c=False, m=mode: self.fitRequested.emit(m))
            menu.addAction(action)
        menu.addSeparator()
        for z in ZOOM_PRESETS:
            a = menu.addAction(f"{round(z * 100)}%")
            a.triggered.connect(lambda _c=False, v=z: self.zoomRequested.emit(v))
        self.arrow.setMenu(menu)

    def set_zoom(self, zoom: float, fit: str) -> None:
        if not self.edit.hasFocus():
            self.edit.setText(f"{round(zoom * 100)}%")
        self.fit_width.setChecked(fit == "width")
        self.fit_page.setChecked(fit == "page")

    def _submit(self) -> None:
        text = self.edit.text().replace("%", "").replace(",", ".").strip()
        try:
            value = float(text) / 100
        except ValueError:
            return
        if value > 0:
            self.zoomRequested.emit(value)
        self.edit.clearFocus()


class HeaderBar(QWidget):
    def __init__(self, parent=None, window_controls: bool = True):
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(HEADER_HEIGHT)

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 0, 6, 0)
        row.setSpacing(6)

        # ---- lado esquerdo
        self.left = QWidget()
        left = QHBoxLayout(self.left)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(6)
        self.open_button = QPushButton("Abrir…")
        self.open_button.setProperty("hb", True)
        self.open_button.setFixedHeight(34)
        self.open_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.open_button.setToolTip("Abrir um documento (Ctrl+O)")
        self.sidebar_button = hb_button("sidebar-show", "Barra lateral (F9)", checkable=True)
        self.page_entry = PageEntry()
        left.addWidget(self.open_button)
        left.addWidget(self.sidebar_button)
        left.addWidget(self.page_entry)
        row.addWidget(self.left)
        row.addStretch(1)

        # ---- lado direito
        self.right = QWidget()
        right = QHBoxLayout(self.right)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(6)
        self.zoom_entry = ZoomEntry()
        self.search_button = hb_button("edit-find", "Buscar (Ctrl+F)", checkable=True)
        self.menu_button = hb_button("open-menu", "Menu")
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        right.addWidget(self.zoom_entry)
        right.addWidget(self.search_button)
        right.addWidget(self.menu_button)

        self.min_button = self.max_button = self.close_button = None
        if window_controls:
            sep = QFrame()
            sep.setFixedSize(1, 22)
            sep.setStyleSheet("background: #cdc7c2;")
            right.addSpacing(4)
            right.addWidget(sep)
            right.addSpacing(4)
            self.min_button = self._window_button("window-minimize", "Minimizar")
            self.max_button = self._window_button("window-maximize", "Maximizar")
            self.close_button = self._window_button("window-close", "Fechar")
            for b in (self.min_button, self.max_button, self.close_button):
                right.addWidget(b)
        row.addWidget(self.right)

        # ---- título centralizado (posicionado manualmente, como no GTK)
        self.title_box = QWidget(self)
        self.title_box.setObjectName("TitleBox")
        self.title_box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        tb = QVBoxLayout(self.title_box)
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(0)
        self.title = QLabel("PDFx")
        self.title.setObjectName("Title")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("Subtitle")
        for lbl in (self.title, self.subtitle):
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tb.addWidget(lbl)
        self._title_text, self._subtitle_text = "PDFx", ""

    def _window_button(self, icon_name: str, tip: str) -> QToolButton:
        b = QToolButton()
        b.setIcon(icons.icon(icon_name))
        b.setIconSize(QSize(16, 16))
        b.setToolTip(tip)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.setProperty("wc", True)
        return b

    # ---- API
    def set_title(self, title: str, subtitle: str = "") -> None:
        self._title_text, self._subtitle_text = title, subtitle
        self.subtitle.setVisible(bool(subtitle))
        self._place_title()

    def set_document_mode(self, has_document: bool) -> None:
        self.open_button.setVisible(not has_document)
        for w in (self.sidebar_button, self.page_entry, self.zoom_entry, self.search_button):
            w.setVisible(has_document)
        QTimer.singleShot(0, self._place_title)

    def set_maximized(self, maximized: bool) -> None:
        if self.max_button is not None:
            self.max_button.setIcon(icons.icon("window-restore" if maximized else "window-maximize"))
            self.max_button.setToolTip("Restaurar" if maximized else "Maximizar")

    def set_backdrop(self, backdrop: bool) -> None:
        if self.property("backdrop") != backdrop:
            self.setProperty("backdrop", backdrop)
            for w in (self, self.title):
                w.style().unpolish(w)
                w.style().polish(w)

    def is_drag_area(self, widget: QWidget | None) -> bool:
        """True se o ponto clicado é "vazio" (pode arrastar a janela por ali)."""
        return widget is None or widget in (self, self.left, self.right, self.title_box, self.title, self.subtitle)

    # ---- layout do título
    def _place_title(self) -> None:
        left_edge = self.left.geometry().right() + 12
        right_edge = self.right.geometry().left() - 12
        available = max(0, right_edge - left_edge)
        width = self.width()
        # Centraliza na janela; se não couber, centraliza no espaço livre.
        fm_title = QFontMetrics(self.title.font())
        fm_sub = QFontMetrics(self.subtitle.font())
        wanted = max(fm_title.horizontalAdvance(self._title_text), fm_sub.horizontalAdvance(self._subtitle_text)) + 8
        box_w = min(wanted, available)
        x = (width - box_w) // 2
        if x < left_edge:
            x = left_edge
        if x + box_w > right_edge:
            x = max(left_edge, right_edge - box_w)
        self.title.setText(fm_title.elidedText(self._title_text, Qt.TextElideMode.ElideRight, box_w))
        self.subtitle.setText(fm_sub.elidedText(self._subtitle_text, Qt.TextElideMode.ElideMiddle, box_w))
        self.title_box.setGeometry(x, 0, box_w, self.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._place_title)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self._place_title)

    # ---- arrastar a janela (quando a moldura nativa do Windows não estiver tratando isso)
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.is_drag_area(self.childAt(event.position().toPoint())):
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            win = self.window()
            win.showNormal() if win.isMaximized() else win.showMaximized()
            return
        super().mouseDoubleClickEvent(event)
