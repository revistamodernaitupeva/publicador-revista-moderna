"""Monta o story (1080x1920) do Alto Uruguai a partir da arte do feed.

Uso: python3 -I arte/montar_story_altouruguai.py ARTE_FEED.jpg SAIDA.jpg
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
AZUL = (0, 43, 82)
AMARELO = (255, 205, 0)
BRANCO = (255, 255, 255)


def fonte(tam):
    return ImageFont.truetype(str(AQUI / "anton.ttf"), tam)


def centralizar(d, y, texto, f, cor):
    w = d.textlength(texto, font=f)
    d.text(((1080 - w) / 2, y), texto, font=f, fill=cor)


def montar(feed_jpg, saida):
    tela = Image.new("RGB", (1080, 1920), AZUL)
    d = ImageDraw.Draw(tela)
    centralizar(d, 240, "NOVA MATÉRIA NO FEED", fonte(74), AMARELO)
    arte = Image.open(feed_jpg).convert("RGB").resize((880, 1100), Image.LANCZOS)
    # moldura branca fina; textos fora das areas cobertas pela interface do Instagram
    d.rectangle((94, 364, 986, 1476), fill=BRANCO)
    tela.paste(arte, (100, 370))
    centralizar(d, 1515, "Leia a matéria completa no perfil", fonte(54), BRANCO)
    centralizar(d, 1600, "@revistamoderna.altouruguai", fonte(62), AMARELO)
    tela.save(saida, "JPEG", quality=92)


if __name__ == "__main__":
    montar(sys.argv[1], sys.argv[2])
