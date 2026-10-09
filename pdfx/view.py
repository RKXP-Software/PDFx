"""Área de visualização das páginas (equivalente ao EvView do Evince).

Desenha só as páginas visíveis, renderiza em segundo plano (um bloco por ciclo do
event loop) e divide páginas muito grandes em blocos (tiles) para zoom alto.
"""

from __future__ import annotations

import bisect
import math
from collections import OrderedDict
from enum import Enum

import pymupdf
from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication, QPainter, QPixmap
from PySide6.QtWidgets import QAbstractScrollArea, QFrame, QToolTip

from . import theme
from .document import Document


class FitMode(str, Enum):
    NONE = "none"
    WIDTH = "width"
    PAGE = "page"


ZOOM_LEVELS = (0.1, 0.25, 0.33, 0.5, 0.7, 0.85, 1.0, 1.25, 1.5, 1.75, 2.0, 3.0, 4.0, 6.0, 8.0)
MIN_ZOOM, MAX_ZOOM = 0.1, 8.0
MARGIN = 14
SPACING = 14
TILE = 1024
FULL_PAGE_LIMIT = 2600 * 2600  # acima disso (em pixels de tela) a página é renderizada em blocos
SAFE_URL_SCHEMES = ("http", "https", "mailto")


class _PixmapCache:
    """Cache LRU de páginas renderizadas, limitado por memória."""

    def __init__(self, budget_bytes: int = 400 * 1024 * 1024):
        self._items: OrderedDict = OrderedDict()
        self._bytes = 0
        self._budget = budget_bytes

    def __contains__(self, key) -> bool:
        return key in self._items

    def get(self, key):
        pm = self._items.get(key)
        if pm is not None:
            self._items.move_to_end(key)
        return pm

    def put(self, key, pm: QPixmap) -> None:
        old = self._items.pop(key, None)
        if old is not None:
            self._bytes -= old.width() * old.height() * 4
        self._items[key] = pm
        self._bytes += pm.width() * pm.height() * 4
        while self._bytes > self._budget and len(self._items) > 1:
            _, evicted = self._items.popitem(last=False)
            self._bytes -= evicted.width() * evicted.height() * 4

    def fallback(self, page: int, rotation: int, inverted: bool):
        """Qualquer renderização completa da página (outro zoom) para mostrar enquanto a nova não fica pronta."""
        best, best_scale = None, -1.0
        for (p, scale, rot, inv, tile), pm in self._items.items():
            if p == page and rot == rotation and inv == inverted and tile is None and scale > best_scale:
                best, best_scale = pm, scale
        return best

    def clear(self) -> None:
        self._items.clear()
        self._bytes = 0


class PageView(QAbstractScrollArea):
    currentPageChanged = Signal(int)
    zoomChanged = Signal()
    selectionChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().setMouseTracking(True)
        self.viewport().setAutoFillBackground(False)

        self.doc: Document | None = None
        self._zoom = 1.0
        self._fit = FitMode.WIDTH
        self._rotation = 0
        self._dual = False
        self._continuous = True
        self._inverted = False

        self._rects: list[QRectF | None] = []
        self._rows_all: list[list[int]] = []
        self._layout_rows: list[list[int]] = []
        self._row_tops: list[float] = []
        self._content = QSize(0, 0)
        self._current = 0
        self._in_layout = False

        self._cache = _PixmapCache()
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(0)
        self._render_timer.timeout.connect(self._render_tick)

        self._find: dict[int, list] = {}
        self._find_active: tuple[int, pymupdf.Rect] | None = None

        self._sel_page = -1
        self._sel_anchor: pymupdf.Point | None = None
        self._sel_range: tuple[int, int] | None = None

        self._press_pos: QPointF | None = None
        self._press_link: dict | None = None
        self._pan: tuple[QPointF, int, int] | None = None
        self._flip_clock = QElapsedTimer()
        self._flip_clock.start()

    # ------------------------------------------------------------------ API
    def set_document(self, doc: Document | None, state: dict | None = None) -> None:
        self.doc = doc
        self._cache.clear()
        self._find, self._find_active = {}, None
        self._clear_selection(emit=False)
        if doc is None:
            self._current = 0
            self._relayout()
            return
        st = state or {}
        self._rotation = int(st.get("rotation", 0)) % 360
        self._dual = bool(st.get("dual", False))
        self._continuous = bool(st.get("continuous", True))
        self._inverted = bool(st.get("inverted", self._inverted))
        try:
            self._fit = FitMode(st.get("fit", FitMode.WIDTH.value))
        except ValueError:
            self._fit = FitMode.WIDTH
        self._zoom = self._clamp_zoom(float(st.get("zoom", 1.0)))
        page = min(max(int(st.get("page", 0)), 0), doc.page_count - 1)
        self._current = page
        self._relayout()
        self.go_to_page(page)
        self.currentPageChanged.emit(self._current)

    def reload_document(self, doc: Document) -> None:
        """Troca o documento mantendo a posição de leitura (usado quando o arquivo muda no disco)."""
        anchor = self._anchor_at(QPointF(self.viewport().width() / 2, 0))
        self.doc = doc
        self._cache.clear()
        self._find, self._find_active = {}, None
        self._clear_selection(emit=False)
        self._current = min(self._current, doc.page_count - 1)
        self._relayout(anchor)

    def state(self) -> dict:
        return {
            "page": self._current,
            "zoom": self._zoom,
            "fit": self._fit.value,
            "rotation": self._rotation,
            "dual": self._dual,
            "continuous": self._continuous,
        }

    def current_page(self) -> int:
        return self._current

    def zoom(self) -> float:
        return self._zoom

    def fit_mode(self) -> FitMode:
        return self._fit

    @property
    def rotation(self) -> int:
        return self._rotation

    @property
    def dual(self) -> bool:
        return self._dual

    @property
    def continuous(self) -> bool:
        return self._continuous

    @property
    def inverted(self) -> bool:
        return self._inverted

    def set_zoom(self, zoom: float, anchor_pos: QPointF | None = None) -> None:
        if self.doc is None:
            return
        if anchor_pos is None:
            anchor_pos = QPointF(self.viewport().width() / 2, self.viewport().height() / 2)
        anchor = self._anchor_at(anchor_pos)
        self._fit = FitMode.NONE
        self._zoom = self._clamp_zoom(zoom)
        self._relayout(anchor)

    def set_fit(self, mode: FitMode) -> None:
        self._fit = FitMode(mode)
        if self.doc is not None:
            page = self._current
            self._relayout(self._anchor_at(QPointF(self.viewport().width() / 2, 0)))
            if self._fit == FitMode.PAGE:
                self.go_to_page(page)
        self.zoomChanged.emit()

    def zoom_in(self) -> None:
        steps = [z for z in ZOOM_LEVELS if z > self._zoom * 1.01]
        self.set_zoom(steps[0] if steps else MAX_ZOOM)

    def zoom_out(self) -> None:
        steps = [z for z in ZOOM_LEVELS if z < self._zoom * 0.99]
        self.set_zoom(steps[-1] if steps else MIN_ZOOM)

    def rotate(self, delta: int) -> None:
        self._rotation = (self._rotation + delta) % 360
        self._relayout_keep_page()

    def set_dual(self, dual: bool) -> None:
        self._dual = bool(dual)
        self._relayout_keep_page()

    def set_continuous(self, continuous: bool) -> None:
        self._continuous = bool(continuous)
        self._relayout_keep_page()

    def set_inverted(self, inverted: bool) -> None:
        self._inverted = bool(inverted)
        self.viewport().update()
        self._schedule_render()

    def go_to_page(self, index: int, point: pymupdf.Point | None = None) -> None:
        if self.doc is None:
            return
        index = min(max(index, 0), self.doc.page_count - 1)
        if not self._continuous and self._rects[index] is None:
            self._current = index
            self._relayout()
        r = self._rects[index]
        if r is None:
            return
        y = r.top() - MARGIN
        if point is not None:
            try:
                p = pymupdf.Point(point) * self.doc.transform(index, self._scale(), self._rotation)
                y = r.top() + p.y - MARGIN
            except Exception:
                pass
        self.verticalScrollBar().setValue(round(y))
        if r.width() > self.viewport().width():
            self.horizontalScrollBar().setValue(round(r.left() - MARGIN))
        if self._current != index:
            self._current = index
            self.currentPageChanged.emit(index)
        self.viewport().update()

    def next_page(self) -> None:
        self.go_to_page(self._current + (2 if self._dual else 1))

    def previous_page(self) -> None:
        self.go_to_page(self._current - (2 if self._dual else 1))

    # ---- busca
    def set_find_results(self, results: dict[int, list]) -> None:
        self._find = results
        self.viewport().update()

    def set_active_find(self, page: int | None, rect: pymupdf.Rect | None) -> None:
        self._find_active = (page, rect) if page is not None and rect is not None else None
        if self._find_active:
            self._ensure_visible(page, rect)
        self.viewport().update()

    # ---- seleção
    def has_selection(self) -> bool:
        return self._sel_range is not None

    def selected_text(self) -> str:
        if self.doc is None or self._sel_range is None:
            return ""
        return self.doc.text_between(self._sel_page, *self._sel_range)

    def copy_selection(self) -> None:
        text = self.selected_text()
        if text:
            QGuiApplication.clipboard().setText(text)

    def select_all_on_page(self) -> None:
        if self.doc is None:
            return
        words = self.doc.words(self._current)
        if words:
            self._sel_page = self._current
            self._sel_range = (0, len(words) - 1)
            self.viewport().update()
            self.selectionChanged.emit(True)

    # ------------------------------------------------------------ geometria
    @staticmethod
    def _clamp_zoom(z: float) -> float:
        return min(max(z, MIN_ZOOM), MAX_ZOOM)

    def _dpi_scale(self) -> float:
        return self.logicalDpiX() / 72.0

    def _scale(self) -> float:
        return self._zoom * self._dpi_scale()

    def _row_of(self, page: int) -> int:
        return page // 2 if self._dual else page

    def _all_rows(self) -> list[list[int]]:
        n = self.doc.page_count
        if self._dual:
            return [list(range(i, min(i + 2, n))) for i in range(0, n, 2)]
        return [[i] for i in range(n)]

    def _available_size(self) -> tuple[int, int]:
        vw, vh = self.viewport().width(), self.viewport().height()
        if not self.verticalScrollBar().isVisible():
            vw -= self.verticalScrollBar().sizeHint().width()
        return vw, vh

    def _fit_zoom(self) -> float:
        vw, vh = self._available_size()
        dpi = self._dpi_scale()
        if self._fit == FitMode.WIDTH:
            rows = self._rows_all
        else:
            rows = [self._rows_all[min(self._row_of(self._current), len(self._rows_all) - 1)]]
        best = None
        for row in rows:
            sizes = [self.doc.page_size(i, self._rotation) for i in row]
            w_pts = sum(s[0] for s in sizes)
            h_pts = max(s[1] for s in sizes)
            gaps = SPACING * (len(row) - 1)
            z = (vw - 2 * MARGIN - gaps) / (w_pts * dpi)
            if self._fit == FitMode.PAGE:
                z = min(z, (vh - 2 * MARGIN) / (h_pts * dpi))
            best = z if best is None else min(best, z)
        return self._clamp_zoom(best or 1.0)

    def _relayout(self, anchor=None) -> None:
        if self.doc is None:
            self._rects, self._rows_all, self._layout_rows, self._row_tops = [], [], [], []
            self._content = QSize(0, 0)
            self._update_scrollbars()
            self.viewport().update()
            return
        self._in_layout = True
        try:
            self._rows_all = self._all_rows()
            if self._fit != FitMode.NONE:
                self._zoom = self._fit_zoom()
            scale = self._scale()
            if self._continuous:
                rows = self._rows_all
            else:
                rows = [self._rows_all[min(self._row_of(self._current), len(self._rows_all) - 1)]]
            rects: list[QRectF | None] = [None] * self.doc.page_count
            specs = []
            y = float(MARGIN)
            content_w = 0.0
            for row in rows:
                sizes = [self.doc.page_size(i, self._rotation) for i in row]
                sizes = [(w * scale, h * scale) for w, h in sizes]
                row_w = sum(s[0] for s in sizes) + SPACING * (len(row) - 1)
                row_h = max(s[1] for s in sizes)
                specs.append((row, sizes, row_w, row_h, y))
                y += row_h + SPACING
                content_w = max(content_w, row_w)
            content_w += 2 * MARGIN
            content_h = y - SPACING + MARGIN
            tops = []
            for row, sizes, row_w, row_h, top in specs:
                x = (content_w - row_w) / 2
                for idx, (w, h) in zip(row, sizes):
                    rects[idx] = QRectF(x, top + (row_h - h) / 2, w, h)
                    x += w + SPACING
                tops.append(top)
            self._rects = rects
            self._layout_rows = rows
            self._row_tops = tops
            self._content = QSize(math.ceil(content_w), math.ceil(content_h))
            self._update_scrollbars()
            if anchor is not None:
                self._restore_anchor(anchor)
        finally:
            self._in_layout = False
        self.viewport().update()
        self._update_current_page()
        self._schedule_render()
        self.zoomChanged.emit()

    def _relayout_keep_page(self) -> None:
        if self.doc is None:
            return
        page = self._current
        self._relayout()
        self.go_to_page(page)

    def _update_scrollbars(self) -> None:
        vw, vh = self.viewport().width(), self.viewport().height()
        h, v = self.horizontalScrollBar(), self.verticalScrollBar()
        h.setRange(0, max(0, self._content.width() - vw))
        h.setPageStep(max(1, vw))
        h.setSingleStep(48)
        v.setRange(0, max(0, self._content.height() - vh))
        v.setPageStep(max(1, int(vh * 0.9)))
        v.setSingleStep(48)

    def _x_off(self) -> float:
        return max(0.0, (self.viewport().width() - self._content.width()) / 2)

    def _y_off(self) -> float:
        return max(0.0, (self.viewport().height() - self._content.height()) / 2)

    def _offset(self) -> QPointF:
        return QPointF(self._x_off() - self.horizontalScrollBar().value(),
                       self._y_off() - self.verticalScrollBar().value())

    def _to_layout(self, pos: QPointF) -> QPointF:
        return QPointF(pos) - self._offset()

    def _visible_layout_rect(self) -> QRectF:
        return QRectF(self._to_layout(QPointF(0, 0)), QSize(self.viewport().width(), self.viewport().height()).toSizeF())

    def _visible_pages(self) -> list[int]:
        if not self._layout_rows:
            return []
        vis = self._visible_layout_rect()
        start = max(0, bisect.bisect_right(self._row_tops, vis.top()) - 1)
        pages = []
        for ri in range(start, len(self._layout_rows)):
            if self._row_tops[ri] > vis.bottom():
                break
            for p in self._layout_rows[ri]:
                r = self._rects[p]
                if r is not None and r.intersects(vis):
                    pages.append(p)
        return pages

    def _page_at(self, lp: QPointF) -> int:
        ri = bisect.bisect_right(self._row_tops, lp.y()) - 1
        ri = min(max(ri, 0), len(self._layout_rows) - 1)
        row = self._layout_rows[ri]

        def dist(p):
            r = self._rects[p]
            return 0 if r.left() <= lp.x() <= r.right() else min(abs(lp.x() - r.left()), abs(lp.x() - r.right()))

        return min(row, key=dist)

    def _anchor_at(self, pos: QPointF):
        if self.doc is None or not self._layout_rows:
            return None
        lp = self._to_layout(pos)
        page = self._page_at(lp)
        r = self._rects[page]
        return page, (lp.x() - r.left()) / r.width(), (lp.y() - r.top()) / r.height(), QPointF(pos)

    def _restore_anchor(self, anchor) -> None:
        page, fx, fy, pos = anchor
        page = min(page, len(self._rects) - 1)
        r = self._rects[page] if page >= 0 else None
        if r is None:
            return
        target = QPointF(r.left() + fx * r.width(), r.top() + fy * r.height())
        self.horizontalScrollBar().setValue(round(target.x() - pos.x() + self._x_off()))
        self.verticalScrollBar().setValue(round(target.y() - pos.y() + self._y_off()))

    def _update_current_page(self) -> None:
        if self.doc is None or not self._continuous:
            return
        vis = self._visible_layout_rect()
        best, best_h = -1, -1.0
        for p in self._visible_pages():
            h = self._rects[p].intersected(vis).height()
            if h > best_h + 0.5:
                best, best_h = p, h
        if best >= 0 and best != self._current:
            self._current = best
            self.currentPageChanged.emit(best)

    def _ensure_visible(self, page: int, rect: pymupdf.Rect) -> None:
        if self._rects[page] is None:
            self.go_to_page(page)
        r = self._rects[page]
        m = self.doc.transform(page, self._scale(), self._rotation)
        pr = pymupdf.Rect(rect) * m
        target = QRectF(r.left() + pr.x0, r.top() + pr.y0, pr.width, pr.height)
        vis = self._visible_layout_rect().adjusted(20, 20, -20, -20)
        if not vis.contains(target):
            v, h = self.verticalScrollBar(), self.horizontalScrollBar()
            if target.top() < vis.top() or target.bottom() > vis.bottom():
                v.setValue(round(target.center().y() - self.viewport().height() / 2 + self._y_off()))
            if target.left() < vis.left() or target.right() > vis.right():
                h.setValue(round(target.center().x() - self.viewport().width() / 2 + self._x_off()))

    # ------------------------------------------------------------ renderização
    def _key(self, page: int, scale_px: float, tile):
        return (page, round(scale_px, 4), self._rotation, self._inverted, tile)

    def _tiles(self, page: int, target: QRectF, dpr: float):
        """Blocos da página que precisam ser desenhados: [(tile, clip_px, destino_na_tela)]."""
        W = max(1, round(target.width() * dpr))
        H = max(1, round(target.height() * dpr))
        if W * H <= FULL_PAGE_LIMIT:
            return [(None, None, target)]
        vis = QRectF(self.viewport().rect()).intersected(target)
        if vis.isEmpty():
            return []
        local = vis.translated(-target.topLeft())
        tx0 = max(0, int(local.left() * dpr) // TILE)
        ty0 = max(0, int(local.top() * dpr) // TILE)
        tx1 = min((W - 1) // TILE, int(math.ceil(local.right() * dpr)) // TILE)
        ty1 = min((H - 1) // TILE, int(math.ceil(local.bottom() * dpr)) // TILE)
        tiles = []
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                x0, y0 = tx * TILE, ty * TILE
                x1, y1 = min(x0 + TILE, W), min(y0 + TILE, H)
                dest = QRectF(target.left() + x0 / dpr, target.top() + y0 / dpr, (x1 - x0) / dpr, (y1 - y0) / dpr)
                tiles.append(((tx, ty), (x0, y0, x1, y1), dest))
        return tiles

    def _schedule_render(self) -> None:
        if self.doc is not None and not self._render_timer.isActive():
            self._render_timer.start()

    def _render_tick(self) -> None:
        if self.doc is None:
            return
        dpr = self.devicePixelRatioF()
        scale_px = self._scale() * dpr
        off = self._offset()
        pages = self._visible_pages()
        jobs = []
        for p in pages:
            for tile, clip, _dest in self._tiles(p, self._rects[p].translated(off), dpr):
                jobs.append((p, tile, clip, True))
        if pages:  # pré-carrega as páginas vizinhas
            for p in (pages[-1] + 1, pages[0] - 1):
                if 0 <= p < self.doc.page_count and self._rects[p] is not None:
                    tiles = self._tiles(p, self._rects[p].translated(off), dpr)
                    if len(tiles) == 1 and tiles[0][0] is None:
                        jobs.append((p, None, None, False))
        for p, tile, clip, visible in jobs:
            key = self._key(p, scale_px, tile)
            if key in self._cache:
                continue
            try:
                img = self.doc.render(p, scale_px, self._rotation, self._inverted, clip)
            except Exception:
                img = None
            pm = QPixmap.fromImage(img) if img is not None and not img.isNull() else QPixmap(1, 1)
            pm.setDevicePixelRatio(dpr)
            self._cache.put(key, pm)
            if visible:
                self.viewport().update()
            self._render_timer.start()
            return

    # ------------------------------------------------------------ pintura
    def paintEvent(self, event) -> None:
        painter = QPainter(self.viewport())
        painter.fillRect(event.rect(), theme.VIEW_BG)
        if self.doc is None:
            return
        dpr = self.devicePixelRatioF()
        scale = self._scale()
        scale_px = scale * dpr
        off = self._offset()
        missing = False
        page_bg = QColor("black") if self._inverted else QColor("white")
        for p in self._visible_pages():
            target = self._rects[p].translated(off)
            self._paint_shadow(painter, target)
            painter.fillRect(target, page_bg)
            tiles = self._tiles(p, target, dpr)
            ready = [(dest, self._cache.get(self._key(p, scale_px, tile))) for tile, _clip, dest in tiles]
            if any(pm is None for _dest, pm in ready):
                missing = True
                fallback = self._cache.fallback(p, self._rotation, self._inverted)
                if fallback is not None:
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                    painter.drawPixmap(target, fallback, QRectF(fallback.rect()))
                    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            for dest, pm in ready:
                if pm is not None:
                    painter.drawPixmap(dest, pm, QRectF(pm.rect()))
            self._paint_overlays(painter, p, target, scale)
        if missing:
            self._schedule_render()

    @staticmethod
    def _paint_shadow(painter: QPainter, r: QRectF) -> None:
        # box-shadow: rgba(60,64,67,.2) 0 2px 3px 1px, rgba(60,64,67,.3) 0 1px 3px 1px  (evince.css)
        c = QColor(theme.PAGE_SHADOW)
        for dx, top, bottom, alpha in ((3, 0, 5, 14), (2, 0, 4, 22), (1, 0, 3, 34), (1, 0, 1, 40)):
            c.setAlpha(alpha)
            painter.fillRect(r.adjusted(-dx, top - dx + 1, dx, bottom), c)

    def _paint_overlays(self, painter: QPainter, page: int, target: QRectF, scale: float) -> None:
        finds = self._find.get(page)
        active = self._find_active if self._find_active and self._find_active[0] == page else None
        selected = self._sel_range if self._sel_page == page else None
        if not finds and not active and not selected:
            return
        m = self.doc.transform(page, scale, self._rotation)

        def to_view(rect) -> QRectF:
            r = pymupdf.Rect(rect) * m
            return QRectF(target.left() + r.x0, target.top() + r.y0, r.width, r.height)

        for r in finds or ():
            painter.fillRect(to_view(r), theme.FIND_RESULT)
        if active:
            painter.fillRect(to_view(active[1]), theme.FIND_ACTIVE)
        if selected:
            words = self.doc.words(page)[selected[0]:selected[1] + 1]
            lines: dict[tuple, pymupdf.Rect] = {}
            for w in words:
                key = (w[5], w[6])
                rect = pymupdf.Rect(w[:4])
                lines[key] = lines[key] | rect if key in lines else rect
            for rect in lines.values():
                painter.fillRect(to_view(rect), theme.SELECTION)

    # ------------------------------------------------------------ eventos
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._in_layout:
            self._update_scrollbars()
            return
        if self.doc is not None:
            self._relayout(self._anchor_at(QPointF(self.viewport().width() / 2, 0)))

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        self.viewport().update()
        if not self._in_layout:
            self._update_current_page()
            self._schedule_render()

    def wheelEvent(self, event) -> None:
        if self.doc is None:
            return
        dy = event.angleDelta().y()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if dy:
                self.set_zoom(self._zoom * (1.1 ** (dy / 120)), event.position())
            event.accept()
            return
        if not self._continuous and dy:
            v = self.verticalScrollBar()
            if dy < 0 and v.value() >= v.maximum():
                self._flip(1)
                event.accept()
                return
            if dy > 0 and v.value() <= v.minimum():
                self._flip(-1, to_bottom=True)
                event.accept()
                return
        super().wheelEvent(event)

    def _flip(self, direction: int, to_bottom: bool = False) -> None:
        """Modo não contínuo: troca de página quando a rolagem chega ao limite."""
        if self._flip_clock.elapsed() < 300:
            return
        self._flip_clock.restart()
        step = 2 if self._dual else 1
        target = self._current + direction * step
        if 0 <= target < self.doc.page_count:
            self.go_to_page(target)
            if to_bottom:
                self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def keyPressEvent(self, event) -> None:
        if self.doc is None:
            return super().keyPressEvent(event)
        key = event.key()
        mods = event.modifiers()
        v, h = self.verticalScrollBar(), self.horizontalScrollBar()
        if key == Qt.Key.Key_Home:
            self.go_to_page(0)
        elif key == Qt.Key.Key_End:
            self.go_to_page(self.doc.page_count - 1)
            v.setValue(v.maximum())
        elif key in (Qt.Key.Key_Space, Qt.Key.Key_PageDown, Qt.Key.Key_PageUp, Qt.Key.Key_Backspace):
            forward = key in (Qt.Key.Key_Space, Qt.Key.Key_PageDown)
            if key == Qt.Key.Key_Space and mods & Qt.KeyboardModifier.ShiftModifier:
                forward = False
            if not self._continuous:
                at_end = v.value() >= v.maximum() if forward else v.value() <= v.minimum()
                if at_end:
                    self._flip(1 if forward else -1, to_bottom=not forward)
                    return
            v.triggerAction(v.SliderAction.SliderPageStepAdd if forward else v.SliderAction.SliderPageStepSub)
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right) and h.maximum() == 0:
            self.previous_page() if key == Qt.Key.Key_Left else self.next_page()
        else:
            super().keyPressEvent(event)

    # ---- mouse: seleção de texto, links e arrastar com o botão do meio
    def _hit(self, pos: QPointF):
        if self.doc is None:
            return None
        lp = self._to_layout(pos)
        for p in self._visible_pages():
            if self._rects[p].contains(lp):
                return p, self._pdf_point(p, pos)
        return None

    def _pdf_point(self, page: int, pos: QPointF) -> pymupdf.Point:
        lp = self._to_layout(pos)
        r = self._rects[page]
        inv = ~self.doc.transform(page, self._scale(), self._rotation)
        return pymupdf.Point(lp.x() - r.left(), lp.y() - r.top()) * inv

    def _link_at(self, hit) -> dict | None:
        if hit is None:
            return None
        page, pt = hit
        for link in self.doc.links(page):
            rect = link.get("from")
            if rect is not None and pymupdf.Rect(rect).contains(pt):
                return link
        return None

    @staticmethod
    def _nearest_word(words: list, pt: pymupdf.Point) -> int:
        best, best_d = 0, float("inf")
        for i, w in enumerate(words):
            dx = max(w[0] - pt.x, 0.0, pt.x - w[2])
            dy = max(w[1] - pt.y, 0.0, pt.y - w[3])
            d = dy * 4 + dx  # prioriza palavras da mesma linha
            if d < best_d:
                best, best_d = i, d
        return best

    def _clear_selection(self, emit: bool = True) -> None:
        had = self._sel_range is not None
        self._sel_page, self._sel_anchor, self._sel_range = -1, None, None
        if had:
            self.viewport().update()
            if emit:
                self.selectionChanged.emit(False)

    def mousePressEvent(self, event) -> None:
        if self.doc is None:
            return
        self.setFocus()
        pos = event.position()
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan = (pos, self.horizontalScrollBar().value(), self.verticalScrollBar().value())
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        hit = self._hit(pos)
        self._press_pos = pos
        self._press_link = self._link_at(hit)
        if self._press_link is None:
            self._clear_selection()
            if hit is not None:
                self._sel_page, self._sel_anchor = hit

    def mouseMoveEvent(self, event) -> None:
        if self.doc is None:
            return
        pos = event.position()
        if self._pan is not None:
            origin, hx, vy = self._pan
            delta = pos - origin
            self.horizontalScrollBar().setValue(round(hx - delta.x()))
            self.verticalScrollBar().setValue(round(vy - delta.y()))
            return
        if event.buttons() & Qt.MouseButton.LeftButton:
            if (self._sel_page >= 0 and self._press_pos is not None and self._press_link is None
                    and (pos - self._press_pos).manhattanLength() > 3):
                words = self.doc.words(self._sel_page)
                if words:
                    a = self._nearest_word(words, self._sel_anchor)
                    b = self._nearest_word(words, self._pdf_point(self._sel_page, pos))
                    self._sel_range = (min(a, b), max(a, b))
                    self.viewport().update()
            return
        hit = self._hit(pos)
        link = self._link_at(hit)
        if link is not None:
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            uri = link.get("uri")
            tip = uri if uri else (f"Ir para a página {link['page'] + 1}" if link.get("page", -1) >= 0 else "")
            if tip:
                QToolTip.showText(event.globalPosition().toPoint(), tip, self.viewport())
            return
        QToolTip.hideText()
        cursor = Qt.CursorShape.ArrowCursor
        if hit is not None:
            page, pt = hit
            for w in self.doc.words(page):
                if w[0] <= pt.x <= w[2] and w[1] <= pt.y <= w[3]:
                    cursor = Qt.CursorShape.IBeamCursor
                    break
        self.viewport().setCursor(cursor)

    def mouseReleaseEvent(self, event) -> None:
        if self._pan is not None and event.button() == Qt.MouseButton.MiddleButton:
            self._pan = None
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        link, press = self._press_link, self._press_pos
        self._press_link, self._press_pos = None, None
        if link is not None and press is not None and (event.position() - press).manhattanLength() <= 4:
            self._follow_link(link)
            return
        if self._sel_range is not None:
            self.selectionChanged.emit(True)

    def mouseDoubleClickEvent(self, event) -> None:
        if self.doc is None or event.button() != Qt.MouseButton.LeftButton:
            return
        hit = self._hit(event.position())
        if hit is None:
            return
        page, pt = hit
        words = self.doc.words(page)
        for i, w in enumerate(words):
            if w[0] <= pt.x <= w[2] and w[1] <= pt.y <= w[3]:
                self._sel_page, self._sel_range = page, (i, i)
                self.viewport().update()
                self.selectionChanged.emit(True)
                return

    def _follow_link(self, link: dict) -> None:
        uri = link.get("uri")
        if uri:
            url = QUrl(uri)
            if url.scheme().lower() in SAFE_URL_SCHEMES:
                QDesktopServices.openUrl(url)
            return
        page = link.get("page", -1)
        if page is not None and page >= 0:
            self.go_to_page(page, link.get("to"))

    # ---- mensagem quando não há documento
    def sizeHint(self) -> QSize:
        return QSize(800, 600)
