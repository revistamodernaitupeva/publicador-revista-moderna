#!/usr/bin/env python3
"""Monta a arte da Revista Moderna (layout 1068x1337) e salva em JPEG.

Uso:
  python3 -I montar_arte.py FOTO SAIDA.jpg "Titulo da materia" [crop=x0,y0,x1,y1] [rosto=0.5] [tamanho=64] [alinhar=centro]

- FOTO: imagem de entrada (jpg/png).
- Use "|" no titulo para escolher onde quebrar as linhas.
- crop: recorte da foto em pixels (proporcao ideal ~1,25 largura/altura).
- rosto: posicao horizontal (0 a 1) do assunto, usada quando nao ha crop.
- A saida e cortada para 1068x1335 (proporcao 4:5 exata), exigida pelo Instagram.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(AQUI, "template.png")
FONTE = os.path.join(AQUI, "anton.ttf")

LARGURA, ALTURA = 1068, 1337
FOTO_H = 852                      # a foto ocupa y 0..852
MEDALHAO = (529.2, 846.8, 69.0)   # centro x, centro y, raio
MARGEM = 50
TITULO_Y0, TITULO_Y1 = 930, 1146  # area do titulo na faixa azul
TAMANHO_MAX = 64
MAX_LINHAS = 3


def preparar_foto(caminho, crop, rosto):
    foto = Image.open(caminho).convert("RGB")
    if crop:
        foto = foto.crop(crop)
    else:
        alvo = LARGURA / FOTO_H
        w, h = foto.size
        if w / h > alvo:                      # larga demais: corta nas laterais
            nw = int(h * alvo)
            cx = int(w * rosto)
            x0 = min(max(cx - nw // 2, 0), w - nw)
            foto = foto.crop((x0, 0, x0 + nw, h))
        else:                                 # alta demais: corta em cima/baixo
            nh = int(w / alvo)
            y0 = (h - nh) // 2
            foto = foto.crop((0, y0, w, y0 + nh))
    return foto.resize((LARGURA, FOTO_H), Image.LANCZOS)


def quebrar(texto, fonte, largura_max):
    """Quebra automatica por palavras."""
    palavras, linhas, atual = texto.split(), [], ""
    for p in palavras:
        teste = (atual + " " + p).strip()
        if fonte.getlength(teste) <= largura_max or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas


def ajustar_titulo(titulo, tamanho_max):
    largura_max = LARGURA - 2 * MARGEM
    altura_max = TITULO_Y1 - TITULO_Y0
    manual = [l.strip() for l in titulo.split("|")] if "|" in titulo else None
    for tam in range(tamanho_max, 27, -1):
        fonte = ImageFont.truetype(FONTE, tam)
        linhas = manual or quebrar(titulo, fonte, largura_max)
        entrelinha = int(tam * 1.12)
        cabe_largura = all(fonte.getlength(l) <= largura_max for l in linhas)
        if len(linhas) <= MAX_LINHAS and cabe_largura and entrelinha * len(linhas) <= altura_max:
            return fonte, linhas, entrelinha
    raise SystemExit("AVISO: o titulo nao cabe; encurte o texto.")


def main():
    args = [a for a in sys.argv[1:] if "=" not in a or not a.split("=")[0].isalpha()]
    opts = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a and a.split("=")[0].isalpha())
    if len(args) != 3:
        raise SystemExit(__doc__)
    foto_path, saida, titulo = args

    crop = tuple(int(v) for v in opts["crop"].split(",")) if "crop" in opts else None
    rosto = float(opts.get("rosto", 0.5))
    tamanho = int(opts.get("tamanho", TAMANHO_MAX))
    centro = opts.get("alinhar") == "centro"

    modelo = Image.open(TEMPLATE).convert("RGB")
    tela = modelo.copy()
    tela.paste(preparar_foto(foto_path, crop, rosto), (0, 0))

    # medalhao do logo por cima da foto, com borda suave (supersampling 4x)
    cx, cy, r = MEDALHAO
    ss = 4
    mascara = Image.new("L", (LARGURA * ss, ALTURA * ss), 0)
    ImageDraw.Draw(mascara).ellipse(
        [(cx - r) * ss, (cy - r) * ss, (cx + r) * ss, (cy + r) * ss], fill=255)
    mascara = mascara.resize((LARGURA, ALTURA), Image.LANCZOS)
    tela.paste(modelo, (0, 0), mascara)

    # titulo em Anton branca, sem forcar caixa alta
    fonte, linhas, entrelinha = ajustar_titulo(titulo, tamanho)
    bloco = entrelinha * len(linhas)
    y = TITULO_Y0 + (TITULO_Y1 - TITULO_Y0 - bloco) // 2
    desenho = ImageDraw.Draw(tela)
    for linha in linhas:
        x = (LARGURA - fonte.getlength(linha)) / 2 if centro else MARGEM
        desenho.text((x, y), linha, font=fonte, fill=(255, 255, 255))
        y += entrelinha

    tela = tela.crop((0, 0, LARGURA, 1335))  # 4:5 exato
    tela.save(saida, "JPEG", quality=95, optimize=True)
    print("ok", tela.size, saida)


if __name__ == "__main__":
    main()
