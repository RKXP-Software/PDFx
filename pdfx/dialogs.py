"""Diálogos: propriedades do documento, atalhos de teclado e "Sobre"."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from . import APP_NAME, __version__, theme
from .document import Document, parse_pdf_date
from .resources import resource_path


def _human_size(n: int) -> str:
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024
    return str(n)


def _paper_name(w_mm: float, h_mm: float) -> str:
    papers = {"A3": (297, 420), "A4": (210, 297), "A5": (148, 210), "Carta": (216, 279), "Ofício": (216, 356)}
    a, b = sorted((w_mm, h_mm))
    for name, (pw, ph) in papers.items():
        if abs(a - pw) < 3 and abs(b - ph) < 3:
            orient = "retrato" if w_mm <= h_mm else "paisagem"
            return f"{name}, {orient}"
    return ""


class PropertiesDialog(QDialog):
    def __init__(self, doc: Document, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Propriedades")
        self.setMinimumWidth(460)
        meta = doc.metadata
        w, h = doc.page_size(0)
        w_mm, h_mm = w * 25.4 / 72, h * 25.4 / 72
        paper = _paper_name(w_mm, h_mm)
        size = f"{w_mm:.0f} × {h_mm:.0f} mm" + (f" ({paper})" if paper else "")
        try:
            file_size = _human_size(os.path.getsize(doc.path))
        except OSError:
            file_size = ""
        rows = [
            ("Título:", meta.get("title", "")),
            ("Localização:", doc.path),
            ("Assunto:", meta.get("subject", "")),
            ("Autor:", meta.get("author", "")),
            ("Palavras-chave:", meta.get("keywords", "")),
            ("Produtor:", meta.get("producer", "")),
            ("Criador:", meta.get("creator", "")),
            ("Criado em:", parse_pdf_date(meta.get("creationDate", ""))),
            ("Modificado em:", parse_pdf_date(meta.get("modDate", ""))),
            ("Número de páginas:", str(doc.page_count)),
            ("Formato:", doc.format_name),
            ("Segurança:", "Criptografado" if meta.get("encryption") else "Nenhuma"),
            ("Tamanho do papel:", size),
            ("Tamanho:", file_size),
        ]
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        for label, value in rows:
            key = QLabel(label)
            key.setStyleSheet("font-weight: bold;")
            val = QLabel(value or "—")
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            if not value:
                val.setStyleSheet(f"color: {theme.DIM_FG};")
            form.addRow(key, val)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 12)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Fechar")
        buttons.rejected.connect(self.reject)
        layout.addSpacing(8)
        layout.addWidget(buttons)


SHORTCUTS = [
    ("Documentos", [
        ("Ctrl+O", "Abrir um documento"),
        ("Ctrl+W", "Fechar a janela"),
        ("Ctrl+S", "Salvar uma cópia"),
        ("Ctrl+P", "Imprimir"),
        ("Ctrl+R", "Recarregar o documento"),
        ("Alt+Enter", "Propriedades"),
    ]),
    ("Navegação", [
        ("Ctrl+L", "Ir para a página…"),
        ("Page Up / Page Down", "Rolar uma tela"),
        ("← / →", "Página anterior / seguinte (sem rolagem horizontal)"),
        ("Ctrl+Page Up / Down", "Página anterior / seguinte"),
        ("Home / End", "Primeira / última página"),
        ("Ctrl+D", "Adicionar marcador"),
        ("Botão do meio", "Arrastar o documento"),
    ]),
    ("Busca e seleção", [
        ("Ctrl+F", "Buscar"),
        ("Enter / F3", "Próximo resultado"),
        ("Shift+Enter / Shift+F3", "Resultado anterior"),
        ("Ctrl+C", "Copiar o texto selecionado"),
        ("Ctrl+A", "Selecionar o texto da página"),
    ]),
    ("Visualização", [
        ("Ctrl + / Ctrl −", "Aumentar / diminuir o zoom"),
        ("Ctrl+0", "Tamanho original (100%)"),
        ("Ctrl+roda do mouse", "Zoom"),
        ("Ctrl+← / Ctrl+→", "Girar à esquerda / direita"),
        ("Ctrl+I", "Cores invertidas (modo noturno)"),
        ("F9", "Mostrar/ocultar a barra lateral"),
        ("F11", "Tela cheia"),
        ("F5", "Apresentação"),
    ]),
]


class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Atalhos de teclado")
        self.resize(560, 600)
        content = QWidget()
        content.setStyleSheet(f"background: {theme.BG};")
        grid = QGridLayout(content)
        grid.setContentsMargins(24, 18, 24, 18)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        row = 0
        for section, items in SHORTCUTS:
            title = QLabel(section)
            title.setStyleSheet("font-weight: bold; padding-top: 10px;")
            grid.addWidget(title, row, 0, 1, 2)
            row += 1
            for keys, desc in items:
                k = QLabel(keys)
                k.setStyleSheet(f"background: {theme.BASE}; border: 1px solid {theme.BORDER}; "
                                "border-radius: 4px; padding: 2px 6px;")
                k.setAlignment(Qt.AlignmentFlag.AlignCenter)
                grid.addWidget(k, row, 0, Qt.AlignmentFlag.AlignRight)
                grid.addWidget(QLabel(desc), row, 1)
                row += 1
        grid.setRowStretch(row, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Sobre o {APP_NAME}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 28, 36, 20)
        layout.setSpacing(10)
        logo = QLabel()
        pm = QPixmap(resource_path("pdfx.png"))
        if not pm.isNull():
            logo.setPixmap(pm.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name = QLabel(APP_NAME)
        name.setStyleSheet("font-size: 18pt; font-weight: bold;")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version = QLabel(f"Versão {__version__}")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet(f"color: {theme.DIM_FG};")
        desc = QLabel("Leitor de documentos para Windows inspirado no Evince, do projeto GNOME.\n"
                      "PDF, XPS, EPUB, MOBI, FB2, CBZ e imagens.")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        credits = QLabel("Renderização: MuPDF / PyMuPDF  •  Interface: Qt / PySide6")
        credits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credits.setStyleSheet(f"color: {theme.DIM_FG}; font-size: 8pt;")
        for w in (logo, name, version, desc, credits):
            layout.addWidget(w)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Fechar")
        buttons.rejected.connect(self.reject)
        layout.addSpacing(6)
        layout.addWidget(buttons, 0, Qt.AlignmentFlag.AlignCenter)
