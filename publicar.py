#!/usr/bin/env python3
"""Publicador automatico: le a fila/ e publica no Instagram e Facebook."""
import base64
import html
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CFG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
V = CFG.get("versao_api", "v26.0")
IG_PADRAO = CFG["instagram_id"]
PAGINA_PADRAO = CFG["pagina_id"]
CONTAS = CFG.get("contas", {})
ANTECEDENCIA = timedelta(minutes=CFG.get("antecedencia_minutos", 20))
ATRASO_MAX = timedelta(hours=CFG.get("atraso_maximo_horas", 3))
MAX_TENTATIVAS = 3
REPO = os.environ.get("GITHUB_REPOSITORY", "")
TOKEN = os.environ.get("META_TOKEN", "")
SIMULACAO = os.environ.get("SIMULACAO", "false").lower() == "true"
SITE_URL = CFG.get("site_url", "").rstrip("/")
WP_USUARIO = os.environ.get("WP_USUARIO", "")
WP_SENHA = os.environ.get("WP_SENHA", "")


class MetaError(Exception):
    pass


def api(metodo, caminho, token, **params):
    """Chama a Graph API. O token vai no cabecalho, nunca na URL."""
    params = {k: v for k, v in params.items() if v is not None}
    url = f"https://graph.facebook.com/{V}/{caminho}"
    dados = None
    if metodo == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        dados = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        url, data=dados, method=metodo,
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise MetaError(e.read().decode("utf-8", "replace"))
    except urllib.error.URLError as e:
        raise MetaError(f"falha de rede: {e}")


def url_imagem(nome):
    return (f"https://raw.githubusercontent.com/{REPO}/main/fila/"
            f"{urllib.parse.quote(nome)}")


def esperar_pronto(container_id, tentativas=24, token=None):
    for _ in range(tentativas):
        st = api("GET", container_id, token or TOKEN, fields="status_code").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise MetaError(f"container {container_id} com status {st}")
        time.sleep(5)
    raise MetaError(f"container {container_id} nao ficou pronto a tempo")


def token_da_conta(post):
    """Chave da Meta da conta do post (cada conta pode ter a sua)."""
    nome = post.get("conta")
    if not nome:
        return TOKEN
    var = CONTAS.get(nome, {}).get("token_env")
    t = os.environ.get(var, "") if var else ""
    if var and not t:
        raise MetaError(f"conta '{nome}': Secret {var} nao configurado")
    return t or TOKEN


def conta_do_post(post):
    """Retorna (instagram_id, pagina_id) da conta do post.

    Sem o campo 'conta', usa a conta padrao (Itupeva) do config.json.
    """
    nome = post.get("conta")
    if not nome:
        return IG_PADRAO, PAGINA_PADRAO
    c = CONTAS.get(nome)
    if not c or not c.get("instagram_id"):
        raise MetaError(f"conta '{nome}' sem instagram_id no config.json")
    return c["instagram_id"], c.get("pagina_id")


def enviar_binario(url, token, caminho, extras=None):
    """Envia o arquivo inteiro para o servidor de upload da Meta (rupload)."""
    dados = Path(caminho).read_bytes()
    h = {"Authorization": f"OAuth {token}", "offset": "0",
         "file_size": str(len(dados)), "Content-Type": "application/octet-stream"}
    h.update(extras or {})
    req = urllib.request.Request(url, data=dados, method="POST", headers=h)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise MetaError(f"upload HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}")
    except urllib.error.URLError as e:
        raise MetaError(f"upload: falha de rede: {e}")


def publicar_instagram_reel(post, IG, T):
    """Reels: container resumable, envio do .mp4 direto para a Meta e publicacao."""
    video = RAIZ / "fila" / post["video"]
    c = api("POST", f"{IG}/media", T, media_type="REELS", upload_type="resumable",
            caption=post["legenda"], share_to_feed="true",
            cover_url=url_imagem(post["capa"]) if post.get("capa") else None)
    cid = c["id"]
    uri = c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{V}/{cid}"
    enviar_binario(uri, T, video)
    esperar_pronto(cid, tentativas=120, token=T)   # video demora: ate 10 min
    media_id = api("POST", f"{IG}/media_publish", T, creation_id=cid)["id"]
    try:
        link = api("GET", media_id, T, fields="permalink").get("permalink")
    except MetaError:
        link = None
    return {"id": media_id, "link": link}


def publicar_facebook_reel(post, PAGINA, tp):
    """Reels da Pagina: start -> upload do .mp4 -> finish (publicado)."""
    video = RAIZ / "fila" / post["video"]
    ini = api("POST", f"{PAGINA}/video_reels", tp, upload_phase="start")
    vid = ini["video_id"]
    url = ini.get("upload_url") or f"https://rupload.facebook.com/video-upload/{V}/{vid}"
    enviar_binario(url, tp, video)
    fim = api("POST", f"{PAGINA}/video_reels", tp, upload_phase="finish",
              video_id=vid, video_state="PUBLISHED", description=post["legenda"])
    if not fim.get("success", True):
        raise MetaError(f"reels do Facebook nao finalizou: {fim}")
    return {"id": vid, "link": f"https://www.facebook.com/reel/{vid}"}


def publicar_instagram(post):
    IG, _ = conta_do_post(post)
    T = token_da_conta(post)
    if post["tipo"] == "reel":
        return publicar_instagram_reel(post, IG, T)
    imgs, legenda = post["imagens"], post["legenda"]
    if post["tipo"] == "story":
        c = api("POST", f"{IG}/media", T,
                image_url=url_imagem(imgs[0]), media_type="STORIES")["id"]
        esperar_pronto(c, token=T)
    elif len(imgs) == 1:
        c = api("POST", f"{IG}/media", T,
                image_url=url_imagem(imgs[0]), caption=legenda)["id"]
        esperar_pronto(c, token=T)
    else:
        filhos = []
        for n in imgs:
            f = api("POST", f"{IG}/media", T,
                    image_url=url_imagem(n), is_carousel_item="true")["id"]
            filhos.append(f)
        for f in filhos:
            esperar_pronto(f, token=T)
        c = api("POST", f"{IG}/media", T, media_type="CAROUSEL",
                children=",".join(filhos), caption=legenda)["id"]
        esperar_pronto(c, token=T)
    media_id = api("POST", f"{IG}/media_publish", T, creation_id=c)["id"]
    try:
        link = api("GET", media_id, T, fields="permalink").get("permalink")
    except MetaError:
        link = None
    return {"id": media_id, "link": link}


def token_pagina(PAGINA, base=None):
    base = base or TOKEN
    try:
        return api("GET", PAGINA, base, fields="access_token")["access_token"]
    except (MetaError, KeyError):
        return base


def publicar_facebook(post):
    _, PAGINA = conta_do_post(post)
    if not PAGINA:
        raise MetaError("esta conta nao tem pagina_id no config.json")
    tp = token_pagina(PAGINA, token_da_conta(post))
    if post["tipo"] == "reel":
        return publicar_facebook_reel(post, PAGINA, tp)
    imgs, legenda = post["imagens"], post["legenda"]
    if len(imgs) == 1:
        r = api("POST", f"{PAGINA}/photos", tp, url=url_imagem(imgs[0]),
                caption=legenda, published="true")
        return {"id": r.get("post_id") or r.get("id")}
    anexos = []
    for n in imgs:
        r = api("POST", f"{PAGINA}/photos", tp, url=url_imagem(n),
                published="false")
        anexos.append({"media_fbid": r["id"]})
    r = api("POST", f"{PAGINA}/feed", tp, message=legenda,
            attached_media=json.dumps(anexos))
    return {"id": r.get("id")}


def _wp_auth():
    cred = f"{WP_USUARIO}:{WP_SENHA}".encode()
    return "Basic " + base64.b64encode(cred).decode()


def wp(metodo, caminho, corpo=None, cabecalhos=None):
    """Chama a API REST do WordPress (senha de aplicativo no cabecalho)."""
    if not (SITE_URL and WP_USUARIO and WP_SENHA):
        raise MetaError("site: falta site_url no config.json ou os Secrets "
                        "WP_USUARIO/WP_SENHA")
    h = {"Authorization": _wp_auth(), "User-Agent": "publicador-revista-moderna/1.0",
         "Accept": "application/json"}
    h.update(cabecalhos or {})
    req = urllib.request.Request(f"{SITE_URL}/wp-json/wp/v2/{caminho}",
                                 data=corpo, method=metodo, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise MetaError(f"site HTTP {e.code}: "
                        f"{e.read().decode('utf-8', 'replace')[:500]}")
    except urllib.error.URLError as e:
        raise MetaError(f"site: falha de rede: {e}")


def texto_para_html(texto):
    blocos = [b.strip() for b in texto.replace("\r", "").split("\n\n") if b.strip()]
    return "\n".join(f"<p>{html.escape(b).replace(chr(10), '<br>')}</p>"
                      for b in blocos)


def publicar_site(post):
    cfg = post["site"]
    # imagem destacada
    nome = cfg.get("imagem") or (post.get("capa") if post["tipo"] == "reel" else post["imagens"][0])
    dados = (RAIZ / "fila" / nome).read_bytes()
    midia = wp("POST", "media", dados, {
        "Content-Type": "image/jpeg",
        "Content-Disposition": f'attachment; filename="{nome}"'})
    conteudo = texto_para_html(cfg["texto"])
    creditos = []
    if post.get("foto_credito"):
        creditos.append(f"Foto: {post['foto_credito']}")
    if post.get("fonte"):
        creditos.append(f"Fonte: {post['fonte']}")
    link_video = (post.get("resultado", {}).get("instagram") or {}).get("link")
    if post["tipo"] == "reel" and link_video:
        conteudo += (f'\n<p><a href="{html.escape(link_video)}">'
                     f"Assista ao vídeo no Instagram</a></p>")
    if creditos:
        conteudo += f"\n<p><em>{html.escape(' | '.join(creditos))}</em></p>"
    corpo = {"title": cfg["titulo"], "content": conteudo,
             "status": cfg.get("status", "publish"),
             "featured_media": midia["id"]}
    if cfg.get("resumo"):
        corpo["excerpt"] = cfg["resumo"]
    if cfg.get("categorias"):
        corpo["categories"] = cfg["categorias"]
    r = wp("POST", "posts", json.dumps(corpo).encode(),
           {"Content-Type": "application/json"})
    return {"id": r.get("id"), "link": r.get("link"), "status": r.get("status")}


def derivar_site(post):
    """Monta o bloco 'site' a partir da legenda, se o post nao trouxer um."""
    import re
    blocos = [b.strip() for b in post["legenda"].replace("\r", "").split("\n\n")]
    texto = []
    for b in blocos:
        if not b:
            continue
        if re.fullmatch(r"(#\w+\s*)+", b):
            continue
        if b.startswith("Foto:") or "texto de Revista Moderna" in b:
            continue
        texto.append(b)
    corpo = "\n\n".join(texto)
    titulo = post.get("titulo")
    if not titulo:
        primeira = re.split(r"(?<=[.!?])\s", texto[0], maxsplit=1)[0] if texto else "Revista Moderna"
        titulo = re.sub("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\uFE0F]", "", primeira).strip()[:110]
    return {"titulo": titulo, "texto": corpo, "status": "publish"}


def validar(post):
    for campo in ("horario", "tipo", "legenda"):
        if campo not in post:
            return f"falta o campo '{campo}'"
    if post["tipo"] not in ("feed", "carrossel", "reel", "story"):
        return "tipo deve ser 'feed', 'carrossel', 'reel' ou 'story'"
    if post["tipo"] == "story" and "facebook" in post.get("plataformas", []):
        return "story so pode ir para o instagram"
    if post["tipo"] == "reel":
        return validar_reel(post)
    if "imagens" not in post:
        return "falta o campo 'imagens'"
    imgs = post["imagens"]
    if not isinstance(imgs, list) or not imgs:
        return "'imagens' deve ser uma lista com pelo menos um arquivo"
    if post["tipo"] in ("feed", "story") and len(imgs) != 1:
        return f"tipo '{post['tipo']}' precisa de exatamente 1 imagem"
    if post["tipo"] == "carrossel" and not (2 <= len(imgs) <= 10):
        return "tipo 'carrossel' precisa de 2 a 10 imagens"
    if post.get("conta") and post["conta"] not in CONTAS:
        return f"conta '{post['conta']}' nao existe em config.json (contas)"
    if len(post["legenda"]) > 2200:
        return "legenda passa de 2200 caracteres"
    if "site" in post:
        for campo in ("titulo", "texto"):
            if not post["site"].get(campo):
                return f"site: falta '{campo}'"
        ni = post["site"].get("imagem")
        if ni and not (RAIZ / "fila" / ni).exists():
            return f"{ni}: imagem do site nao encontrada na fila/"
    for n in imgs:
        p = RAIZ / "fila" / n
        if not n.lower().endswith((".jpg", ".jpeg")):
            return f"{n}: so JPEG e aceito"
        if not p.exists():
            return f"{n}: arquivo nao encontrado na fila/"
        if p.stat().st_size > 8 * 1024 * 1024:
            return f"{n}: maior que 8 MB"
    return None


def validar_reel(post):
    v = post.get("video")
    if not v:
        return "tipo 'reel' precisa do campo 'video' (.mp4 na fila/)"
    if not v.lower().endswith(".mp4"):
        return f"{v}: o video deve ser .mp4"
    pv = RAIZ / "fila" / v
    if not pv.exists():
        return f"{v}: arquivo nao encontrado na fila/"
    if pv.stat().st_size > 95 * 1024 * 1024:
        return f"{v}: maior que 95 MB"
    capa = post.get("capa")
    if capa:
        if not capa.lower().endswith((".jpg", ".jpeg")):
            return f"{capa}: a capa deve ser JPEG"
        if not (RAIZ / "fila" / capa).exists():
            return f"{capa}: capa nao encontrada na fila/"
    if post.get("conta") and post["conta"] not in CONTAS:
        return f"conta '{post['conta']}' nao existe em config.json (contas)"
    if len(post["legenda"]) > 2200:
        return "legenda passa de 2200 caracteres"
    if "site" in post:
        for campo in ("titulo", "texto"):
            if not post["site"].get(campo):
                return f"site: falta '{campo}'"
        ni = post["site"].get("imagem")
        if ni and not (RAIZ / "fila" / ni).exists():
            return f"{ni}: imagem do site nao encontrada na fila/"
    return None


def salvar(caminho, post):
    caminho.write_text(json.dumps(post, ensure_ascii=False, indent=2),
                       encoding="utf-8")


def mover(arquivo_json, post, destino, status, motivo=None):
    pasta = RAIZ / destino
    pasta.mkdir(exist_ok=True)
    extras = [post["site"]["imagem"]] if post.get("site", {}).get("imagem") else []
    extras += [post[k] for k in ("video", "capa") if post.get(k)]
    for n in post.get("imagens", []) + extras:
        origem = RAIZ / "fila" / n
        if origem.exists():
            shutil.move(str(origem), str(pasta / n))
    post["status"] = status
    if motivo:
        post["motivo"] = motivo
    post["movido_em"] = datetime.now(timezone.utc).isoformat()
    salvar(pasta / arquivo_json.name, post)
    arquivo_json.unlink()


def main():
    if (RAIZ / "PAUSA").exists():
        print("Arquivo PAUSA encontrado: nada sera publicado.")
        return 0
    if not TOKEN and not SIMULACAO:
        print("ERRO: META_TOKEN nao configurado.")
        return 1

    agora = datetime.now(timezone.utc)
    houve_erro = False
    arquivos = sorted((RAIZ / "fila").glob("*.json"))
    print(f"Agora (UTC): {agora.isoformat()} | posts na fila: {len(arquivos)}"
          f"{' | SIMULACAO' if SIMULACAO else ''}")

    for jf in arquivos:
        try:
            post = json.loads(jf.read_text(encoding="utf-8"))
            horario = datetime.fromisoformat(post["horario"])
            if horario.tzinfo is None:
                raise ValueError("horario sem fuso (use ex.: -03:00)")
        except Exception as e:
            print(f"[{jf.name}] ERRO ao ler: {e}")
            houve_erro = True
            continue

        if agora < horario - ANTECEDENCIA:
            print(f"[{jf.name}] ainda nao e hora ({post['horario']}).")
            continue

        if agora > horario + ATRASO_MAX:
            print(f"[{jf.name}] atrasado demais: indo para atrasados/.")
            if not SIMULACAO:
                mover(jf, post, "atrasados", "atrasado",
                      "passou do limite de atraso")
            continue

        conta_cfg = CONTAS.get(post.get("conta") or "", {})
        if post.get("conta") and "plataformas" not in post:
            post["plataformas"] = conta_cfg.get(
                "plataformas", ["instagram"] + (["facebook"] if conta_cfg.get("pagina_id") else []))
        if ("site" not in post and "plataformas" not in post
                and CFG.get("site_para_todos", False) and SITE_URL):
            post["site"] = derivar_site(post)

        erro = validar(post)
        if erro:
            print(f"[{jf.name}] INVALIDO: {erro}")
            houve_erro = True
            if not SIMULACAO:
                mover(jf, post, "atrasados", "invalido", erro)
            continue

        padrao = ["instagram", "facebook"] + (["site"] if "site" in post else [])
        plataformas = post.get("plataformas", padrao)
        resultado = post.setdefault("resultado", {})
        falhou = False
        for nome, funcao in (("instagram", publicar_instagram),
                             ("facebook", publicar_facebook),
                             ("site", publicar_site)):
            if nome not in plataformas or nome in resultado:
                continue
            if SIMULACAO:
                print(f"[{jf.name}] (simulacao) publicaria no {nome}.")
                continue
            try:
                resultado[nome] = funcao(post)
                salvar(jf, post)
                print(f"[{jf.name}] publicado no {nome}: {resultado[nome]}")
            except Exception as e:
                falhou = True
                print(f"[{jf.name}] ERRO no {nome}: {e}")

        if SIMULACAO:
            continue
        if falhou:
            houve_erro = True
            post["tentativas"] = post.get("tentativas", 0) + 1
            if post["tentativas"] >= MAX_TENTATIVAS:
                mover(jf, post, "atrasados", "falhou",
                      "falhou apos varias tentativas")
            else:
                salvar(jf, post)
        elif all(p in resultado for p in plataformas):
            mover(jf, post, "publicados", "publicado")
            print(f"[{jf.name}] concluido: movido para publicados/.")

    return 1 if houve_erro else 0


if __name__ == "__main__":
    sys.exit(main())
