# Publicador Revista Moderna – Itupeva e região (@arevistamoderna)

Guia para qualquer conversa do Claude (ou pessoa) continuar o trabalho.

## Como funciona
- Posts ficam em `fila/` como par de arquivos: `NOME.json` + `NOME.jpg`.
- O robô (`publicar.py`, workflow "Publicar") publica no Instagram e no Facebook via API oficial da Meta.
- Quem aciona o robô: cron-job.org, a cada 5 minutos (chave do GitHub vence em out/2027). Reserva: cron do GitHub.
- Janela: publica de `horario - antecedencia_minutos` (10 min) até `horario + atraso_maximo_horas` (3 h). Fora disso vai para `atrasados/`. Após publicar vai para `publicados/`.
- Pausa de emergência: criar arquivo `PAUSA` na raiz. Token da Meta: segredo `META_TOKEN` (GitHub Secrets; nunca em código ou chat).

## Formato do JSON
```json
{
  "tipo": "feed",
  "imagens": ["NOME.jpg"],
  "legenda": "texto com 5 hashtags, a última #RevistaModerna, e linha de créditos",
  "fonte": "Agência Brasil",
  "foto_credito": "Fotógrafo / Agência",
  "licenca_verificada": false,
  "horario": "2026-11-14T23:50:00-03:00",
  "status": "aprovado"
}
```
- `tipo`: `feed` (1 imagem) ou `carrossel` (2 a 10). Só JPEG, até 8 MB, proporção mínima 4:5.
- `horario` com fuso -03:00. Legenda até 2200 caracteres.
- Rascunhos ficam em `rascunhos/` (sem `horario`). Só vão para `fila/` depois que o dono diz "aprovar" e informa o horário.

## Arte
`python3 -I arte/montar_arte.py FOTO SAIDA.jpg "Linha1|Linha2|Linha3" crop=x0,y0,x1,y1`
Opcionais: `rosto=0.5`, `tamanho=64`, `alinhar=centro`. Saída 1068x1335. Grade diária de horários (BRT): 07:00, 09:30, 11:00, 12:30, 14:00, 15:30, 17:00, 18:30, 20:00, 21:30, 23:00.

## Regras
- Reescrever textos com palavras próprias; creditar foto e fonte; evitar temas sensíveis.
- Não repetir matéria já publicada (ver `publicados/`).
- Aprovação do dono antes de cada post entrar na fila.

## Site (arevistamoderna.com.br – WordPress)
- Todo post aprovado também é publicado direto no site (`site_para_todos: true` em `config.json`), usando a imagem como destaque, com os créditos no fim.
- Para controlar título e texto da matéria, inclua no JSON: `"titulo": "..."` e/ou `"site": {"titulo": "...", "texto": "parágrafos separados por linha em branco", "status": "publish"}`. Sem `site`, o robô monta a matéria a partir da legenda (sem hashtags e sem a linha de créditos).
- Para não ir ao site: `"plataformas": ["instagram", "facebook"]`. Para só o site: `["site"]`. `"status": "draft"` cria rascunho em vez de publicar.
- Segredos: `WP_USUARIO` e `WP_SENHA` (senha de aplicativo do WordPress), nos GitHub Secrets.
- **Imagem do site: só a foto, sem layout, 1200x800.** Gere com `python3 -I arte/foto_site.py FOTO NOME-site.jpg [crop=x0,y0,x1,y1] [rosto=0.5]` e aponte no JSON em `"site": {"imagem": "NOME-site.jpg", ...}` (o arquivo vai junto na `fila/`). Sem `site.imagem`, o robô usa a arte do Instagram.
- **Título da arte:** use um título LONGO e informativo (cerca de 80 a 110 caracteres), SEM "|", e deixe a quebra automática: o script usa fonte 54, margem esquerda 50 e direita 40, até 3 linhas largas, como no modelo do dono.

## Outras contas (ex.: Alto Uruguai)
- O padrão continua sendo Itupeva (`instagram_id`/`pagina_id` do topo do `config.json`).
- Para publicar em outra conta, ponha no JSON do post `"conta": "altouruguai"`. Os IDs ficam em `config.json` → `contas`.
- Uma conta extra publica só nas `plataformas` definidas para ela (Alto Uruguai: só Instagram; nunca vai para o site de Itupeva).
- Cada conta pode ter sua chave: `token_env` em `contas` aponta o Secret (Alto Uruguai: `META_TOKEN_ALTOURUGUAI`, do portfólio "Look do dia"). Sem `token_env`, usa `META_TOKEN`, que precisa ter acesso ao Instagram/Página dessa conta no Gerenciador de Negócios da Meta. Confira rodando o workflow "Teste de conexao Meta".
- **Arte do Alto Uruguai:** `python3 -I arte/montar_arte_altouruguai.py FOTO SAIDA.jpg "Título longo da matéria" crop=x0,y0,x1,y1` (modelo `arte/template_altouruguai.png`, faixa clara, título Anton azul-escuro em maiúsculas e minúsculas, fonte 54, até 3 linhas largas, mesmo tamanho do modelo de Itupeva). Título de 80 a 110 caracteres, sem "|".
