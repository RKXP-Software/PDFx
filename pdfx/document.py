"""Camada fina sobre o PyMuPDF (MuPDF): abre documentos, renderiza páginas e extrai texto."""

from __future__ import annotations

import os
from datetime import datetime

import pymupdf
from PySide6.QtGui import QImage

try:
    pymupdf.TOOLS.mupdf_display_errors(False)
    pymupdf.TOOLS.mupdf_display_warnings(False)
except Exception:  # versões antigas não têm essas funções
    pass

# Formatos suportados pelo MuPDF que fazem sentido em um leitor de documentos.
DOCUMENT_FORMATS = {
    "pdf": "PDF",
    "xps": "XPS",
    "oxps": "OpenXPS",
    "epub": "EPUB",
    "mobi": "Mobipocket",
    "fb2": "FictionBook",
    "cbz": "Quadrinhos (CBZ)",
    "svg": "SVG",
    "txt": "Texto",
}
IMAGE_FORMATS = ("png", "jpg", "jpeg", "bmp", "gif", "tif", "tiff", "jxr", "jpx", "jp2", "pnm", "pgm", "pbm", "ppm", "psd")


def file_filter() -> str:
    docs = " ".join(f"*.{e}" for e in DOCUMENT_FORMATS)
    imgs = " ".join(f"*.{e}" for e in IMAGE_FORMATS)
    return ";;".join([
        f"Todos os documentos ({docs} {imgs})",
        "Documentos PDF (*.pdf)",
        "Documentos XPS (*.xps *.oxps)",
        "Livros eletrônicos (*.epub *.mobi *.fb2)",
        "Quadrinhos (*.cbz)",
        f"Imagens ({imgs})",
        "Todos os arquivos (*)",
    ])


def is_supported(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    return ext in DOCUMENT_FORMATS or ext in IMAGE_FORMATS


class PasswordRequired(Exception):
    """O documento está protegido e a senha não foi informada (ou está errada)."""


class DocumentError(Exception):
    """O arquivo não pôde ser aberto."""


def parse_pdf_date(value: str) -> str:
    """Converte 'D:20230102153000-03'00'' em '02/01/2023 15:30'."""
    if not value:
        return ""
    text = value[2:] if value.startswith("D:") else value
    digits = "".join(ch for ch in text[:14] if ch.isdigit())
    for fmt, size in (("%Y%m%d%H%M%S", 14), ("%Y%m%d%H%M", 12), ("%Y%m%d", 8), ("%Y", 4)):
        if len(digits) >= size:
            try:
                dt = datetime.strptime(digits[:size], fmt)
            except ValueError:
                continue
            return dt.strftime("%d/%m/%Y %H:%M") if size > 8 else dt.strftime("%d/%m/%Y")
    return value


class Document:
    def __init__(self, path: str, password: str | None = None):
        self.path = os.path.abspath(path)
        try:
            doc = pymupdf.open(self.path)
        except Exception as exc:  # o MuPDF lança vários tipos de exceção
            raise DocumentError(str(exc)) from exc
        if doc.needs_pass:
            if not password or not doc.authenticate(password):
                doc.close()
                raise PasswordRequired()
        if doc.page_count == 0:
            doc.close()
            raise DocumentError("O documento não possui páginas.")
        self._doc = doc
        self._sizes: list[tuple[float, float]] = []
        for page in doc:
            r = page.rect
            self._sizes.append((max(r.width, 1.0), max(r.height, 1.0)))
        self._words: dict[int, list] = {}
        self._links: dict[int, list] = {}
        self._toc: list | None = None

    def close(self) -> None:
        try:
            self._doc.close()
        except Exception:
            pass

    # ---- informações --------------------------------------------------------
    @property
    def page_count(self) -> int:
        return len(self._sizes)

    @property
    def is_pdf(self) -> bool:
        return bool(self._doc.is_pdf)

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)

    @property
    def metadata(self) -> dict:
        return dict(self._doc.metadata or {})

    @property
    def title(self) -> str:
        title = (self.metadata.get("title") or "").strip()
        return title or self.filename

    @property
    def author(self) -> str:
        return (self.metadata.get("author") or "").strip()

    @property
    def format_name(self) -> str:
        fmt = (self.metadata.get("format") or "").strip()
        if fmt:
            return fmt
        ext = os.path.splitext(self.path)[1].lower().lstrip(".")
        return DOCUMENT_FORMATS.get(ext, ext.upper())

    def page_size(self, index: int, rotation: int = 0) -> tuple[float, float]:
        """Tamanho da página em pontos (1/72 pol.), já considerando a rotação."""
        w, h = self._sizes[index]
        return (h, w) if rotation % 180 else (w, h)

    def transform(self, index: int, scale: float, rotation: int = 0) -> pymupdf.Matrix:
        """Matriz que leva coordenadas da página (pontos) para pixels da imagem renderizada."""
        w, h = self._sizes[index]
        m = pymupdf.Matrix(scale, scale).prerotate(rotation)
        r = pymupdf.Rect(0, 0, w, h) * m
        return m * pymupdf.Matrix(1, 0, 0, 1, -r.x0, -r.y0)

    # ---- renderização -------------------------------------------------------
    def render(self, index: int, scale: float, rotation: int = 0, inverted: bool = False,
               clip: tuple[int, int, int, int] | None = None) -> QImage:
        """Renderiza a página (ou um recorte dela, em pixels) como QImage RGB."""
        page = self._doc.load_page(index)
        matrix = pymupdf.Matrix(scale, scale).prerotate(rotation)
        kwargs = {}
        if clip is not None:
            inv = ~self.transform(index, scale, rotation)
            kwargs["clip"] = pymupdf.Rect(*clip) * inv
        pix = page.get_pixmap(matrix=matrix, alpha=False, **kwargs)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
        if inverted:
            img.invertPixels()
        return img

    # ---- texto, links e sumário --------------------------------------------
    def words(self, index: int) -> list:
        """Palavras da página em ordem de leitura: (x0, y0, x1, y1, texto, bloco, linha, n)."""
        words = self._words.get(index)
        if words is None:
            try:
                words = self._doc.load_page(index).get_text("words")
            except Exception:
                words = []
            self._words[index] = words
        return words

    def links(self, index: int) -> list[dict]:
        links = self._links.get(index)
        if links is None:
            try:
                links = self._doc.load_page(index).get_links()
            except Exception:
                links = []
            self._links[index] = links
        return links

    def search(self, index: int, text: str) -> list[pymupdf.Rect]:
        try:
            return self._doc.load_page(index).search_for(text)
        except Exception:
            return []

    def toc(self) -> list:
        """Sumário: lista de (nível, título, página base 0, ponto de destino ou None)."""
        if self._toc is None:
            entries = []
            try:
                raw = self._doc.get_toc(simple=False)
            except Exception:
                raw = []
            for item in raw:
                level, title, page = item[0], item[1], item[2]
                dest = item[3] if len(item) > 3 and isinstance(item[3], dict) else {}
                point = dest.get("to") if dest.get("kind") == pymupdf.LINK_GOTO else None
                entries.append((level, title, page - 1, point))
            self._toc = entries
        return self._toc

    def text_between(self, index: int, start: int, end: int) -> str:
        words = self.words(index)[start:end + 1]
        lines: list[str] = []
        current_key = None
        for w in words:
            key = (w[5], w[6])
            if key != current_key:
                lines.append(w[4])
                current_key = key
            else:
                lines[-1] += " " + w[4]
        return "\n".join(lines)
