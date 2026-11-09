"""Quem fala contra um projeto em notícias, quando nenhum documento oficial é contra.

Ordem das fontes (regra do projeto: oficial primeiro):
1. Documentos oficiais (debate.py): parecer pela rejeição e voto em separado, pelas APIs da Câmara e do Senado.
   Só quando nenhum deles é contra, procuramos em notícias.
2. Notícias. Primeiro a API pública do GDELT (https://api.gdeltproject.org/api/v2/doc/doc), a única API aberta de
   busca de notícias; mas ela só guarda os últimos 3 meses e, do GitHub Actions, costuma recusar com HTTP 429 (o
   limite de 1 pedido a cada 5 segundos é dividido com todo mundo que usa o mesmo endereço). Por isso usamos também os
   feeds RSS de busca do Google Notícias e do Bing Notícias (sem chave), que acham notícias antigas (testado em
   09/11/2026: só o Google achou as notícias do PL 4.881/2023, de setembro de 2025). O RSS do Google dá um link
   codificado; o endereço original sai do serviço que a própria página do Google Notícias usa para abrir a notícia.
   Nenhuma busca traz o texto: ele vem da própria página da notícia (HTML), porque os jornais não oferecem API.

Regras para nunca inventar:
- A notícia só conta se o texto citar a proposta pelo número e ano (ex.: "PL 4.881/2023").
- Copiamos, sem trocar nenhuma palavra, até duas frases da notícia que falam contra (crítica, risco, oposição) e
  dizem quem fala ("afirmou", "segundo"...). Só frases do trecho da notícia que trata desta proposta.
- "Quem fala" é o nome que aparece na própria frase; se a frase não deixa claro, fica vazio e o site manda ler a
  notícia. Veículo, título, data e link vêm da página da notícia.
- Tudo vai marcado no site como notícia, não documento oficial. Se nada for achado, o site diz que procurou e não achou.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import logging
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .util import _session, get, url_segura

log = logging.getLogger("sa_etl.noticias")

GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"
BING = "https://www.bing.com/news/search"
GOOGLE = "https://news.google.com/rss/search"
GOOGLE_ARTIGO = "https://news.google.com/rss/articles/{id}"
GOOGLE_DECODIFICAR = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
VERSAO_CACHE = 1
DIAS_BUSCA = 3         # a busca de uma proposta vale 3 dias; depois procuramos de novo
DIAS_ARTIGO = 60       # a página de uma notícia lida vale 60 dias
ESPERA_GDELT = 6       # a API do GDELT pede no máximo um pedido a cada 5 segundos
MAX_ARTIGOS = 8        # notícias abertas por proposta
MAX_NOTICIAS = 3       # notícias mostradas por proposta
MAX_TRECHO = 420
# Navegador genérico: muitos jornais recusam quem não se apresenta assim. Sem dado pessoal.
UA = "Mozilla/5.0 (compatible; SegredosAbertos/0.1; +https://github.com/amarigo/segredos-abertos)"
# Sites oficiais já entram pelos documentos; aqui só imprensa
OFICIAIS = re.compile(r"(^|\.)(camara\.leg\.br|senado\.leg\.br|senado\.gov\.br|congressonacional\.leg\.br|gov\.br)$")

NOMES_LONGOS = {
    "PL": r"projeto de lei", "PLP": r"projeto de lei complementar", "PEC": r"proposta de emenda (?:[àa] )?constitui[çc][ãa]o",
    "MPV": r"MP|medida provis[óo]ria", "PDL": r"projeto de decreto legislativo",
}


# ---------------------------------------------------------------- reconhecer a proposta no texto

def _num_regex(numero: str) -> str:
    """4881 -> 4\\.?881 (os jornais escrevem 4881 ou 4.881)."""
    n = str(int(numero))
    if len(n) <= 3:
        return n
    return rf"{n[:-3]}\.?{n[-3:]}"


def padrao_proposta(sigla: str, numero: str, ano: str) -> re.Pattern:
    """PL 4.881/2023, PL nº 4881/23, Projeto de Lei 4.881, de 2023..."""
    nome = rf"(?:{sigla}|{NOMES_LONGOS.get(sigla, sigla)})"
    return re.compile(rf"\b{nome}\s*(?:n[º°o.]*\s*)?{_num_regex(numero)}\s*(?:/\s*(?:{ano}|{ano[-2:]})|,?\s+de\s+{ano})\b", re.I)


_OUTRA = re.compile(r"\b(?:PL|PLP|PEC|PDL|MP|MPV|projeto de lei|proposta de emenda)\s*(?:n[º°o.]*\s*)?\d[\d.]*\s*(?:/|,?\s+de\s+)\s*\d{2,4}\b", re.I)


# ---------------------------------------------------------------- frases contra

# Palavras de oposição. Testado com dados reais em 09/11/2026: "risco", "ameaça" e "problema" sozinhos pegavam frases que
# descrevem o problema que o projeto quer resolver ("o albino é ameaçado pelos riscos do câncer de pele"), e "crític"
# pegava "minerais críticos". Por isso as palavras fortes são obrigatórias e as fracas só somam.
_CONTRA = re.compile(
    r"\bcritic(?:a|am|ou|aram|ar|ando)\b|\bcr[íi]ticas?\b|\bcr[íi]ticos? (?:d[aoe]s?|ao|à)\b|\bse op[õo]e|\bop[õo]e-se|"
    r"\bopuse|\bopo(?:sição|sicao)\b|\bcontr[áa]ri[oa]s?\b|\brejei[çct]|\bpreocupa|\balert|\bprejudic|\bretrocesso|"
    r"\binconstitucional|\bdesvirtu|\benfraquec|\bequ[íi]voc|\bonera|\binseguran[çc]a jur|\binvi[áa]vel|\bdistor[çc]|"
    r"\bimpacto negativo|\bcontra (?:o|a) (?:projeto|proposta|texto|PL|PEC|medida|mudan)", re.I)
_FRACAS = re.compile(r"\briscos?\b|\bamea[çc]|\bproblem|\bdanos?\b|\bdesvio|\bpreju[íi]z", re.I)
# A frase tem de falar da proposta (ou ser a fala de alguém, entre aspas), não de outro assunto da página
_PROPOSTA = re.compile(r"\b(?:projeto|proposta|propos|texto|PLP?|PEC|PDL|MP|medida|mat[ée]ria|relat[óo]rio|substitutivo|"
                       r"mudan[çc]a|altera[çc]|lei)\b|[“\"]", re.I)
_QUEM_DIZ = re.compile(
    r"\bafirm|\bdiss(?:e|eram)\b|\bdiz(?:em)?\b|\bdeclar|\bavali|\bsegundo\b|\bde acordo com\b|\bcritic|\balert|"
    r"\bdefend|\bargument|\bressalt|\bapont|\bexplic|\bsustent|\bconsider|\bavisa|\bpara (?:o|a) [A-ZÁÉÍÓÚ]|"
    r"\bem nota\b|\bnota t[ée]cnica\b|\bpara (?:a |o )?(?:entidade|associa|ministério|confedera|federa)", re.I)
# Frase a favor ("o projeto vai reduzir riscos") não é contra: estes descontam
_A_FAVOR = re.compile(r"\b(?:reduz(?:ir)?|diminu\w*|combat\w*|evitar?) (?:o |os |a |as )?(?:risco|preju[íi]zo|dano|problema)", re.I)

_PAPEL = (r"(?:(?:o|a|os|as)\s+)?(?:(?:senador|senadora|deputad[oa]|ministr[oa]|presidente|diretor[a]?|secret[áa]ri[oa]|"
          r"economista|especialista|advogad[oa]|professor[a]?|pesquisador[a]?|relator[a]?|l[íi]der|coordenador[a]?|"
          r"porta-voz|governador[a]?|prefeit[oa]|t[ée]cnicos?)\s+(?:d[aeo]s?\s+)?)?")
_NOME = r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ú.\-]+(?:\s+(?:d[aeo]s?\s+|e\s+)?[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ú.\-]+){0,5}"
_VERBO = r"(?:afirm(?:a|ou)|diss(?:e|eram)|diz(?:em)?|declar(?:a|ou)|avali(?:a|ou)|critic(?:a|ou)|alert(?:a|ou)|defend(?:e|eu)|argument(?:a|ou)|ressalt(?:a|ou)|apont(?:a|ou)|explic(?:a|ou)|sustent(?:a|ou)|consider(?:a|ou))"
_QUEM = [
    re.compile(rf"\b(?:[Ss]egundo|[Dd]e acordo com)\s+(?P<q>{_PAPEL}{_NOME})"),
    re.compile(rf"^Para\s+(?P<q>{_PAPEL}{_NOME}),"),  # "Para a ABSAE, ..." (no meio da frase, "para" quase nunca é quem fala)
    re.compile(rf"(?P<q>{_PAPEL}{_NOME}),?\s+{_VERBO}\b"),
    re.compile(rf"\b{_VERBO}\s+(?P<q>{_PAPEL}{_NOME})"),
]
# Palavras com maiúscula que não são quem fala
_NAO_QUEM = re.compile(r"^(?:o |a |os |as )?(?:O|A|Os|As|Ele|Ela|Eles|Elas|Isso|Esse|Essa|Este|Esta|Segundo|Projeto|Proposta|PL|PEC|Texto|Lei|Senado|Câmara|Brasil)\b")


def quem_fala(frase: str) -> str:
    """O nome de quem fala, como está escrito na frase (ou "" se a frase não deixa claro)."""
    for p in _QUEM:
        for m in p.finditer(frase):
            q = m.group("q").strip(" ,.;:")
            nucleo = re.sub(rf"^{_PAPEL}", "", q).strip()
            if len(nucleo) < 3 or _NAO_QUEM.match(q) or _NAO_QUEM.match(nucleo) or len(q) > 90:
                continue
            q = re.sub(r"^(?:o|a|os|as)\s+", "", q, flags=re.I)
            return q[0].upper() + q[1:]
    return ""


def _nota_contra(f: str) -> float:
    if not (80 <= len(f) <= 700):
        return -1
    if not _CONTRA.search(f) or not _QUEM_DIZ.search(f) or not _PROPOSTA.search(f):
        return -1
    n = (2 * len(_CONTRA.findall(f)) + len(_FRACAS.findall(f)) + 1.5 * min(2, len(_QUEM_DIZ.findall(f)))
         - 3 * len(_A_FAVOR.findall(f)))
    if re.search(r"[“\"]", f):
        n += 1  # citação entre aspas: é a fala de alguém, não do jornal
    return n


def _cortar(f: str) -> str:
    if len(f) <= MAX_TRECHO:
        return f
    return f[:MAX_TRECHO].rsplit(" ", 1)[0].rstrip(",;:") + " […]"


_SPLIT = re.compile(r"(?<=[.!?…”\"])\s+(?=[\"“(]?[A-ZÁÉÍÓÚÂÊÔÃÕÇ])")
_ABREV = re.compile(r"\b(?:art|arts|inc|Dep|Sr|Sra|Dr|Dra|Prof|Profa|Min|Sen|nº|n|p|pp)\.$", re.I)


def frases(texto: str) -> list[str]:
    out: list[str] = []
    for p in _SPLIT.split(texto or ""):
        if out and _ABREV.search(out[-1]):
            out[-1] = f"{out[-1]} {p}"
        else:
            out.append(p)
    return [f.strip() for f in out if f.strip()]


def trechos_contra(paragrafos: list[str], titulo: str, padrao: re.Pattern, n: int = 2) -> list[str]:
    """Até n frases contra, copiadas sem mudança, só dos parágrafos que tratam desta proposta.

    Um parágrafo trata desta proposta se ela foi citada nele ou antes dele (ou no título), e nenhuma outra proposta
    foi citada depois disso (notícia que fala de vários projetos)."""
    nossa = bool(padrao.search(titulo or ""))
    cands: list[tuple[float, int, str]] = []
    k = 0
    for p in paragrafos:
        tem_nossa = bool(padrao.search(p))
        outras = [m for m in _OUTRA.finditer(p) if not padrao.search(m.group(0))]
        if tem_nossa:
            nossa = True
        elif outras:
            nossa = False
        if not nossa:
            continue
        for f in frases(p):
            nota = _nota_contra(f)
            if nota >= 3.5:
                cands.append((nota, k, f))
            k += 1
    melhores = sorted(cands, key=lambda c: (-c[0], c[1]))[:n]
    return [_cortar(f) for _, _, f in sorted(melhores, key=lambda c: c[1])]


# ---------------------------------------------------------------- página da notícia

class _Pagina(HTMLParser):
    """Lê do HTML só o que precisamos: metadados (título, veículo, autor, data) e o texto dos parágrafos."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.ld: list[str] = []
        self.paragrafos: list[str] = []
        self.titulo = ""
        self._pilha: list[str] = []
        self._buf: list[str] | None = None
        self._ignorar = 0
        self._em_titulo = False
        self._em_ld = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            k = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if k and a.get("content") and k not in self.meta:
                self.meta[k] = a["content"].strip()
        elif tag in ("script", "style", "noscript", "nav", "footer", "aside", "form", "figcaption"):
            if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
                self._em_ld = True
                self.ld.append("")
            else:
                self._ignorar += 1
        elif tag == "title":
            self._em_titulo = True
        elif tag == "p" and not self._ignorar:
            self._buf = []
        elif tag == "br" and self._buf is not None:
            self._buf.append(" ")

    def handle_endtag(self, tag):
        if tag in ("style", "noscript", "nav", "footer", "aside", "form", "figcaption") or (tag == "script" and not self._em_ld):
            self._ignorar = max(0, self._ignorar - 1)
        elif tag == "script":
            self._em_ld = False
        elif tag == "title":
            self._em_titulo = False
        elif tag == "p" and self._buf is not None:
            t = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if len(t) >= 40:
                self.paragrafos.append(t)
            self._buf = None

    def handle_data(self, data):
        if self._em_ld:
            self.ld[-1] += data
        elif self._em_titulo:
            self.titulo += data
        elif self._buf is not None and not self._ignorar:
            self._buf.append(data)


def _ld_campos(blocos: list[str]) -> dict:
    """Autor, veículo e data do JSON-LD (schema.org NewsArticle), quando a página traz."""
    out: dict = {}

    def nome(x):
        if isinstance(x, list):
            return ", ".join(n for n in (nome(i) for i in x[:3]) if n)
        if isinstance(x, dict):
            return str(x.get("name") or "").strip()
        return str(x or "").strip()

    def visitar(o):
        if isinstance(o, list):
            for i in o:
                visitar(i)
        elif isinstance(o, dict):
            if "@graph" in o:
                visitar(o["@graph"])
            tipo = o.get("@type")
            tipos = tipo if isinstance(tipo, list) else [tipo]
            if any(str(t).endswith(("Article", "NewsArticle", "ReportageNewsArticle", "BlogPosting")) for t in tipos):
                out.setdefault("autor", nome(o.get("author")))
                out.setdefault("veiculo", nome(o.get("publisher")))
                out.setdefault("data", str(o.get("datePublished") or "")[:10])
                out.setdefault("titulo", str(o.get("headline") or "").strip())

    for b in blocos:
        try:
            visitar(json.loads(b))
        except ValueError:
            continue
    return {k: v for k, v in out.items() if v}


def ler_pagina(raw: str, url: str) -> dict:
    p = _Pagina()
    try:
        p.feed(raw)
    except Exception:  # noqa: BLE001 - HTML quebrado: fica o que deu para ler
        pass
    ld = _ld_campos(p.ld)
    m = p.meta
    site = (urlsplit(url).hostname or "").removeprefix("www.")
    autor = ld.get("autor") or m.get("author") or m.get("article:author") or ""
    if autor.startswith("http"):
        autor = ""
    return {
        "titulo": html.unescape(ld.get("titulo") or m.get("og:title") or p.titulo).strip()[:300],
        "veiculo": html.unescape(m.get("og:site_name") or ld.get("veiculo") or site).strip()[:120],
        "autor": html.unescape(autor).strip()[:120],
        "data": (ld.get("data") or m.get("article:published_time") or m.get("datepublished") or m.get("date") or "")[:10],
        "paragrafos": p.paragrafos[:200],
    }


# ---------------------------------------------------------------- busca

def _frases_busca(sigla: str, numero: str, ano: str) -> list[str]:
    n = str(int(numero))
    com_ponto = f"{int(n):,}".replace(",", ".")
    return sorted({f'"{sigla} {n}/{ano}"', f'"{sigla} {com_ponto}/{ano}"'})


def _limpar_url(u: str) -> str:
    u = url_segura(u)
    if not u:
        return ""
    host = (urlsplit(u).hostname or "").lower()
    if not host or OFICIAIS.search(host) or host.endswith(("bing.com", "google.com", "gdeltproject.org")):
        return ""
    return u


def buscar_gdelt(sigla: str, numero: str, ano: str) -> list[dict]:
    fs = _frases_busca(sigla, numero, ano)
    q = f"({' OR '.join(fs)})" if len(fs) > 1 else fs[0]
    r = get(GDELT, params={"query": f"{q} sourcelang:portuguese", "mode": "artlist", "format": "json",
                           "maxrecords": 50, "sort": "datedesc", "timespan": "3months"},
            timeout=60, tries=1, headers={"User-Agent": UA})
    try:
        arts = (r.json() or {}).get("articles") or []
    except ValueError:  # o GDELT responde texto quando a busca é curta demais
        return []
    out = []
    for a in arts:
        u = _limpar_url(a.get("url"))
        if u:
            d = str(a.get("seendate") or "")
            out.append({"url": u, "titulo": (a.get("title") or "").strip(),
                        "data": f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) >= 8 else ""})
    return out


def buscar_bing(sigla: str, numero: str, ano: str) -> list[dict]:
    """Feed RSS de busca do Bing Notícias. O link de cada item passa pelo Bing, com o endereço original no parâmetro url."""
    import xml.etree.ElementTree as ET

    itens = []
    for q in _frases_busca(sigla, numero, ano):  # o Bing não aceitou "a" OR "b" no teste: uma busca por forma
        r = get(BING, params={"q": q, "format": "rss", "setlang": "pt-BR", "cc": "BR"}, timeout=60, tries=2,
                headers={"User-Agent": UA, "Accept": "application/rss+xml,application/xml,*/*"})
        try:
            itens += _rss(ET.fromstring(r.content))
        except ET.ParseError:
            continue
    out = []
    for it in itens:
        link = (it.findtext("link") or "").strip()
        orig = parse_qs(urlsplit(link).query).get("url", [""])[0] if "bing.com" in link else link
        u = _limpar_url(orig)
        if u:
            out.append({"url": u, "titulo": (it.findtext("title") or "").strip(), "data": _data_rss(it.findtext("pubDate") or "")})
    return out


def _rss(raiz) -> list:
    return list(raiz.iter("item"))


def _data_rss(txt: str) -> str:
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(txt or "").date().isoformat()
    except (TypeError, ValueError):
        return ""


def buscar_google(sigla: str, numero: str, ano: str) -> list[dict]:
    """Feed RSS de busca do Google Notícias. O link vem codificado (news.google.com/rss/articles/<id>): guardamos o id e
    só descobrimos o endereço original da notícia quando formos abri-la (google_original)."""
    import xml.etree.ElementTree as ET

    q = " OR ".join(_frases_busca(sigla, numero, ano))
    r = get(GOOGLE, params={"q": q, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"}, timeout=60, tries=2,
            headers={"User-Agent": UA, "Accept": "application/rss+xml,application/xml,*/*"})
    try:
        raiz = ET.fromstring(r.content)
    except ET.ParseError:
        return []
    out = []
    for it in _rss(raiz):
        m = re.search(r"/articles/([A-Za-z0-9_-]+)", it.findtext("link") or "")
        fonte = it.find("source")
        site = (fonte.get("url") if fonte is not None else "") or ""
        if not m or OFICIAIS.search(urlsplit(site).hostname or ""):
            continue
        titulo = (it.findtext("title") or "").strip()
        veiculo = (fonte.text or "").strip() if fonte is not None else ""
        if veiculo and titulo.endswith(f" - {veiculo}"):
            titulo = titulo[: -len(veiculo) - 3]
        out.append({"google": m.group(1), "url": "", "titulo": titulo, "veiculo": veiculo,
                    "data": _data_rss(it.findtext("pubDate") or "")})
    return out


def google_original(gid: str) -> str:
    """Endereço original de uma notícia do Google Notícias: a página do artigo traz uma assinatura e a hora
    (data-n-a-sg, data-n-a-ts), que o serviço batchexecute troca pelo endereço do jornal."""
    r = get(GOOGLE_ARTIGO.format(id=gid), timeout=30, tries=2, headers={"User-Agent": UA, "Accept": "text/html"})
    sg = re.search(r'data-n-a-sg="([^"]+)"', r.text)
    ts = re.search(r'data-n-a-ts="(\d+)"', r.text)
    if not sg or not ts:
        return ""
    pedido = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1],
                             "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], gid, int(ts.group(1)), sg.group(1)]
    resp = _session.post(GOOGLE_DECODIFICAR, data={"f.req": json.dumps([[["Fbv4je", json.dumps(pedido)]]])},
                         headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                         timeout=30)
    resp.raise_for_status()
    try:
        partes = resp.text.split("\n\n", 1)
        dados = json.loads(partes[1] if len(partes) > 1 else partes[0])
        return _limpar_url(json.loads(dados[0][2])[1])
    except (ValueError, IndexError, TypeError):
        return ""


class Buscador:
    """Busca e lê as notícias, com cache em cache/noticias/ e limite de tempo por coleta (o resto fica para o dia seguinte)."""

    def __init__(self, cache: Path, minutos: float = 10, hoje: dt.date | None = None):
        self.pasta = cache / "noticias"
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.fim = time.monotonic() + minutos * 60
        self.hoje = hoje or dt.date.today()
        self._ultimo_gdelt = 0.0
        self.buscas = self.faltaram = self.achadas = 0
        self.fontes_ok: set[str] = set()
        self.fontes_falha: set[str] = set()
        self.desligadas: set[str] = set()

    def _ler_cache(self, arq: Path, dias: int) -> dict | None:
        try:
            d = json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if d.get("v") != VERSAO_CACHE:
            return None
        try:
            idade = (self.hoje - dt.date.fromisoformat(d.get("em", ""))).days
        except ValueError:
            return None
        return d if idade < dias else None

    def _gravar(self, arq: Path, d: dict) -> None:
        arq.write_text(json.dumps({"v": VERSAO_CACHE, "em": self.hoje.isoformat(), **d}, ensure_ascii=False), encoding="utf-8")

    def _sem_tempo(self) -> bool:
        return time.monotonic() > self.fim

    def _achar(self, sigla, numero, ano) -> tuple[list[dict], int]:
        """Candidatos de todas as buscas, e quantas buscas responderam."""
        achados: dict[str, dict] = {}
        ok = 0
        for nome, fn in (("gdelt", buscar_gdelt), ("google", buscar_google), ("bing", buscar_bing)):
            if nome in self.desligadas:
                continue
            if nome == "gdelt":
                espera = ESPERA_GDELT - (time.monotonic() - self._ultimo_gdelt)
                if espera > 0:
                    time.sleep(espera)
                self._ultimo_gdelt = time.monotonic()
            try:
                for a in fn(sigla, numero, ano):
                    achados.setdefault(a["url"] or f"google:{a['google']}", a)
                self.fontes_ok.add(nome)
                ok += 1
            except Exception as e:  # noqa: BLE001 - uma busca fora do ar não impede a outra
                self.fontes_falha.add(nome)
                if nome == "gdelt":
                    # Do GitHub Actions o GDELT quase sempre recusa (HTTP 429, limite dividido com quem usa o mesmo
                    # endereço): depois da primeira recusa, não insistimos nesta coleta
                    self.desligadas.add(nome)
                log.info("Busca de notícias (%s) de %s %s/%s falhou: %s", nome, sigla, numero, ano, e)
        return list(achados.values()), ok

    def original(self, cand: dict) -> str:
        """Endereço original do candidato (os do Google Notícias são decodificados uma vez e guardados)."""
        if cand.get("url") or not cand.get("google"):
            return cand.get("url") or ""
        arq = self.pasta / f"g-{hashlib.sha1(cand['google'].encode()).hexdigest()}.json"
        try:
            return json.loads(arq.read_text(encoding="utf-8"))["url"]
        except (OSError, ValueError, KeyError):
            pass
        if self._sem_tempo():
            return ""
        try:
            u = google_original(cand["google"])
        except Exception as e:  # noqa: BLE001 - sem o endereço original não usamos a notícia
            log.info("Google Notícias: endereço original de %s indisponível: %s", cand["google"][:20], e)
            return ""
        if u:
            arq.write_text(json.dumps({"url": u}), encoding="utf-8")
        return u

    def artigo(self, url: str) -> dict | None:
        arq = self.pasta / f"a-{hashlib.sha1(url.encode()).hexdigest()}.json"
        c = self._ler_cache(arq, DIAS_ARTIGO)
        if c is not None:
            return c.get("pagina")
        if self._sem_tempo():
            return None
        try:
            r = get(url, timeout=30, tries=1, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
            final = _limpar_url(r.url) or url
            pag = ler_pagina(r.text, final) if "html" in (r.headers.get("content-type") or "html") else None
            if pag:
                pag["url"] = final
        except Exception as e:  # noqa: BLE001 - jornal fora do ar ou que recusa robô: pulamos essa notícia
            log.info("Notícia indisponível %s: %s", url, e)
            pag = None
        self._gravar(arq, {"pagina": pag})
        return pag

    def contra(self, it: dict) -> dict | None:
        """{"buscado_em": data, "noticias": [...]}, ou None se não deu tempo de procurar hoje."""
        sigla, numero, ano = it["sigla"], it["numero"], it["ano"]
        arq = self.pasta / f"b-{sigla}-{numero}-{ano}.json"
        c = self._ler_cache(arq, DIAS_BUSCA)
        if c is not None:
            return c["resultado"]
        if self._sem_tempo():
            self.faltaram += 1
            return None
        self.buscas += 1
        candidatos, responderam = self._achar(sigla, numero, ano)
        if not responderam:
            return None  # todas as buscas falharam: não dizemos "não achamos" sem ter procurado
        padrao = padrao_proposta(sigla, numero, ano)
        noticias, abertas = [], 0
        for cand in sorted(candidatos, key=lambda a: a.get("data") or "", reverse=True):
            if len(noticias) >= MAX_NOTICIAS or abertas >= MAX_ARTIGOS:
                break
            url = self.original(cand)
            if not url or any(n["url"] == url for n in noticias):
                continue
            abertas += 1
            pag = self.artigo(url)
            if not pag:
                continue
            texto = " ".join([pag.get("titulo") or ""] + pag.get("paragrafos", []))
            if not padrao.search(texto):
                continue  # a notícia não cita esta proposta pelo número: não usamos
            tr = trechos_contra(pag.get("paragrafos", []), pag.get("titulo") or "", padrao)
            if not tr or any(tr == n["trechos"] for n in noticias):
                continue
            noticias.append({k: v for k, v in {
                "veiculo": cand.get("veiculo") or pag.get("veiculo") or "", "titulo": pag.get("titulo") or cand.get("titulo") or "",
                "autor": pag.get("autor") or "", "data": pag.get("data") or cand.get("data") or "",
                "url": pag.get("url") or url, "quem": next((q for q in map(quem_fala, tr) if q), ""),
                "trechos": tr}.items() if v or k == "trechos"})
        self.achadas += len(noticias)
        res = {"buscado_em": self.hoje.isoformat(), "noticias": noticias}
        if not noticias and candidatos and self._sem_tempo():
            return None  # o tempo acabou no meio da leitura: procuramos de novo amanhã
        self._gravar(arq, {"resultado": res})
        return res
