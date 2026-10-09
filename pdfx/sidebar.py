"""Barra lateral: miniaturas, sumário e marcadores (como o EvSidebar do Evince)."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem,
    QStackedWidget, QStyle, QStyledItemDelegate, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QWidget,
)

from . import icons, theme
from .document import Document

THUMB_WIDTH = 100
PIXMAP_ROLE = Qt.ItemDataRole.UserRole
ASPECT_ROLE = Qt.ItemDataRole.UserRole + 1
DEST_ROLE = Qt.ItemDataRole.UserRole + 2


class _ThumbnailDelegate(QStyledItemDelegate):
    """Miniatura com borda preta e o número da página embaixo; selecionada fica com fundo azul."""

    PAD = 6
    LABEL_H = 20

    def sizeHint(self, option, index) -> QSize:
        aspect = index.data(ASPECT_ROLE) or 1.4
        return QSize(THUMB_WIDTH + 2 * self.PAD, int(THUMB_WIDTH * aspect) + self.LABEL_H + 2 * self.PAD)

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        aspect = index.data(ASPECT_ROLE) or 1.4
        tw, th = THUMB_WIDTH, int(THUMB_WIDTH * aspect)
        box = QRect(rect.center().x() - tw // 2 - self.PAD, rect.top() + 2, tw + 2 * self.PAD,
                    th + self.LABEL_H + 2 * self.PAD - 4)
        if selected:
            painter.fillRect(box, QColor(theme.ACCENT))
        thumb = QRect(rect.center().x() - tw // 2, rect.top() + self.PAD, tw, th)
        pm = index.data(PIXMAP_ROLE)
        painter.fillRect(thumb, QColor("white"))
        if pm is not None:
            painter.drawPixmap(QRectF(thumb), pm, QRectF(pm.rect()))
        painter.setPen(QPen(QColor("black"), 1))
        painter.drawRect(thumb.adjusted(0, 0, -1, -1))
        font = QFont(option.font)
        font.setItalic(True)
        painter.setFont(font)
        painter.setPen(QColor("white") if selected else QColor(theme.FG))
        label = QRect(rect.left(), thumb.bottom() + 2, rect.width(), self.LABEL_H)
        painter.drawText(label, Qt.AlignmentFlag.AlignCenter, index.data(Qt.ItemDataRole.DisplayRole))
        painter.restore()


class ThumbnailList(QListWidget):
    pageActivated = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(_ThumbnailDelegate(self))
        self.setUniformItemSizes(False)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSpacing(2)
        self._doc: Document | None = None
        self._rotation = 0
        self._inverted = False
        self._done: set[int] = set()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(15)
        self._timer.timeout.connect(self._render_visible)
        self.verticalScrollBar().valueChanged.connect(lambda _v: self._timer.start())
        self.currentRowChanged.connect(self._on_row_changed)

    def set_document(self, doc: Document | None, rotation: int = 0, inverted: bool = False) -> None:
        self.blockSignals(True)
        self.clear()
        self.blockSignals(False)
        self._doc, self._rotation, self._inverted = doc, rotation, inverted
        self._done.clear()
        if doc is None:
            return
        for i in range(doc.page_count):
            w, h = doc.page_size(i, rotation)
            item = QListWidgetItem(str(i + 1))
            item.setData(ASPECT_ROLE, h / w)
            self.addItem(item)
        self._timer.start()

    def set_options(self, rotation: int, inverted: bool) -> None:
        if self._doc is None or (rotation, inverted) == (self._rotation, self._inverted):
            return
        current = self.currentRow()
        self.set_document(self._doc, rotation, inverted)
        self.set_current(current)

    def set_current(self, page: int) -> None:
        if page < 0 or page >= self.count():
            return
        self.blockSignals(True)
        self.setCurrentRow(page)
        self.blockSignals(False)
        self.scrollToItem(self.item(page), QAbstractItemView.ScrollHint.EnsureVisible)
        self._timer.start()

    def _on_row_changed(self, row: int) -> None:
        if row >= 0:
            self.pageActivated.emit(row)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._timer.start()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()

    def _render_visible(self) -> None:
        if self._doc is None or not self.isVisible() or self.count() == 0:
            return
        vp = self.viewport().rect()
        first = self.indexAt(QPoint(vp.center().x(), vp.top() + 2)).row()
        last = self.indexAt(QPoint(vp.center().x(), vp.bottom() - 2)).row()
        first = 0 if first < 0 else first
        last = self.count() - 1 if last < 0 else last
        dpr = self.devicePixelRatioF()
        for row in range(max(0, first - 1), min(self.count(), last + 2)):
            if row in self._done:
                continue
            w, _h = self._doc.page_size(row, self._rotation)
            scale = THUMB_WIDTH * dpr / w
            try:
                img = self._doc.render(row, scale, self._rotation, self._inverted)
            except Exception:
                img = None
            self._done.add(row)
            if img is not None:
                pm = QPixmap.fromImage(img)
                pm.setDevicePixelRatio(dpr)
                self.item(row).setData(PIXMAP_ROLE, pm)
            self._timer.start()  # uma miniatura por ciclo para não travar a interface
            return


class OutlineTree(QTreeWidget):
    destinationActivated = Signal(int, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setColumnCount(2)
        self.setRootIsDecorated(True)
        self.setUniformRowHeights(True)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.itemActivated.connect(self._activate)
        self.itemClicked.connect(self._activate)

    def set_toc(self, toc: list) -> None:
        self.clear()
        stack: list[tuple[int, QTreeWidgetItem | None]] = [(0, None)]
        for level, title, page, point in toc:
            while len(stack) > 1 and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1]
            item = QTreeWidgetItem([title, str(page + 1) if page >= 0 else ""])
            item.setForeground(1, QColor(theme.DIM_FG))
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item.setToolTip(0, title)
            item.setData(0, DEST_ROLE, (page, point))
            if parent is None:
                self.addTopLevelItem(item)
            else:
                parent.addChild(item)
            stack.append((level, item))
        if self.topLevelItemCount() <= 12:
            self.expandAll()

    def _activate(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        page, point = item.data(0, DEST_ROLE)
        if page is not None and page >= 0:
            self.destinationActivated.emit(page, point)


class BookmarksPanel(QWidget):
    pageActivated = Signal(int)
    addRequested = Signal()
    removeRequested = Signal(int)
    renamed = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.list = QListWidget()
        self.list.itemActivated.connect(self._activate)
        self.list.itemClicked.connect(self._activate)
        self.list.itemChanged.connect(self._changed)
        self.empty = QLabel("Nenhum marcador\n\nUse Ctrl+D para marcar\na página atual")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setStyleSheet(f"color: {theme.DIM_FG}; background: {theme.BASE};")
        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.list)
        layout.addWidget(self.stack, 1)

        bar = QWidget()
        bar.setStyleSheet(f"background: {theme.BASE};")
        row = QHBoxLayout(bar)
        row.setContentsMargins(6, 6, 6, 6)
        row.setSpacing(0)
        self.add_button = _hb_button("list-add", "Adicionar marcador (Ctrl+D)", linked="left")
        self.remove_button = _hb_button("list-remove", "Remover marcador", linked="right")
        self.add_button.clicked.connect(self.addRequested)
        self.remove_button.clicked.connect(self._remove)
        row.addStretch(1)
        row.addWidget(self.add_button)
        row.addWidget(self.remove_button)
        row.addStretch(1)
        layout.addWidget(bar)

    def set_bookmarks(self, items: list[dict]) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for b in sorted(items, key=lambda b: b["page"]):
            item = QListWidgetItem(b.get("title") or f"Página {b['page'] + 1}")
            item.setData(DEST_ROLE, b["page"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.stack.setCurrentIndex(1 if items else 0)
        self.remove_button.setEnabled(bool(items))

    def _activate(self, item: QListWidgetItem) -> None:
        self.pageActivated.emit(item.data(DEST_ROLE))

    def _changed(self, item: QListWidgetItem) -> None:
        self.renamed.emit(item.data(DEST_ROLE), item.text().strip())

    def _remove(self) -> None:
        item = self.list.currentItem()
        if item is not None:
            self.removeRequested.emit(item.data(DEST_ROLE))


def _hb_button(icon_name: str, tooltip: str, checkable: bool = False, linked: str | None = None) -> QToolButton:
    b = QToolButton()
    b.setIcon(icons.icon(icon_name))
    b.setIconSize(QSize(16, 16))
    b.setToolTip(tooltip)
    b.setCheckable(checkable)
    b.setAutoRaise(False)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    b.setProperty("hb", True)
    if linked:
        b.setProperty("linked", linked)
    return b


class Sidebar(QWidget):
    pageRequested = Signal(int, object)

    THUMBNAILS, OUTLINE, BOOKMARKS = range(3)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(140)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.thumbnails = ThumbnailList()
        self.outline = OutlineTree()
        self.bookmarks = BookmarksPanel()
        self.stack = QStackedWidget()
        for w in (self.thumbnails, self.outline, self.bookmarks):
            self.stack.addWidget(w)
        layout.addWidget(self.stack, 1)

        switcher = QWidget()
        switcher.setObjectName("SidebarSwitcher")
        switcher.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(switcher)
        row.setContentsMargins(6, 6, 6, 6)
        row.setSpacing(0)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        specs = (("view-grid", "Miniaturas", "left"), ("view-index", "Sumário", "mid"),
                 ("bookmarks", "Marcadores", "right"))
        self.buttons: list[QToolButton] = []
        row.addStretch(1)
        for i, (name, tip, linked) in enumerate(specs):
            b = _hb_button(name, tip, checkable=True, linked=linked)
            self._group.addButton(b, i)
            self.buttons.append(b)
            row.addWidget(b)
        row.addStretch(1)
        self._group.idClicked.connect(self.set_page)
        layout.addWidget(switcher)

        self.thumbnails.pageActivated.connect(lambda p: self.pageRequested.emit(p, None))
        self.outline.destinationActivated.connect(self.pageRequested)
        self.bookmarks.pageActivated.connect(lambda p: self.pageRequested.emit(p, None))
        self.set_page(self.THUMBNAILS)

    def set_page(self, index: int) -> None:
        if not self.buttons[index].isEnabled():
            index = self.THUMBNAILS
        self.stack.setCurrentIndex(index)
        self.buttons[index].setChecked(True)

    def current(self) -> int:
        return self.stack.currentIndex()

    def set_document(self, doc: Document | None, rotation: int = 0, inverted: bool = False) -> None:
        self.thumbnails.set_document(doc, rotation, inverted)
        toc = doc.toc() if doc is not None else []
        self.outline.set_toc(toc)
        self.buttons[self.OUTLINE].setEnabled(bool(toc))
        if not toc and self.current() == self.OUTLINE:
            self.set_page(self.THUMBNAILS)

    def set_current_page(self, page: int) -> None:
        self.thumbnails.set_current(page)
