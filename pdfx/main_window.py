"""Janela principal (equivalente ao EvWindow do Evince)."""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

from PySide6.QtCore import QFileSystemWatcher, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog, QInputDialog, QLineEdit, QMainWindow, QMenu, QMessageBox, QSplitter, QStackedWidget,
    QVBoxLayout, QWidget,
)

from . import APP_NAME, frameless
from .dialogs import AboutDialog, PropertiesDialog, ShortcutsDialog
from .document import Document, DocumentError, PasswordRequired, file_filter, is_supported
from .frameless import FramelessMixin
from .headerbar import HeaderBar
from .presentation import PresentationWindow
from .printing import print_document
from .recent import RecentView, store_thumbnail
from .resources import resource_path
from .search import SearchBar, SearchController
from .sidebar import Sidebar
from .view import FitMode, PageView

if TYPE_CHECKING:
    from .app import Application


class MainWindow(FramelessMixin, QMainWindow):
    def __init__(self, ctx: "Application"):
        super().__init__()
        self.ctx = ctx
        self.settings = ctx.settings
        self.doc: Document | None = None
        self._password: str | None = None
        self._presentation: PresentationWindow | None = None
        self._reload_attempts = 0
        self._was_maximized = False

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(resource_path("pdfx.ico")))
        self.setAcceptDrops(True)
        self.setMinimumSize(520, 380)

        # ---- widgets
        self.header = HeaderBar(window_controls=frameless.enabled())
        self.search_bar = SearchBar()
        self.search_bar.hide()
        self.view = PageView()
        self.sidebar = Sidebar()
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.view)
        self.splitter.setStretchFactor(1, 1)
        self.recent = RecentView()
        self.stack = QStackedWidget()
        self.stack.addWidget(self.recent)
        self.stack.addWidget(self.splitter)

        central = QWidget()
        central.setObjectName("Central")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.search_bar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.search = SearchController(self)
        self._search_delay = QTimer(self)
        self._search_delay.setSingleShot(True)
        self._search_delay.setInterval(250)
        self._search_delay.timeout.connect(self._start_search)

        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(lambda _p: self._reload_timer.start())
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(700)
        self._reload_timer.timeout.connect(self._auto_reload)

        self._build_actions()
        self._build_menu()
        self._connect()
        self._setup_frameless(self.header)
        self._show_recent()

    # ------------------------------------------------------------ construção
    def _action(self, text: str, slot, shortcuts=(), checkable: bool = False, needs_doc: bool = True) -> QAction:
        action = QAction(text, self)
        if shortcuts:
            action.setShortcuts([QKeySequence(s) for s in shortcuts])
        action.setCheckable(checkable)
        action.triggered.connect(slot)
        action.setProperty("needs_doc", needs_doc)
        self.addAction(action)
        return action

    def _build_actions(self) -> None:
        a = self._action
        self.act_open = a("Abrir…", self.open_dialog, ["Ctrl+O"], needs_doc=False)
        self.act_save_copy = a("Salvar uma cópia…", self.save_copy, ["Ctrl+S"])
        self.act_print = a("Imprimir…", self.print_doc, ["Ctrl+P"])
        self.act_properties = a("Propriedades", self.show_properties, ["Alt+Return"])
        self.act_reload = a("Recarregar", self.reload, ["Ctrl+R"])
        self.act_close = a("Fechar", self.close, ["Ctrl+W"], needs_doc=False)
        self.act_quit = a("Sair", self.ctx.quit, ["Ctrl+Q"], needs_doc=False)
        self.act_copy = a("Copiar", self.view.copy_selection, [QKeySequence.StandardKey.Copy])
        self.act_select_all = a("Selecionar tudo", self.view.select_all_on_page, [QKeySequence.StandardKey.SelectAll])
        self.act_find = a("Buscar", lambda: self.header.search_button.setChecked(True) or self._focus_search(),
                          ["Ctrl+F"])
        self.act_find_next = a("Próximo resultado", self._find_next, ["F3", "Ctrl+G"])
        self.act_find_prev = a("Resultado anterior", self._find_previous, ["Shift+F3", "Ctrl+Shift+G"])
        self.act_goto = a("Ir para a página…", lambda: self.header.page_entry.focus(), ["Ctrl+L"])
        self.act_sidebar = a("Barra lateral", self._toggle_sidebar_action, ["F9"], checkable=True)
        self.act_next = a("Próxima página", lambda: self.view.next_page(), ["Ctrl+PgDown", "N"])
        self.act_prev = a("Página anterior", lambda: self.view.previous_page(), ["Ctrl+PgUp", "P"])
        self.act_zoom_in = a("Aumentar zoom", lambda: self.view.zoom_in(), ["Ctrl++", "Ctrl+="])
        self.act_zoom_out = a("Diminuir zoom", lambda: self.view.zoom_out(), ["Ctrl+-"])
        self.act_zoom_reset = a("Tamanho original", lambda: self.view.set_zoom(1.0), ["Ctrl+0"])
        self.act_rot_left = a("Girar à esquerda", lambda: self._rotate(-90), ["Ctrl+Left"])
        self.act_rot_right = a("Girar à direita", lambda: self._rotate(90), ["Ctrl+Right"])
        self.act_continuous = a("Contínuo", lambda c: self.view.set_continuous(c), checkable=True)
        self.act_dual = a("Duas páginas", lambda c: self.view.set_dual(c), checkable=True)
        self.act_inverted = a("Cores invertidas", self._set_inverted, ["Ctrl+I"], checkable=True)
        self.act_fullscreen = a("Tela cheia", self.toggle_fullscreen, ["F11"], checkable=True, needs_doc=False)
        self.act_presentation = a("Apresentação", self.start_presentation, ["F5"])
        self.act_bookmark = a("Adicionar marcador", self.add_bookmark, ["Ctrl+D"])
        self.act_shortcuts = a("Atalhos de teclado", lambda: ShortcutsDialog(self).exec(), ["Ctrl+F1"],
                               needs_doc=False)
        self.act_about = a(f"Sobre o {APP_NAME}", lambda: AboutDialog(self).exec(), needs_doc=False)

    def _build_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction(self.act_open)
        self.recent_menu = menu.addMenu("Abrir recente")
        self.recent_menu.aboutToShow.connect(self._fill_recent_menu)
        menu.addAction(self.act_save_copy)
        menu.addAction(self.act_print)
        menu.addSeparator()
        menu.addAction(self.act_fullscreen)
        menu.addAction(self.act_presentation)
        menu.addSeparator()
        menu.addAction(self.act_continuous)
        menu.addAction(self.act_dual)
        menu.addSeparator()
        menu.addAction(self.act_rot_left)
        menu.addAction(self.act_rot_right)
        menu.addAction(self.act_inverted)
        menu.addSeparator()
        menu.addAction(self.act_bookmark)
        menu.addAction(self.act_reload)
        menu.addAction(self.act_properties)
        menu.addSeparator()
        menu.addAction(self.act_shortcuts)
        menu.addAction(self.act_about)
        self.header.menu_button.setMenu(menu)

    def _connect(self) -> None:
        h = self.header
        h.open_button.clicked.connect(self.open_dialog)
        h.sidebar_button.toggled.connect(self.set_sidebar_visible)
        h.page_entry.pageRequested.connect(lambda p: (self.view.go_to_page(p), self.view.setFocus()))
        h.zoom_entry.zoomRequested.connect(lambda z: (self.view.set_zoom(z), self.view.setFocus()))
        h.zoom_entry.fitRequested.connect(lambda m: self.view.set_fit(FitMode(m)))
        h.search_button.toggled.connect(self.set_search_visible)
        if h.close_button is not None:
            h.min_button.clicked.connect(self.showMinimized)
            h.max_button.clicked.connect(lambda: self.showNormal() if self.isMaximized() else self.showMaximized())
            h.close_button.clicked.connect(self.close)

        self.view.currentPageChanged.connect(self._on_page_changed)
        self.view.zoomChanged.connect(self._on_zoom_changed)
        self.view.selectionChanged.connect(self.act_copy.setEnabled)

        self.sidebar.pageRequested.connect(lambda p, pt: self.view.go_to_page(p, pt))
        self.sidebar.bookmarks.addRequested.connect(self.add_bookmark)
        self.sidebar.bookmarks.removeRequested.connect(self._remove_bookmark)
        self.sidebar.bookmarks.renamed.connect(self._rename_bookmark)

        self.search_bar.textChanged.connect(lambda _t: self._search_delay.start())
        self.search_bar.nextRequested.connect(self._find_next)
        self.search_bar.previousRequested.connect(self._find_previous)
        self.search_bar.closeRequested.connect(lambda: self.header.search_button.setChecked(False))
        self.search.resultsChanged.connect(self._on_search_results)
        self.search.activeChanged.connect(self.view.set_active_find)

        self.recent.openRequested.connect(self.open_path)
        self.recent.removeRequested.connect(self._remove_recent)

    # ------------------------------------------------------------ abrir / fechar
    def open_dialog(self) -> None:
        start = self.settings.value("last_dir", os.path.expanduser("~"))
        if self.doc is not None:
            start = os.path.dirname(self.doc.path)
        paths, _ = QFileDialog.getOpenFileNames(self, "Abrir documento", start, file_filter())
        if paths:
            self.settings.set_value("last_dir", os.path.dirname(paths[0]))
        for path in paths:
            self.ctx.open(path, self)

    def open_path(self, path: str) -> None:
        self.ctx.open(path, self)

    def load(self, path: str) -> bool:
        doc, password = self._open_document(path)
        if doc is None:
            return False
        if self.doc is not None:
            self._save_state()
            self._unwatch()
            self.doc.close()
        self.doc, self._password = doc, password
        self._show_document()
        return True

    def _open_document(self, path: str) -> tuple[Document | None, str | None]:
        name = os.path.basename(path)
        password = None
        prompt = f"O documento “{name}” está protegido por senha.\nDigite a senha para abri-lo:"
        for _attempt in range(5):
            try:
                return Document(path, password), password
            except PasswordRequired:
                text, ok = QInputDialog.getText(self, "Senha necessária", prompt, QLineEdit.EchoMode.Password)
                if not ok:
                    return None, None
                password = text
                prompt = f"Senha incorreta para “{name}”.\nTente novamente:"
            except DocumentError as exc:
                if not os.path.exists(path):
                    self._remove_recent(path)
                    detail = "O arquivo não existe mais."
                else:
                    detail = str(exc)
                QMessageBox.critical(self, "Não foi possível abrir o documento",
                                     f"Não foi possível abrir “{name}”.\n\n{detail}")
                return None, None
        return None, None

    def _show_document(self) -> None:
        doc = self.doc
        state = self.settings.document_state(doc.path)
        self.stack.setCurrentIndex(1)
        self.header.set_document_mode(True)
        has_title = doc.title != doc.filename
        self.header.set_title(doc.title, doc.filename if has_title else "")
        self.setWindowTitle(f"{doc.title} — {APP_NAME}")

        self.view.set_document(doc, state)
        self.sidebar.set_document(doc, self.view.rotation, self.view.inverted)
        self.sidebar.bookmarks.set_bookmarks(self.settings.bookmarks(doc.path))
        self.sidebar.set_page(int(state.get("sidebar_page", Sidebar.THUMBNAILS)))
        self.sidebar.set_current_page(self.view.current_page())
        self.set_sidebar_visible(bool(state.get("sidebar", self.settings.value("sidebar_visible", True, bool))))
        sizes = self.settings.value("sidebar_width", 180, int)
        self.splitter.setSizes([sizes, max(200, self.width() - sizes)])

        self.act_continuous.setChecked(self.view.continuous)
        self.act_dual.setChecked(self.view.dual)
        self.act_inverted.setChecked(self.view.inverted)
        self.act_copy.setEnabled(False)
        self._update_actions()
        self._on_page_changed(self.view.current_page())
        self._on_zoom_changed()

        self.settings.add_recent(doc.path)
        self.ctx.recent_changed()
        self._watch(doc.path)
        if self.search_bar.isVisible() and self.search_bar.entry.text():
            self._start_search()
        QTimer.singleShot(800, lambda d=doc: self._cache_thumbnail(d))
        self.view.setFocus()

    def _cache_thumbnail(self, doc: Document) -> None:
        if doc is self.doc:
            try:
                store_thumbnail(doc)
            except Exception:
                pass

    def _show_recent(self) -> None:
        self.stack.setCurrentIndex(0)
        self.header.set_document_mode(False)
        self.header.set_title("Documentos recentes")
        self.search_bar.hide()
        self.refresh_recent()
        self._update_actions()

    def refresh_recent(self) -> None:
        if self.doc is None:
            self.recent.set_files(self.settings.recent_files())

    def _remove_recent(self, path: str) -> None:
        self.settings.remove_recent(path)
        self.ctx.recent_changed()

    def _fill_recent_menu(self) -> None:
        self.recent_menu.clear()
        files = [p for p in self.settings.recent_files() if os.path.exists(p)][:12]
        if not files:
            self.recent_menu.addAction("Nenhum documento recente").setEnabled(False)
            return
        for i, path in enumerate(files, 1):
            label = os.path.basename(path).replace("&", "&&")
            action = self.recent_menu.addAction(f"&{i % 10}  {label}" if i <= 10 else label)
            action.setToolTip(path)
            action.triggered.connect(lambda _c=False, p=path: self.open_path(p))

    def _update_actions(self) -> None:
        has_doc = self.doc is not None
        for action in self.actions():
            if action.property("needs_doc"):
                action.setEnabled(has_doc)
        self.act_copy.setEnabled(has_doc and self.view.has_selection())

    # ------------------------------------------------------------ estado
    def _save_state(self) -> None:
        if self.doc is None:
            return
        state = self.view.state()
        state["inverted"] = self.view.inverted
        state["sidebar"] = self.sidebar.isVisibleTo(self)
        state["sidebar_page"] = self.sidebar.current()
        self.settings.save_document_state(self.doc.path, state)

    def restore_window(self, offset: int = 0) -> None:
        geometry = self.settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
            if offset:
                self.move(self.pos().x() + offset, self.pos().y() + offset)
        else:
            screen = self.screen().availableGeometry()
            self.resize(min(1180, screen.width() - 80), min(800, screen.height() - 80))
            self.move(screen.center().x() - self.width() // 2 + offset, screen.center().y() - self.height() // 2 + offset)
        if self.settings.value("window/maximized", False, bool) and not offset:
            self.showMaximized()
        else:
            self.show()

    def closeEvent(self, event) -> None:
        self._save_state()
        if not self.isFullScreen():
            self.settings.set_value("window/maximized", self.isMaximized())
            if not self.isMaximized():
                self.settings.set_value("window/geometry", self.saveGeometry())
        if self.doc is not None and self.sidebar.isVisibleTo(self):
            self.settings.set_value("sidebar_width", self.splitter.sizes()[0])
        if self._presentation is not None:
            self._presentation.close()
        if self.doc is not None:
            self._unwatch()
            self.view.set_document(None)
            self.sidebar.set_document(None)
            self.doc.close()
            self.doc = None
        self.ctx.window_closed(self)
        super().closeEvent(event)

    # ------------------------------------------------------------ recarregar
    def _watch(self, path: str) -> None:
        if path not in self._watcher.files():
            self._watcher.addPath(path)

    def _unwatch(self) -> None:
        files = self._watcher.files()
        if files:
            self._watcher.removePaths(files)

    def _auto_reload(self) -> None:
        if self.doc is None:
            return
        if not os.path.exists(self.doc.path):  # editores costumam apagar e recriar o arquivo
            if self._reload_attempts < 10:
                self._reload_attempts += 1
                self._reload_timer.start()
            return
        self.reload(quiet=True)

    def reload(self, quiet: bool = False) -> None:
        if self.doc is None:
            return
        path = self.doc.path
        try:
            new = Document(path, self._password)
        except Exception as exc:
            if quiet and self._reload_attempts < 10:  # arquivo ainda sendo gravado
                self._reload_attempts += 1
                self._reload_timer.start()
            elif not quiet:
                QMessageBox.warning(self, "Recarregar", f"Não foi possível recarregar o documento.\n\n{exc}")
            return
        self._reload_attempts = 0
        old, self.doc = self.doc, new
        self.view.reload_document(new)
        self.sidebar.set_document(new, self.view.rotation, self.view.inverted)
        self.sidebar.set_current_page(self.view.current_page())
        self.header.set_title(new.title, new.filename if new.title != new.filename else "")
        old.close()
        self._watch(path)
        if self.search_bar.isVisible() and self.search_bar.entry.text():
            self._start_search()

    # ------------------------------------------------------------ comandos
    def save_copy(self) -> None:
        if self.doc is None:
            return
        ext = os.path.splitext(self.doc.path)[1]
        target, _ = QFileDialog.getSaveFileName(
            self, "Salvar uma cópia", os.path.join(self.settings.value("last_dir", os.path.expanduser("~")),
                                                   self.doc.filename), f"Documento (*{ext});;Todos os arquivos (*)")
        if not target:
            return
        if os.path.normcase(os.path.abspath(target)) == os.path.normcase(self.doc.path):
            return
        try:
            shutil.copy2(self.doc.path, target)
        except OSError as exc:
            QMessageBox.critical(self, "Salvar uma cópia", f"Não foi possível salvar a cópia.\n\n{exc}")

    def print_doc(self) -> None:
        if self.doc is not None:
            print_document(self, self.doc, self.view.current_page())

    def show_properties(self) -> None:
        if self.doc is not None:
            PropertiesDialog(self.doc, self).exec()

    def set_sidebar_visible(self, visible: bool) -> None:
        self.sidebar.setVisible(visible)
        for w in (self.header.sidebar_button, self.act_sidebar):
            if w.isChecked() != visible:
                w.blockSignals(True)
                w.setChecked(visible)
                w.blockSignals(False)
        if self.doc is not None:
            self.settings.set_value("sidebar_visible", visible)

    def _toggle_sidebar_action(self, checked: bool) -> None:
        self.set_sidebar_visible(checked)

    def _rotate(self, delta: int) -> None:
        self.view.rotate(delta)
        self.sidebar.thumbnails.set_options(self.view.rotation, self.view.inverted)

    def _set_inverted(self, inverted: bool) -> None:
        self.view.set_inverted(inverted)
        self.sidebar.thumbnails.set_options(self.view.rotation, inverted)

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showMaximized() if self._was_maximized else self.showNormal()
            QTimer.singleShot(0, self._frameless_state_changed)
        else:
            self._was_maximized = self.isMaximized()
            self.showFullScreen()

    def start_presentation(self) -> None:
        if self.doc is None:
            return
        w = PresentationWindow(self.doc, self.view.current_page(), self.view.rotation, self.view.inverted)
        w.finished.connect(self._presentation_finished)
        w.setGeometry(self.screen().geometry())
        w.showFullScreen()
        w.activateWindow()
        w.setFocus()
        self._presentation = w

    def _presentation_finished(self, page: int) -> None:
        self._presentation = None
        self.view.go_to_page(page)
        self.activateWindow()

    # ---- marcadores
    def add_bookmark(self) -> None:
        if self.doc is None:
            return
        page = self.view.current_page()
        items = self.settings.bookmarks(self.doc.path)
        if not any(b["page"] == page for b in items):
            items.append({"page": page, "title": f"Página {page + 1}"})
            self.settings.set_bookmarks(self.doc.path, items)
        self.sidebar.bookmarks.set_bookmarks(items)
        self.set_sidebar_visible(True)
        self.sidebar.set_page(Sidebar.BOOKMARKS)

    def _remove_bookmark(self, page: int) -> None:
        items = [b for b in self.settings.bookmarks(self.doc.path) if b["page"] != page]
        self.settings.set_bookmarks(self.doc.path, items)
        self.sidebar.bookmarks.set_bookmarks(items)

    def _rename_bookmark(self, page: int, title: str) -> None:
        items = self.settings.bookmarks(self.doc.path)
        for b in items:
            if b["page"] == page:
                b["title"] = title or f"Página {page + 1}"
        self.settings.set_bookmarks(self.doc.path, items)

    # ---- busca
    def set_search_visible(self, visible: bool) -> None:
        if self.doc is None:
            visible = False
        self.search_bar.setVisible(visible)
        if visible:
            self._focus_search()
            if self.search_bar.entry.text():
                self._start_search()
        else:
            self._search_delay.stop()
            self.search.stop()
            self.view.set_find_results({})
            self.view.setFocus()

    def _focus_search(self) -> None:
        self.search_bar.entry.setFocus()
        self.search_bar.entry.selectAll()

    def _start_search(self) -> None:
        self._search_delay.stop()
        self.search.start(self.doc, self.search_bar.entry.text(), self.view.current_page())

    def _find_next(self) -> None:
        if self._search_delay.isActive() or self.search.text != self.search_bar.entry.text().strip():
            self._start_search()
        else:
            self.search.next()

    def _find_previous(self) -> None:
        if self._search_delay.isActive():
            self._start_search()
        else:
            self.search.previous()

    def _on_search_results(self) -> None:
        self.view.set_find_results(self.search.results)
        self.search_bar.set_status(self.search.status_text(), bool(self.search.matches))

    # ---- sincronização
    def _on_page_changed(self, page: int) -> None:
        if self.doc is not None:
            self.header.page_entry.set_page(page, self.doc.page_count)
            self.sidebar.set_current_page(page)

    def _on_zoom_changed(self) -> None:
        self.header.zoom_entry.set_zoom(self.view.zoom(), self.view.fit_mode().value)

    # ------------------------------------------------------------ eventos
    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.toggle_fullscreen()
                self.act_fullscreen.setChecked(False)
                return
            if self.search_bar.isVisible():
                self.header.search_button.setChecked(False)
                return
        super().keyPressEvent(event)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            self.header.set_maximized(self.isMaximized())
            self.act_fullscreen.setChecked(self.isFullScreen())
        elif event.type() == event.Type.ActivationChange:
            self.header.set_backdrop(not self.isActiveWindow())

    def dragEnterEvent(self, event) -> None:
        if any(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        for path in paths:
            if os.path.isfile(path) and (is_supported(path) or len(paths) == 1):
                self.ctx.open(path, self)
        event.acceptProposedAction()

    def sizeHint(self) -> QSize:
        return QSize(1180, 800)
