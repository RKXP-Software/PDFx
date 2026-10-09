"""Gera o ícone do aplicativo (pdfx.png e pdfx.ico) com Pillow.

Inspirado no ícone do Evince: uma folha de documento com um par de óculos azul.
Uso: python tools/make_icon.py
"""

import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "pdfx", "resources")
S = 1024  # desenha grande e reduz, para suavizar as bordas


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # sombra da folha
    d.rounded_rectangle((196, 92, 844, 932), radius=56, fill=(0, 0, 0, 40))
    # folha
    d.rounded_rectangle((180, 70, 830, 910), radius=52, fill=(246, 245, 244, 255), outline=(205, 199, 194, 255), width=10)
    # título e linhas de texto
    d.rounded_rectangle((260, 160, 520, 196), radius=12, fill=(119, 118, 123, 255))
    for i, y in enumerate(range(250, 640, 62)):
        right = 750 if i % 3 else 620
        d.rounded_rectangle((260, y, right, y + 30), radius=10, fill=(222, 221, 218, 255))
    # imagem em destaque (o quadro vermelho do ícone do Evince)
    d.rounded_rectangle((560, 330, 750, 500), radius=16, fill=(224, 27, 36, 255))
    d.arc((605, 360, 705, 470), start=200, end=520, fill=(255, 255, 255, 255), width=18)

    # óculos
    blue, dark = (53, 132, 228, 255), (26, 95, 180, 255)
    d.rounded_rectangle((150, 690, 470, 860), radius=34, outline=dark, width=44)
    d.rounded_rectangle((560, 690, 880, 860), radius=34, outline=dark, width=44)
    d.rounded_rectangle((150, 690, 470, 860), radius=34, outline=blue, width=30)
    d.rounded_rectangle((560, 690, 880, 860), radius=34, outline=blue, width=30)
    d.rounded_rectangle((455, 720, 575, 760), radius=14, fill=dark)
    # reflexo nas lentes
    for x0 in (180, 590):
        d.rounded_rectangle((x0, 720, x0 + 260, 830), radius=20, fill=(255, 255, 255, 70))
    return img


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    img = draw()
    img.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "pdfx.png"))
    img.save(os.path.join(OUT, "pdfx.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Ícones gerados em", OUT)


if __name__ == "__main__":
    main()
