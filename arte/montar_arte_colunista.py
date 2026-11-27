#!/usr/bin/env python3
"""Arte de COLUNISTA da Revista Moderna (feed 1068x1335).

Uso:
  python3 -I montar_arte_colunista.py FOTO SAIDA.jpg "Nome do colunista" "Título da coluna" [rosto=0.30] [titulo_tamanho=56]

- FOTO: retrato do colunista (qualquer proporção). A foto ocupa o bloco branco de cima (1068x852).
- rosto: posição vertical do centro do rosto na foto original (0 = topo, 1 = base). Padrão 0.30.
- Faixa branca: "Por NOME | Colunista" (Anton preta, centralizada, ajusta o tamanho para caber).
- Bloco roxo: título em Anton branca, alinhado à esquerda (margem 50), até 3 linhas.
Template limpo: template_colunista.png (1068x1337) na mesma pasta; a saída é cortada para 1068x1335 (4:5).
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
W, H_FOTO = 1068, 852
CX, CY, R = 529, 847, 70          # medalhão do logo
FAIXA_Y0, FAIXA_Y1 = 923, 1019    # faixa branca do nome
TIT_X, TIT_Y, MAXW = 50, 1038, 968


def quebrar(draw, texto, fonte, largura):
    linhas, atual = [], ""
    for p in texto.split():
        teste = (atual + " " + p).strip()
        if draw.textlength(teste, font=fonte) <= largura:
            atual = teste
        else:
            linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas


def main():
    pos = [a for a in sys.argv[1:] if "=" not in a or a.startswith('"')]
    opts = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a and not a.startswith('"')
                and a.split("=", 1)[0] in ("rosto", "titulo_tamanho"))
    pos = [a for a in sys.argv[1:] if a.split("=", 1)[0] not in ("rosto", "titulo_tamanho")]
    if len(pos) < 4:
        sys.exit(__doc__)
    foto_p, saida, nome, titulo = pos[:4]
    rosto = float(opts.get("rosto", 0.30))
    tam = int(opts.get("titulo_tamanho", 56))
    assert "|" not in titulo, "não use | no título"

    tpl = Image.open(AQUI / "template_colunista.png").convert("RGB")
    arte = tpl.copy()

    # --- foto: cobre 1068x852 (recorte vertical centrado no rosto) ---
    foto = Image.open(foto_p).convert("RGB")
    esc = max(W / foto.width, H_FOTO / foto.height)
    foto = foto.resize((round(foto.width * esc), round(foto.height * esc)), Image.LANCZOS)
    cx = (foto.width - W) // 2
    cy = int(rosto * foto.height - 0.36 * H_FOTO)
    cy = max(0, min(cy, foto.height - H_FOTO))
    arte.paste(foto.crop((cx, cy, cx + W, cy + H_FOTO)), (0, 0))

    # --- medalhão do template por cima da foto (máscara suave, 4x) ---
    S = 4
    m = Image.new("L", (W * S, 140 * S), 0)
    ImageDraw.Draw(m).ellipse([(CX - R) * S, (CY - R - 777 + 0) * S, (CX + R) * S, (CY + R - 777) * S], fill=255)
    m = m.resize((W, 140), Image.LANCZOS)
    y0 = 777
    arte.paste(tpl.crop((0, y0, W, y0 + 140)), (0, y0), m)

    d = ImageDraw.Draw(arte)

    # --- nome do colunista ---
    linha_nome = f"Por {nome} | Colunista"
    for t in range(66, 30, -1):
        f = ImageFont.truetype(str(AQUI / "anton.ttf"), t)
        if d.textlength(linha_nome, font=f) <= 980:
            break
    d.text((W / 2, (FAIXA_Y0 + FAIXA_Y1) / 2 + 2), linha_nome, font=f, fill=(0, 0, 0), anchor="mm")

    # --- título ---
    for t in range(tam, 40, -2):
        f = ImageFont.truetype(str(AQUI / "anton.ttf"), t)
        linhas = quebrar(d, titulo, f, MAXW)
        if len(linhas) <= 3:
            break
    assert len(linhas) <= 3, "título longo demais (mais de 3 linhas)"
    ent = round(t * 1.34)
    y = TIT_Y
    for ln in linhas:
        d.text((TIT_X, y), ln, font=f, fill=(255, 255, 255), anchor="la")
        y += ent

    arte.crop((0, 0, W, 1335)).save(saida, quality=95)
    print("ok", saida, f"titulo {t}px {len(linhas)} linhas")


if __name__ == "__main__":
    main()
