"""Tela inicial com a grade de documentos recentes (como o EvRecentView do Evince)."""

from __future__ import annotations

import hashlib
import json
import os

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, QStandardPaths, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QListView, QListWidget, QListWidgetItem, QMenu, QStyle, QStyledItemDelegate

from . import theme
from .document import Document

THUMB_W, THUMB_H = 120, 160
CELL_W, CELL_H = 170, 250
PATH_ROLE = Qt.ItemDataRole.UserRole
PIXMAP_ROLE = Qt.ItemDataRole.UserRole + 1
AUTHOR_ROLE = Qt.ItemDataRole.UserRole + 2


def _cache_dir() -> str:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    path = os.path.join(base, "thumbnails")
    os.makedirs(path, exist_ok=True)
    return path


def _cache_paths(path: str) -> tuple[str, str]:
    digest = hashlib.sha1(os.path.normcase(os.path.abspath(path)).encode("utf-8")).hexdigest()
    base = os.path.join(_cache_dir(), digest)
    return base + ".png", base + ".json"


def load_thumbnail(path: str, render: bool = True) -> tuple[QImage | None, str, str]:
    """Miniatura da 1ª página + título + autor, com cache em disco (invalidado pela data do arquivo)."""
    png, meta = _cache_paths(path)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None, os.path.basename(path), ""
    try:
        with open(meta, encoding="utf-8") as fh:
            info = json.load(fh)
        if info.get("mtime") == mtime and os.path.exists(png):
            img = QImage(png)
            if not img.isNull():
                return img, info.get("title", ""), info.get("author", "")
    except (OSError, ValueError):
        pass
    if not render:
        return None, os.path.basename(path), ""
    try:
        doc = Document(path)
    except Exception:
        return None, os.path.basename(path), ""
    try:
        w, h = doc.page_size(0)
        scale = min(THUMB_W * 2 / w, THUMB_H * 2 / h)
        img = doc.render(0, scale)
        title, author = doc.title, doc.author
    finally:
        doc.close()
    try:
        img.save(png, "PNG")
        with open(meta, "w", encoding="utf-8") as fh:
            json.dump({"mtime": mtime, "title": title, "author": author}, fh)
    except OSError:
        pass
    return img, title, author


def store_thumbnail(doc: Document) -> None:
    """Atualiza o cache ao abrir um documento (assim a tela inicial já tem a miniatura)."""
    png, _meta = _cache_paths(doc.path)
    if not os.path.exists(png):
        load_thumbnail(doc.path)


class _RecentDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index) -> QSize:
        return QSize(CELL_W, CELL_H)

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if hovered or selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 18) if not selected else QColor(53, 132, 228, 40))
            painter.drawRoundedRect(QRectF(rect.adjusted(4, 4, -4, -4)), 8, 8)

        pm: QPixmap | None = index.data(PIXMAP_ROLE)
        area = QRect(rect.left() + (CELL_W - THUMB_W) // 2, rect.top() + 14, THUMB_W, THUMB_H)
        if pm is not None and not pm.isNull():
            size = pm.size().toSizeF() / pm.devicePixelRatio()
            size.scale(area.size().toSizeF(), Qt.AspectRatioMode.KeepAspectRatio)
            thumb = QRectF(area.center().x() - size.width() / 2, area.bottom() - size.height(),
                           size.width(), size.height())
        else:
            thumb = QRectF(area.left() + 10, area.top(), THUMB_W - 20, THUMB_H)
        for spread, alpha in ((3, 14), (2, 22), (1, 36)):
            painter.fillRect(thumb.adjusted(-spread, -spread + 1, spread, spread + 1), QColor(60, 64, 67, alpha))
        painter.fillRect(thumb, QColor("white"))
        if pm is not None and not pm.isNull():
            painter.drawPixmap(thumb, pm, QRectF(pm.rect()))

        text_rect = QRect(rect.left() + 8, area.bottom() + 10, CELL_W - 16, 40)
        font = QFont(option.font)
        painter.setFont(font)
        painter.setPen(QColor(theme.FG))
        fm = QFontMetrics(font)
        title = index.data(Qt.ItemDataRole.DisplayRole) or ""
        lines = _wrap(title, fm, text_rect.width(), 2)
        y = text_rect.top()
        for line in lines:
            painter.drawText(QRect(text_rect.left(), y, text_rect.width(), fm.height()), Qt.AlignmentFlag.AlignHCenter, line)
            y += fm.height()
        author = index.data(AUTHOR_ROLE) or ""
        if author:
            small = QFont(font)
            small.setPointSizeF(font.pointSizeF() * 0.82)
            painter.setFont(small)
            painter.setPen(QColor(46, 52, 54, 140))
            fms = QFontMetrics(small)
            painter.drawText(QRect(text_rect.left(), y + 2, text_rect.width(), fms.height()), Qt.AlignmentFlag.AlignHCenter,
                             fms.elidedText(author, Qt.TextElideMode.ElideRight, text_rect.width()))
        painter.restore()


def _wrap(text: str, fm: QFontMetrics, width: int, max_lines: int) -> list[str]:
    words, lines, i = text.split(), [], 0
    while i < len(words) and len(lines) < max_lines - 1:
        line = words[i]
        i += 1
        while i < len(words) and fm.horizontalAdvance(f"{line} {words[i]}") <= width:
            line = f"{line} {words[i]}"
            i += 1
        lines.append(fm.elidedText(line, Qt.TextElideMode.ElideRight, width))
    if i < len(words):
        lines.append(fm.elidedText(" ".join(words[i:]), Qt.TextElideMode.ElideRight, width))
    return lines


class RecentView(QListWidget):
    openRequested = Signal(str)
    removeRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setGridSize(QSize(CELL_W + 12, CELL_H + 12))
        self.setItemDelegate(_RecentDelegate(self))
        self.setMouseTracking(True)
        self.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setStyleSheet(f"QListWidget {{ background: {theme.BG}; padding: 24px; }}")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self.itemActivated.connect(lambda item: self.openRequested.emit(item.data(PATH_ROLE)))
        self._pending: list[QListWidgetItem] = []
        self._timer = QTimer(self)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._load_next)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        item = self.itemAt(event.position().toPoint())
        if item is not None and event.button() == Qt.MouseButton.LeftButton:
            self.openRequested.emit(item.data(PATH_ROLE))

    def set_files(self, paths: list[str]) -> None:
        self.clear()
        self._pending = []
        for path in paths:
            if not os.path.exists(path):
                continue
            img, title, author = load_thumbnail(path, render=False)
            item = QListWidgetItem(title or os.path.basename(path))
            item.setData(PATH_ROLE, path)
            item.setData(AUTHOR_ROLE, author)
            item.setToolTip(path)
            if img is not None:
                item.setData(PIXMAP_ROLE, QPixmap.fromImage(img))
            else:
                self._pending.append(item)
            self.addItem(item)
        if self._pending:
            self._timer.start()

    def _load_next(self) -> None:
        if not self._pending:
            self._timer.stop()
            return
        item = self._pending.pop(0)
        try:
            path = item.data(PATH_ROLE)
        except RuntimeError:  # item já removido
            return
        img, title, author = load_thumbnail(path)
        if img is not None:
            item.setData(PIXMAP_ROLE, QPixmap.fromImage(img))
        if title:
            item.setText(title)
        item.setData(AUTHOR_ROLE, author)

    def _context_menu(self, pos: QPoint) -> None:
        item = self.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        open_action = menu.addAction("Abrir")
        remove_action = menu.addAction("Remover da lista")
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        path = item.data(PATH_ROLE)
        if chosen == open_action:
            self.openRequested.emit(path)
        elif chosen == remove_action:
            self.removeRequested.emit(path)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.count() == 0:
            painter = QPainter(self.viewport())
            font = QFont(self.font())
            font.setPointSizeF(font.pointSizeF() * 1.6)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(theme.DIM_FG))
            r = self.viewport().rect()
            painter.drawText(r.adjusted(0, -40, 0, -40), Qt.AlignmentFlag.AlignCenter, "Nenhum documento recente")
            small = QFont(self.font())
            painter.setFont(small)
            painter.drawText(r.adjusted(0, 20, 0, 20), Qt.AlignmentFlag.AlignCenter,
                             "Clique em “Abrir…” ou arraste um arquivo para esta janela")
