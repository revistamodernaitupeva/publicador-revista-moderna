"""Baixa a foto de uma matéria para a pasta fotos/ (usado pelo workflow "Baixar foto").

Só aceita endereços https dos domínios listados em config.json ("dominios_foto"),
só aceita imagens (jpg, png, webp) e no máximo 15 MB.
Entrada pelas variáveis de ambiente FOTO_URL e FOTO_NOME.
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

LIMITE = 15 * 1024 * 1024
TIPOS = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

cfg = json.load(open("config.json", encoding="utf-8"))
dominios = [d.lower() for d in cfg.get("dominios_foto", [])]

url = os.environ.get("FOTO_URL", "").strip()
nome = os.environ.get("FOTO_NOME", "").strip()

if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", nome):
    sys.exit("Nome inválido: use só letras minúsculas, números e hífen.")

partes = urllib.parse.urlsplit(url)
host = (partes.hostname or "").lower()
if partes.scheme != "https":
    sys.exit("Só endereços https.")
if not any(host == d or host.endswith("." + d) for d in dominios):
    sys.exit(f"Domínio não autorizado: {host}. Autorizados: {', '.join(dominios)}")

# Espaços e acentos no caminho precisam ser codificados
caminho = urllib.parse.quote(urllib.parse.unquote(partes.path), safe="/%")
url = urllib.parse.urlunsplit((partes.scheme, partes.netloc, caminho, partes.query, ""))

req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (publicador Revista Moderna)"})
with urllib.request.urlopen(req, timeout=60) as r:
    final = (urllib.parse.urlsplit(r.geturl()).hostname or "").lower()
    if not any(final == d or final.endswith("." + d) for d in dominios):
        sys.exit(f"Redirecionou para domínio não autorizado: {final}")
    tipo = r.headers.get_content_type()
    if tipo not in TIPOS:
        sys.exit(f"Não é imagem aceita: {tipo}")
    dados = r.read(LIMITE + 1)
if len(dados) > LIMITE:
    sys.exit("Imagem maior que 15 MB.")

os.makedirs("fotos", exist_ok=True)
destino = os.path.join("fotos", nome + TIPOS[tipo])
with open(destino, "wb") as f:
    f.write(dados)
print(f"OK {destino} ({len(dados)} bytes)")
