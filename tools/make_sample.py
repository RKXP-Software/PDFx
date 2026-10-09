"""Gera um PDF de exemplo (com sumário, links e várias páginas) para testar o PDFx.

Uso: python tools/make_sample.py [saida.pdf]
"""

import sys

import pymupdf

LOREM = ("O Evince é um visualizador de documentos para vários formatos. O objetivo do PDFx é "
         "trazer a mesma experiência simples e limpa para o Windows: abrir rápido, ler com "
         "conforto e encontrar o que se procura. ") * 6


def main(out: str) -> None:
    doc = pymupdf.open()
    toc = []
    for i in range(12):
        page = doc.new_page(width=595, height=842)  # A4
        title = f"Capítulo {i + 1}"
        page.insert_text((72, 90), title, fontsize=26, fontname="helv", color=(0.2, 0.2, 0.3))
        page.draw_rect(pymupdf.Rect(72, 110, 523, 114), color=None, fill=(0.21, 0.52, 0.89))
        rect = pymupdf.Rect(72, 140, 523, 600)
        page.insert_textbox(rect, LOREM, fontsize=12, fontname="helv", align=pymupdf.TEXT_ALIGN_JUSTIFY)
        page.draw_rect(pymupdf.Rect(72, 620, 523, 760), color=(0.8, 0.78, 0.76), fill=(0.96, 0.96, 0.95))
        page.insert_text((90, 700), f"Figura {i + 1} — página {i + 1} de 12", fontsize=14, fontname="helv")
        page.insert_text((72, 800), "Ir para o início", fontsize=11, fontname="helv", color=(0.1, 0.4, 0.8))
        page.insert_link({"kind": pymupdf.LINK_GOTO, "from": pymupdf.Rect(72, 788, 160, 804), "page": 0,
                          "to": pymupdf.Point(0, 0)})
        toc.append([1, title, i + 1])
        if i % 3 == 0:
            toc.append([2, f"Seção {i + 1}.1", i + 1])
    first = doc[0]
    first.insert_text((360, 800), "gnome.org", fontsize=11, fontname="helv", color=(0.1, 0.4, 0.8))
    first.insert_link({"kind": pymupdf.LINK_URI, "from": pymupdf.Rect(360, 788, 420, 804), "uri": "https://www.gnome.org"})
    doc.set_toc(toc)
    doc.set_metadata({"title": "Documento de Exemplo do PDFx", "author": "PDFx", "subject": "Teste"})
    doc.save(out)
    print("PDF gerado:", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "exemplo.pdf")
