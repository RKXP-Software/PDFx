"""Tema visual no estilo Adwaita (GNOME), com as cores medidas nos prints do Evince."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

ACCENT = "#3584e4"
FG = "#2e3436"
DIM_FG = "#929595"
BG = "#f6f5f4"
BASE = "#ffffff"
BORDER = "#cdc7c2"
BORDER_DARK = "#bfb8b1"
HEADER_TOP = "#e0ddda"
HEADER_BOTTOM = "#dad6d2"
BUTTON_TOP = "#f6f5f4"
BUTTON_BOTTOM = "#edebe9"
BUTTON_CHECKED = "#d6d1cd"
ENTRY_BG = "#faf9f8"

# Cores usadas na área do documento (shell/evince.css do Evince).
VIEW_BG = QColor(BG)
PAGE_SHADOW = QColor(60, 64, 67)
FIND_RESULT = QColor(53, 132, 228, 77)  # alpha(@accent_bg_color, 0.3)
FIND_ACTIVE = QColor(53, 132, 228, 153)  # alpha(@accent_bg_color, 0.6)
SELECTION = QColor(53, 132, 228, 90)

STYLESHEET = f"""
QWidget {{
    color: {FG};
}}
QMainWindow, #Central {{
    background: {BG};
}}

/* ---------- Barra de título (headerbar) ---------- */
#HeaderBar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {HEADER_TOP}, stop:1 {HEADER_BOTTOM});
    border-top: 1px solid #f9f8f8;
    border-bottom: 1px solid {BORDER_DARK};
}}
#HeaderBar[backdrop="true"] {{
    background: {BG};
    border-top: 1px solid {BG};
    border-bottom: 1px solid {BORDER};
}}
#Title {{
    font-weight: bold;
}}
#Subtitle {{
    color: {DIM_FG};
    font-size: 8pt;
}}
#HeaderBar[backdrop="true"] #Title {{
    color: #8b8e8f;
}}

QToolButton[hb="true"], QPushButton[hb="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {BUTTON_TOP}, stop:1 {BUTTON_BOTTOM});
    border: 1px solid {BORDER};
    border-bottom-color: {BORDER_DARK};
    border-radius: 5px;
    padding: 4px 6px;
    min-height: 24px;
    min-width: 22px;
}}
QPushButton[hb="true"] {{
    padding: 4px 12px;
}}
QToolButton[hb="true"]:hover, QPushButton[hb="true"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f8f8f7, stop:1 {BUTTON_TOP});
}}
QToolButton[hb="true"]:pressed, QToolButton[hb="true"]:checked,
QPushButton[hb="true"]:pressed, QToolButton[hb="true"]:open {{
    background: {BUTTON_CHECKED};
    border-color: {BORDER_DARK};
}}
QToolButton[hb="true"]:disabled {{
    background: #faf9f8;
    border-color: #d5d0cc;
}}
QToolButton::menu-indicator {{
    image: none;
    width: 0px;
}}
QToolButton[wc="true"] {{
    background: transparent;
    border: none;
    border-radius: 12px;
    min-width: 24px;
    min-height: 24px;
    max-width: 24px;
    max-height: 24px;
    padding: 0px;
}}
QToolButton[wc="true"]:hover {{
    background: rgba(0, 0, 0, 0.08);
}}
QToolButton[wc="true"]:pressed {{
    background: rgba(0, 0, 0, 0.16);
}}

/* ---------- Campos de texto ---------- */
QLineEdit {{
    background: {ENTRY_BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 4px 6px;
    min-height: 24px;
    selection-background-color: {ACCENT};
    selection-color: white;
}}
QLineEdit:focus {{
    border: 1px solid {ACCENT};
    background: {BASE};
}}
#LinkedEntry {{
    background: {ENTRY_BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
}}
#LinkedEntry QLineEdit {{
    border: none;
    background: transparent;
    padding: 0px 4px;
}}
#PageOf {{
    color: {DIM_FG};
    background: {BUTTON_BOTTOM};
    border-left: 1px solid {BORDER};
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
    padding: 0px 8px;
}}
#ZoomArrow {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {BUTTON_TOP}, stop:1 {BUTTON_BOTTOM});
    border: none;
    border-left: 1px solid {BORDER};
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
    padding: 0px 6px;
}}
#ZoomArrow:hover {{
    background: #f8f8f7;
}}
#ZoomArrow:pressed, #ZoomArrow:open {{
    background: {BUTTON_CHECKED};
}}

/* ---------- Barra de busca ---------- */
#SearchBar {{
    background: {BG};
    border-bottom: 1px solid {BORDER_DARK};
}}
#SearchCount {{
    color: {DIM_FG};
}}
QToolButton[linked="left"] {{
    border-top-right-radius: 0px;
    border-bottom-right-radius: 0px;
}}
QToolButton[linked="mid"] {{
    border-radius: 0px;
    border-left: none;
}}
QToolButton[linked="right"] {{
    border-top-left-radius: 0px;
    border-bottom-left-radius: 0px;
    border-left: none;
}}

/* ---------- Barra lateral ---------- */
#Sidebar {{
    background: {BASE};
}}
#SidebarSwitcher {{
    background: {BG};
    border-top: 1px solid {BORDER};
}}
QListView, QTreeView {{
    background: {BASE};
    border: none;
    outline: 0;
}}
QTreeView::item {{
    padding: 4px 2px;
}}
QTreeView::item:selected, QListView::item:selected {{
    background: {ACCENT};
    color: white;
}}
QSplitter::handle {{
    background: {BORDER};
}}

/* ---------- Menus (popovers) ---------- */
QMenu {{
    background: {BASE};
    border: 1px solid {BORDER_DARK};
    padding: 6px 0px;
}}
QMenu::item {{
    padding: 6px 28px 6px 14px;
    background: transparent;
}}
QMenu::item:selected {{
    background: #e8e6e3;
    color: {FG};
}}
QMenu::item:disabled {{
    color: {DIM_FG};
}}
QMenu::separator {{
    height: 1px;
    background: #e0ddda;
    margin: 6px 0px;
}}
QMenu::indicator {{
    width: 14px;
    height: 14px;
    margin-left: 6px;
}}

/* ---------- Barras de rolagem (estilo overlay do GTK) ---------- */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: rgba(46, 52, 54, 0.45);
    border-radius: 3px;
    min-height: 40px;
    margin: 2px 2px 2px 2px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(46, 52, 54, 0.45);
    border-radius: 3px;
    min-width: 40px;
    margin: 2px 2px 2px 2px;
}}
QScrollBar::handle:hover {{
    background: rgba(46, 52, 54, 0.7);
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}

QToolTip {{
    background: #2e3436;
    color: white;
    border: none;
    padding: 4px 6px;
}}

/* ---------- Diálogos ---------- */
QDialog {{
    background: {BG};
}}
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {BUTTON_TOP}, stop:1 {BUTTON_BOTTOM});
    border: 1px solid {BORDER};
    border-bottom-color: {BORDER_DARK};
    border-radius: 5px;
    padding: 5px 14px;
    min-height: 22px;
}}
QPushButton:hover {{
    background: #f8f8f7;
}}
QPushButton:pressed {{
    background: {BUTTON_CHECKED};
}}
QPushButton:default {{
    background: {ACCENT};
    color: white;
    border-color: #1b6acb;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background: {BASE};
    top: -1px;
}}
QTabBar::tab {{
    padding: 6px 16px;
    border: none;
    border-bottom: 3px solid transparent;
}}
QTabBar::tab:selected {{
    border-bottom: 3px solid {ACCENT};
}}
QProgressBar {{
    border: none;
    background: #e0ddda;
    border-radius: 3px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 3px;
}}
"""


def apply(app: QApplication) -> None:
    """Aplica o estilo Adwaita (claro) a toda a aplicação."""
    app.setStyle("Fusion")

    font = QFont("Segoe UI", 9)
    app.setFont(font)

    pal = QPalette()
    fg, bg, base = QColor(FG), QColor(BG), QColor(BASE)
    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        pal.setColor(group, QPalette.ColorRole.Window, bg)
        pal.setColor(group, QPalette.ColorRole.WindowText, fg)
        pal.setColor(group, QPalette.ColorRole.Base, base)
        pal.setColor(group, QPalette.ColorRole.AlternateBase, bg)
        pal.setColor(group, QPalette.ColorRole.Text, fg)
        pal.setColor(group, QPalette.ColorRole.Button, bg)
        pal.setColor(group, QPalette.ColorRole.ButtonText, fg)
        pal.setColor(group, QPalette.ColorRole.Highlight, QColor(ACCENT))
        pal.setColor(group, QPalette.ColorRole.HighlightedText, QColor("white"))
        pal.setColor(group, QPalette.ColorRole.ToolTipBase, fg)
        pal.setColor(group, QPalette.ColorRole.ToolTipText, QColor("white"))
        pal.setColor(group, QPalette.ColorRole.PlaceholderText, QColor(DIM_FG))
        pal.setColor(group, QPalette.ColorRole.Link, QColor("#1b6acb"))
    disabled = QPalette.ColorGroup.Disabled
    pal.setColor(disabled, QPalette.ColorRole.WindowText, QColor(DIM_FG))
    pal.setColor(disabled, QPalette.ColorRole.Text, QColor(DIM_FG))
    pal.setColor(disabled, QPalette.ColorRole.ButtonText, QColor(DIM_FG))
    pal.setColor(disabled, QPalette.ColorRole.Window, bg)
    pal.setColor(disabled, QPalette.ColorRole.Base, bg)
    app.setPalette(pal)

    app.setStyleSheet(STYLESHEET)
