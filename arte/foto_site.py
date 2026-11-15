#!/usr/bin/env python3
"""Gera a imagem do SITE: so a foto (sem layout), 1200x800 JPEG.
Uso: python3 -I arte/foto_site.py FOTO SAIDA.jpg [crop=x0,y0,x1,y1] [rosto=0.5]
Sem crop, corta ao centro na proporcao 3:2. rosto = posicao vertical (0 topo, 1 base)."""
import sys
from PIL import Image

W, H = 1200, 800


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    foto, saida = sys.argv[1], sys.argv[2]
    opts = dict(a.split("=", 1) for a in sys.argv[3:] if "=" in a)
    im = Image.open(foto).convert("RGB")
    if "crop" in opts:
        x0, y0, x1, y1 = (int(float(v)) for v in opts["crop"].split(","))
        im = im.crop((x0, y0, x1, y1))
    w, h = im.size
    alvo = W / H
    if w / h > alvo:                      # larga demais: corta dos lados
        nw = int(h * alvo)
        x = (w - nw) // 2
        im = im.crop((x, 0, x + nw, h))
    else:                                 # alta demais: corta em cima/embaixo
        nh = int(w / alvo)
        pos = float(opts.get("rosto", 0.5))
        y = int((h - nh) * pos)
        im = im.crop((0, y, w, y + nh))
    im = im.resize((W, H), Image.LANCZOS)
    im.save(saida, "JPEG", quality=92)
    print("ok", im.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
