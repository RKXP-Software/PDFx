"""Ícones simbólicos no estilo Adwaita, desenhados em SVG e coloridos conforme o estado."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QIconEngine, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import theme

# Todos os ícones usam uma grade de 16x16, como os ícones simbólicos do GNOME.
# "@C" é substituído pela cor do texto no momento da pintura.
_SVG = {
    "sidebar-show": '<rect x="1.5" y="2.5" width="13" height="11" rx="2" fill="none" stroke="@C"/>'
    '<rect x="2" y="3" width="5" height="10" rx="1.2" fill="@C"/>',
    "open-menu": '<rect x="2" y="3" width="12" height="2" rx="1" fill="@C"/>'
    '<rect x="2" y="7" width="12" height="2" rx="1" fill="@C"/>'
    '<rect x="2" y="11" width="12" height="2" rx="1" fill="@C"/>',
    "edit-find": '<circle cx="6.5" cy="6.5" r="4.25" fill="none" stroke="@C" stroke-width="1.8"/>'
    '<path d="M9.8 9.8L14 14" stroke="@C" stroke-width="2" stroke-linecap="round"/>',
    "go-up": '<path d="M3.5 10.5L8 6l4.5 4.5" fill="none" stroke="@C" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round"/>',
    "go-down": '<path d="M3.5 5.5L8 10l4.5-4.5" fill="none" stroke="@C" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round"/>',
    "pan-down": '<path d="M4 6h8l-4 4.5z" fill="@C"/>',
    "window-close": '<path d="M4.5 4.5l7 7M11.5 4.5l-7 7" stroke="@C" stroke-width="1.6" stroke-linecap="round"/>',
    "window-minimize": '<rect x="4" y="10" width="8" height="1.6" rx=".8" fill="@C"/>',
    "window-maximize": '<rect x="4.3" y="4.3" width="7.4" height="7.4" rx="1" fill="none" stroke="@C" stroke-width="1.5"/>',
    "window-restore": '<rect x="3.8" y="5.8" width="6.4" height="6.4" rx="1" fill="none" stroke="@C" stroke-width="1.4"/>'
    '<path d="M6.2 3.8h5a1 1 0 0 1 1 1v5" fill="none" stroke="@C" stroke-width="1.4"/>',
    "view-grid": '<rect x="2" y="2" width="5" height="5" rx="1" fill="@C"/>'
    '<rect x="9" y="2" width="5" height="5" rx="1" fill="@C"/>'
    '<rect x="2" y="9" width="5" height="5" rx="1" fill="@C"/>'
    '<rect x="9" y="9" width="5" height="5" rx="1" fill="@C"/>',
    "view-index": '<rect x="3" y="1.5" width="10" height="13" rx="1.5" fill="none" stroke="@C" stroke-width="1.2"/>'
    '<rect x="5" y="4" width="6" height="1.4" rx=".7" fill="@C"/>'
    '<rect x="6.5" y="7" width="4.5" height="1.4" rx=".7" fill="@C"/>'
    '<rect x="6.5" y="10" width="4.5" height="1.4" rx=".7" fill="@C"/>',
    "bookmarks": '<path d="M4.5 2h7a.5.5 0 0 1 .5.5V14l-4-3-4 3V2.5a.5.5 0 0 1 .5-.5z" fill="none" '
    'stroke="@C" stroke-width="1.4" stroke-linejoin="round"/>',
    "list-add": '<path d="M8 3v10M3 8h10" stroke="@C" stroke-width="1.8" stroke-linecap="round"/>',
    "list-remove": '<path d="M3 8h10" stroke="@C" stroke-width="1.8" stroke-linecap="round"/>',
    "document-open": '<path d="M1.5 4a1 1 0 0 1 1-1h3.5l1.5 1.5h6a1 1 0 0 1 1 1V12a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1z" '
    'fill="none" stroke="@C" stroke-width="1.3" stroke-linejoin="round"/>',
    "rotate-left": '<path d="M4.2 6.2A4.6 4.6 0 1 1 3.4 9" fill="none" stroke="@C" stroke-width="1.6" stroke-linecap="round"/>'
    '<path d="M2 3.2v4h4z" fill="@C"/>',
    "rotate-right": '<path d="M11.8 6.2A4.6 4.6 0 1 0 12.6 9" fill="none" stroke="@C" stroke-width="1.6" stroke-linecap="round"/>'
    '<path d="M14 3.2v4h-4z" fill="@C"/>',
    "search-small": '<circle cx="6.5" cy="6.5" r="3.8" fill="none" stroke="@C" stroke-width="1.5"/>'
    '<path d="M9.4 9.4L13 13" stroke="@C" stroke-width="1.7" stroke-linecap="round"/>',
}


@lru_cache(maxsize=None)
def _renderer(name: str, color: str) -> QSvgRenderer:
    body = _SVG[name].replace("@C", color)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">{body}</svg>'
    return QSvgRenderer(QByteArray(svg.encode()))


class _SymbolicEngine(QIconEngine):
    def __init__(self, name: str, color: str | None = None):
        super().__init__()
        self._name = name
        self._color = color

    def _color_for(self, mode: QIcon.Mode) -> str:
        if mode == QIcon.Mode.Disabled:
            return "#a8abac"
        if mode == QIcon.Mode.Selected:
            return "#ffffff"
        return self._color or theme.FG

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State) -> None:
        side = min(rect.width(), rect.height())
        target = QRectF(rect.x() + (rect.width() - side) / 2, rect.y() + (rect.height() - side) / 2, side, side)
        _renderer(self._name, self._color_for(mode)).render(painter, target)

    def _image(self, size: QSize, mode: QIcon.Mode, state: QIcon.State, scale: float) -> QPixmap:
        img = QImage(max(1, round(size.width() * scale)), max(1, round(size.height() * scale)),
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.paint(painter, QRect(0, 0, img.width(), img.height()), mode, state)
        painter.end()
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(scale)
        return pm

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        return self._image(size, mode, state, 1.0)

    def scaledPixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State, scale: float) -> QPixmap:
        return self._image(size, mode, state, scale)

    def clone(self) -> QIconEngine:
        return _SymbolicEngine(self._name, self._color)


@lru_cache(maxsize=None)
def icon(name: str, color: str | None = None) -> QIcon:
    return QIcon(_SymbolicEngine(name, color))
