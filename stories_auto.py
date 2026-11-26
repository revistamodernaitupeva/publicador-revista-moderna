#!/usr/bin/env python3
"""Cria na fila/ os stories automáticos (config.json > stories_auto).

Para cada conta e horário configurados, quando faltar até 60 minutos para o
horário e ainda não existir story daquele horário no dia, pega a matéria de
feed mais recente já publicada pela conta (que ainda não virou story nas
últimas 24 horas), monta a arte vertical e coloca o story na fila com o
horário marcado. O publicar.py publica na rodada seguinte, depois que a imagem
já foi enviada ao repositório.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ / "arte"))
from montar_story_altouruguai import montar  # noqa: E402

CFG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
BRT = timezone(timedelta(hours=-3))
JANELA = timedelta(minutes=60)
SIMULACAO = os.environ.get("SIMULACAO", "false").lower() == "true"


def carregar(pasta):
    for jf in sorted((RAIZ / pasta).glob("*.json")):
        try:
            yield jf, json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue


def main():
    agora = datetime.now(BRT)
    regras = CFG.get("stories_auto", {})
    todos = [p for pasta in ("fila", "publicados", "atrasados") for _, p in carregar(pasta)]
    for conta, horarios in regras.items():
        stories = [p for p in todos if p.get("conta") == conta and p.get("tipo") == "story"]
        for hhmm in horarios:
            h, m = map(int, hhmm.split(":"))
            alvo = agora.replace(hour=h, minute=m, second=0, microsecond=0)
            if not (alvo - JANELA <= agora <= alvo):
                continue
            iso = alvo.isoformat()
            if any(s.get("horario") == iso for s in stories):
                continue
            usados = {s.get("origem") for s in stories
                      if datetime.fromisoformat(s["horario"]) > alvo - timedelta(hours=24)}
            feeds = []
            for jf, p in carregar("publicados"):
                if p.get("conta") != conta or p.get("tipo") != "feed":
                    continue
                if jf.name in usados or not p.get("imagens"):
                    continue
                quando = datetime.fromisoformat(p["horario"])
                if quando > agora or quando < agora - timedelta(hours=24):
                    continue
                img = RAIZ / "publicados" / p["imagens"][0]
                if img.exists():
                    feeds.append((quando, jf, p, img))
            if not feeds:
                print(f"[stories {conta} {hhmm}] nenhuma matéria publicada disponível.")
                continue
            _, jf, p, img = max(feeds, key=lambda x: x[0])
            nome = f"{alvo:%Y-%m-%d-%H%M}-{conta}-story"
            post = {"tipo": "story", "conta": conta, "plataformas": ["instagram"],
                    "imagens": [nome + ".jpg"], "legenda": "", "horario": iso,
                    "origem": jf.name, "titulo": p.get("titulo", ""),
                    "status": "aprovado", "aprovado_em": agora.isoformat(),
                    "criado_por": "stories_auto"}
            print(f"[stories {conta} {hhmm}] criando story de: {jf.name}")
            if SIMULACAO:
                continue
            montar(img, RAIZ / "fila" / (nome + ".jpg"))
            (RAIZ / "fila" / (nome + ".json")).write_text(
                json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
            stories.append(post)
    return 0


if __name__ == "__main__":
    sys.exit(main())
