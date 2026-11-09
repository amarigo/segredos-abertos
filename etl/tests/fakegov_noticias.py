"""Busca de notícias simulada (API do GDELT, RSS do Bing Notícias) e as páginas das notícias, para os testes.

Só o PL 250/2024 (na pauta, sem documento oficial contra) tem notícias:
- jornal-a: crítica clara, com quem fala e link (deve aparecer);
- jornal-b: fala do PL 250 só de passagem e critica outro projeto (não deve aparecer);
- jornal-c: não cita o número do projeto (não deve aparecer);
- jornal-d: recusa robôs (HTTP 403);
- jornal-e: achado pelo Google Notícias, que dá o link codificado (deve aparecer, com o endereço original).
"""
from __future__ import annotations

import json

A = "https://www.jornal-a.com.br/politica/transporte-escolar-rural"
B = "https://jornal-b.com.br/resumo-da-semana"
C = "https://jornal-c.com.br/opiniao/estradas"
D = "https://jornal-d.com.br/bloqueado"
E = "https://jornal-e.com.br/2026/10/criticas-ao-pl-250"

PAGINAS = {
    A: """<html><head><title>x</title><meta property="og:site_name" content="Jornal A">
<meta property="og:title" content="Prefeitos criticam PL 250/2024 do transporte escolar">
<script type="application/ld+json">{"@type":"NewsArticle","author":{"name":"Maria Repórter"},"datePublished":"2026-10-30T10:00:00-03:00"}</script>
</head><body><nav><p>Menu do site com muitas palavras para enganar o leitor de parágrafos.</p></nav>
<p>O Senado pode votar nesta semana o PL 250/2024, que muda o transporte escolar rural.</p>
<p>Segundo a Confederação Nacional de Municípios, o texto cria uma despesa sem fonte e pode prejudicar o orçamento das prefeituras pequenas. A entidade pede mais prazo.</p>
<p>O autor defende que a proposta melhora a vida dos alunos do campo.</p>
<script>var x = "O projeto é um risco, afirmou alguém no código";</script>
</body></html>""",
    B: """<html><head><meta property="og:site_name" content="Jornal B"><meta property="og:title" content="Resumo da semana no Congresso"></head><body>
<p>Na pauta da semana estão o PL 250/2024, sobre transporte escolar, e o PL 999/2025, sobre loterias.</p>
<p>Sobre o PL 999/2025, especialistas afirmaram que o texto traz risco de lavagem de dinheiro e critica a falta de controle.</p>
</body></html>""",
    E: """<html><head><meta property="og:site_name" content="Jornal E (site)"><meta name="author" content="João Colunista">
<meta property="article:published_time" content="2026-10-20T08:00:00Z"><title>Críticas ao PL 250</title></head><body>
<p>O Projeto de Lei 250, de 2024, volta à pauta.</p>
<p>“O texto é um retrocesso para quem mora longe da escola”, afirmou a deputada Sicrana Silva em audiência pública.</p>
</body></html>""",
    C: """<html><head><meta property="og:site_name" content="Jornal C"></head><body>
<p>As estradas rurais estão ruins, e o deputado Fulano afirmou que qualquer projeto é um risco para as prefeituras.</p>
</body></html>""",
}


def rota(netloc: str, path: str, q: dict):
    if netloc == "api.gdeltproject.org" and path == "/api/v2/doc/doc":
        arts = []
        if "250/2024" in q.get("query", ""):
            arts = [{"url": A, "title": "Prefeitos criticam", "seendate": "20261030T130000Z", "language": "Portuguese"},
                    {"url": B, "title": "Resumo", "seendate": "20261029T130000Z"},
                    {"url": "https://www12.senado.leg.br/noticias/x", "title": "Agência", "seendate": "20261028T130000Z"}]
        return 200, json.dumps({"articles": arts} if arts else {}).encode(), "application/json"
    if netloc == "news.google.com" and path == "/rss/search":
        itens = ""
        if "250/2024" in q.get("q", ""):
            itens = ("<item><title>Críticas ao PL 250 - Jornal E</title><link>https://news.google.com/rss/articles/GID-E?oc=5</link>"
                     "<pubDate>Tue, 20 Oct 2026 08:00:00 GMT</pubDate><source url=\"https://jornal-e.com.br\">Jornal E</source></item>"
                     "<item><title>Agência</title><link>https://news.google.com/rss/articles/GID-SENADO</link>"
                     "<source url=\"https://www12.senado.leg.br\">Senado</source></item>")
        return 200, f'<?xml version="1.0"?><rss><channel>{itens}</channel></rss>'.encode(), "application/rss+xml"
    if netloc == "news.google.com" and path == "/rss/articles/GID-E":
        return 200, b'<html><c-wiz><div data-n-a-sg="ASSINATURA" data-n-a-ts="1761000000"></div></c-wiz></html>', "text/html"
    if netloc == "news.google.com" and path == "/_/DotsSplashUi/data/batchexecute":
        interno = json.dumps(["garturlres", E, 1])
        return 200, (")]}'\n\n" + json.dumps([["wrb.fr", "Fbv4je", interno, None, None, None, "generic"]])).encode(), "application/json"
    if netloc == "www.bing.com" and path == "/news/search":
        itens = ""
        if "250/2024" in q.get("q", ""):
            for u in (A, C, D):
                itens += (f"<item><title>t</title><link>http://www.bing.com/news/apiclick.aspx?ref=FexRss&amp;aid=&amp;"
                          f"url={u.replace(':', '%3a').replace('/', '%2f')}&amp;c=1</link>"
                          "<pubDate>Thu, 29 Oct 2026 12:00:00 GMT</pubDate></item>")
        return 200, f'<?xml version="1.0"?><rss><channel>{itens}</channel></rss>'.encode(), "application/rss+xml"
    for u, corpo in PAGINAS.items():
        if u.split("//", 1)[1].split("/", 1)[0] == netloc and u.endswith(path):
            return 200, corpo.encode(), "text/html; charset=utf-8"
    if netloc == "jornal-d.com.br":
        return 403, b"Access denied", "text/html"
    return None
