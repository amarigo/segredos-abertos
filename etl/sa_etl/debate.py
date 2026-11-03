"""O que dizem a favor e contra cada projeto em andamento, só com documentos oficiais e com link para cada um.

De onde vem (API primeiro):
- Câmara (https://dadosabertos.camara.leg.br/api/v2): /proposicoes/{id}/relacionadas lista os pareceres dos relatores
  (PRL, PPP...) e os votos em separado (VTS); a ementa do parecer já diz quem é o relator e a conclusão ("pela
  aprovação", "pela rejeição"). /proposicoes/{id} dá o link do texto e /proposicoes/{id}/autores diz quem assinou o
  voto em separado.
- Senado (https://legis.senado.leg.br/dadosabertos): /processo/{id} lista, passo a passo, os relatórios, pareceres e
  votos em separado com o autor de cada um e a conclusão ("com voto pela aprovação").

Por que também lemos o PDF: as APIs dizem quem é e o que concluiu, mas não dizem o porquê nem o efeito esperado. Isso só
está no texto oficial (PDF): a justificação do autor, o voto do relator e o voto em separado de quem discorda. Desse
texto copiamos, sem trocar nenhuma palavra, até duas frases que falam do efeito da proposta e do motivo. Nada é escrito
por nós: cada trecho tem o link do documento de onde saiu. Quando nenhum documento oficial é contra, o site diz isso.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import time
from pathlib import Path

from .util import get, url_segura

log = logging.getLogger("sa_etl.debate")
logging.getLogger("pypdf").setLevel(logging.ERROR)  # avisos de fonte do PDF não interessam

VERSAO_CACHE = 3        # mude quando a forma de recortar a seção mudar (aí os PDFs são lidos de novo)
MAX_BYTES = 12_000_000  # PDF maior que isso é um calhamaço (reforma tributária...): não baixamos
MAX_PAGINAS = 60
MAX_SECAO = 20_000      # letras guardadas por documento
MAX_TRECHO = 420
MAX_FAVOR = 4
MAX_CONTRA = 3

# Conclusão do relator ou do voto em separado, como a Câmara e o Senado escrevem
_APROVA = r"aprova[çc][ãa]o|favor[áa]vel|acolhimento"
_REJEITA = r"rejei[çc][ãa]o|contr[áa]ri[oa]|arquivamento|desaprova[çc][ãa]o"
_CONCLUSAO = re.compile(rf"\bpel[ao]s?\s+({_APROVA}|{_REJEITA})|\bvoto\s+({_APROVA}|{_REJEITA})|\bparecer\s+({_APROVA}|{_REJEITA})", re.I)


_SO_EMENDAS = re.compile(r"^\W*(?:d[aoe]s?|[àa]s?|aos?)?\s*(?:dessas|destas|das|da|demais|todas as)?\s*(?:demais\s+)?emendas?\b", re.I)


def conclusao(texto: str, ultima: bool = False) -> str:
    """"aprovação", "rejeição" ou "" (quando o texto não diz, ou fala só de constitucionalidade ou só das emendas).

    Na ementa do parecer vale a primeira conclusão ("pela aprovação deste e pela rejeição do apensado"); no fim de um
    voto em separado vale a última ("Ante o exposto, votamos pela rejeição"). "Contrário às demais emendas" e
    "pela rejeição dessas emendas" falam das mudanças sugeridas, não da proposta, e não contam."""
    t = texto or ""
    ms = [m for m in _CONCLUSAO.finditer(t) if not _SO_EMENDAS.match(t[m.end(): m.end() + 40])]
    if not ms:
        return ""
    m = ms[-1] if ultima else ms[0]
    x = next(g for g in m.groups() if g)
    return "rejeição" if re.match(_REJEITA, x, re.I) else "aprovação"


# ---------------------------------------------------------------- texto do PDF

_LIXO = re.compile(
    r"Assinado eletronicamente|autenticidade|infoleg|^\*?CD\d{6,}\*?$|^Apresenta[çc][ãa]o:\s*\d|^(PL|PEC|PLP|PDL|MPV)\s*n\.|"
    r"^SF/\d|^\d{1,3}$|^P[áa]gina \d|^C[ÂA]MARA DOS DEPUTADOS$|^SENADO FEDERAL$|^Gabinete d|^Pra[çc]a dos Tr[êe]s Poderes|"
    r"^Anexo [IVX]+|^Ed\. Principal|^Telefone|^CEP\b|^Bras[íi]lia\s*-\s*DF|^Senado Federal\s*[-–]|^\(Do Sr|^\(Da Sra|"
    r"^Barcode|^\s*$|^[A-Z]{2,5}\s*n\.\s*\d+$|^[A-Z]{2,5}\s+\d+/\d+$", re.I)
_LIXO_MEIO = re.compile(r"\*CD\d{6,}\*|Apresenta[çc][ãa]o:\s*\d{2}/\d{2}/\d{4}[\d:. ]*-\s*[A-Z]+")


def limpar(texto: str) -> str:
    """Tira cabeçalhos, rodapés e assinaturas de página e junta as linhas quebradas do PDF."""
    linhas = [_LIXO_MEIO.sub(" ", l).strip() for l in (texto or "").splitlines()]
    linhas = [l for l in linhas if not _LIXO.search(l)]
    t = "\n".join(linhas)
    t = re.sub(r"(\w)-\n([a-zà-ú])", r"\1\2", t)  # palavra quebrada com hífen no fim da linha
    t = re.sub(r"\s*\n\s*", " ", t)
    return re.sub(r"\s{2,}", " ", t).strip()


_INICIO = {
    "justificativa": re.compile(r"\bJUSTIFICA[ÇC][ÃA]O\b|\bJUSTIFICATIVA\b|EXPOSI[ÇC][ÃA]O DE MOTIVOS"),
    "parecer": re.compile(r"\bII\s*[-–—.]\s*(?:VOTO|AN[ÁA]LISE)(?:\s+D[OA]S?\s+RELATOR(?:A|ES|AS)?)?\b|\bVOTO D[OA]S? RELATOR(?:A|ES|AS)?\b"),
    "voto_separado": re.compile(r"\bVOTO EM SEPARADO\b|\bII\s*[-–—.]\s*(?:VOTO|AN[ÁA]LISE)(?:\s+D[OA]S?\s+RELATOR(?:A|ES|AS)?)?\b", re.I),
}
_FIM = re.compile(r"\bSala d[ae]s? (?:Sess|Comiss|Reuni)|\bIII\s*[-–—.]\s*(?:VOTO|PARECER|CONCLUS)|\bIII\s*[-–—.]\s*DO VOTO")


def secao(texto: str, tipo: str) -> str:
    """A parte do documento que tem os argumentos: a justificação do autor ou o voto (análise) do relator."""
    t = texto or ""
    ms = list(_INICIO[tipo].finditer(t))
    if ms:
        # Na justificação vale o último título (o primeiro às vezes é o sumário); no parecer, o primeiro "II - VOTO"
        m = ms[-1] if tipo == "justificativa" else ms[0]
        t = t[m.end():]
    elif tipo != "voto_separado":
        return ""
    f = _FIM.search(t)
    if f:
        t = t[: f.start()]
    return t.strip(" .:-–—")[:MAX_SECAO]


def ler_pdf(raw: bytes) -> str:
    from pypdf import PdfReader  # só aqui: o resto da coleta não precisa da biblioteca

    r = PdfReader(io.BytesIO(raw))
    partes = []
    for p in r.pages[:MAX_PAGINAS]:
        try:
            partes.append(p.extract_text() or "")
        except Exception:  # noqa: BLE001 - uma página ruim não estraga o resto
            continue
    return "\n".join(partes)


# ---------------------------------------------------------------- frases

_ABREV = re.compile(r"\b(?:art|arts|inc|incs|Dep|Deps|Sr|Sra|Srs|Exa|Exmo|Exma|n|nº|Prof|Profa|Dr|Dra|Min|Sen|Cap|al|p|pp|fl|fls|v|ex)\.$", re.I)
_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[\"“(]?[A-ZÁÉÍÓÚÂÊÔÃÕÇ])")

_IMPACTO = re.compile(
    r"impact|efeit|consequ[êe]n|benef[íi]ci|garant|assegur|proteg|melhor|reduz|redu[çc]|aument|ampli|amplia|cust[oa]|"
    r"despesa|receita|arrecad|bilh|milh|R\$|%|por cento|emprego|renda|sal[áa]ri|pre[çc]o|popula[çc]|fam[íi]li|"
    r"trabalhador|cidad[ãa]o|consumidor|empresa|munic[íi]pio|estados|sa[úu]de|educa[çc]|escola|aluno|seguran[çc]a|"
    r"v[íi]tima|crian[çc]a|mulher|idos|direito|risco|preju[íi]z|prejudic|onera|inconstitucional|desequil[íi]br|"
    r"inseguran[çc]a|viola|distor[çc]|injust|desigualdade|precari|qualidade|acesso|valoriza", re.I)
_MOTIVO = re.compile(
    r"\bporque\b|\bpois\b|uma vez que|tendo em vista|\braz[ãa]o\b|\bmotivo|visto que|\bj[áa] que\b|dado que|"
    r"\bportanto\b|objetivo|finalidade|\bvisa\b|\bpermitir[áa]|possibilitar[áa]|evitar[áa]|\bpermite\b|\bevita\b|"
    r"necess[áa]ri|fundamental|urgente|indispens[áa]vel|import[âa]n", re.I)
_CITACAO = re.compile(r"\bart\.|\binciso\b|\bal[íi]nea\b|\bLei n[ºo°]|\bDecreto|\bRegimento|\bRICD\b|\bRISF\b|§", re.I)
_PROTOCOLO = re.compile(
    r"^(?:Ante|Diante|Pelo|Por todo|Em face|Em vista|Assim,? diante) (?:o|do|de todo o|de todo)? ?exposto|Sala d[ae]s|"
    r"Senhor(?:a)? Presidente|\brogo\b|contamos com|conto com|solicit\w+ o apoio|pedimos o apoio|apoio d[oa]s (?:nobres|ilustres|demais)|"
    r"aprova[çc][ãa]o (?:deste|desta|do presente) (?:projeto|proposi)|nobres pares|\bcompete (?:[àa]|a esta)|nos termos do art|"
    r"Regimento Interno|^(?:Cabe|Compete) a esta|[ée] o relat[óo]rio|^Vem (?:[àa]|a) (?:an[áa]lise|exame|esta)|^Trata-se d|"
    r"^O projeto (?:[ée] composto|possui|cont[ée]m)|^O art\. ?\d|^N[ãa]o foram apresentadas emendas|"
    r"constitucionalidade|juridicidade|t[ée]cnica legislativa|admissibilidade|adequa[çc][ãa]o (?:financeira|or[çc]ament)", re.I)


def frases(texto: str) -> list[str]:
    partes = _SPLIT.split(texto or "")
    out: list[str] = []
    for p in partes:
        if out and _ABREV.search(out[-1]):
            out[-1] = f"{out[-1]} {p}"
        else:
            out.append(p)
    return [f.strip() for f in out if f.strip()]


def _nota(f: str, i: int) -> float:
    if len(f) < 60 or _PROTOCOLO.search(f):
        return -1
    letras = [c for c in f if c.isalpha()]
    if letras and sum(c.isupper() for c in letras) > len(letras) / 2:
        return -1  # título ou tabela em maiúsculas, não frase
    n = 2 * len(_IMPACTO.findall(f)) + 1.5 * len(_MOTIVO.findall(f)) - 1.5 * len(_CITACAO.findall(f))
    if re.search(r"R\$\s?\d|\d+(?:,\d+)?\s?(?:%|por cento|bilh|milh)", f):
        n += 2
    if re.search(r"\bEmendas?\s*(?:n[ºo°]|de n|\d)", f):
        n -= 4  # o parecer descrevendo cada emenda não diz o efeito da proposta
    if i < 3:
        n += 1
    if len(f) > MAX_TRECHO:
        n -= 2  # frase comprida demais sai cortada: melhor uma mais curta, se houver
    if len(f) > 700:
        n -= 3
    return n


def _cortar(f: str) -> str:
    if len(f) <= MAX_TRECHO:
        return f
    corte = f[:MAX_TRECHO].rsplit(" ", 1)[0].rstrip(",;:")
    return corte + " […]"


def trechos(texto: str, n: int = 2) -> list[str]:
    """Até n frases copiadas do texto oficial, as que mais falam de efeito e de motivo, na ordem em que aparecem."""
    fs = frases(texto)
    notas = sorted(((_nota(f, i), i) for i, f in enumerate(fs)), key=lambda x: (-x[0], x[1]))
    escolhidas = sorted(i for nota, i in notas[:n] if nota >= 3)
    return [_cortar(fs[i]) for i in escolhidas]


# ---------------------------------------------------------------- download com cache

class Leitor:
    """Baixa e lê os PDFs, guardando a seção já recortada em cache/debate/. Documento oficial publicado não muda,
    então cada um é baixado uma vez só. Há um limite de tempo por coleta: o que faltar fica para o dia seguinte."""

    def __init__(self, cache: Path, minutos: float = 15, max_novos: int = 700):
        self.pasta = cache / "debate"
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.fim = time.monotonic() + minutos * 60
        self.novos = 0
        self.max_novos = max_novos
        self.faltaram = 0

    def _arq(self, url: str, tipo: str) -> Path:
        return self.pasta / f"{hashlib.sha1(f'{tipo}|{url}'.encode()).hexdigest()}.json"

    def ler(self, url: str, tipo: str) -> dict | None:
        """{"secao": texto, "conclusao": ...} ou None se não deu para ler agora."""
        # O Senado publica o mesmo documento nos dois endereços; o .leg.br é o que a API usa nos relatórios
        url = url_segura(url).replace("://legis.senado.gov.br/", "://legis.senado.leg.br/")
        if not url:
            return None
        arq = self._arq(url, tipo)
        if arq.exists():
            try:
                d = json.loads(arq.read_text(encoding="utf-8"))
                if d.get("v") == VERSAO_CACHE:
                    return d
            except ValueError:
                pass
        if time.monotonic() > self.fim or self.novos >= self.max_novos:
            self.faltaram += 1
            return None
        self.novos += 1
        try:
            r = get(url, timeout=60, tries=2, headers={"Accept": "application/pdf,*/*"})
        except Exception as e:  # noqa: BLE001 - sem o documento hoje, tenta amanhã
            log.info("Documento indisponível %s: %s", url, e)
            return None
        raw = r.content
        d = {"v": VERSAO_CACHE, "secao": "", "conclusao": ""}
        if raw[:5] == b"%PDF-" and len(raw) <= MAX_BYTES:
            try:
                texto = limpar(ler_pdf(raw))
                d["secao"] = secao(texto, tipo)
                d["conclusao"] = conclusao(texto[-3000:], ultima=True) if tipo != "justificativa" else ""
            except Exception as e:  # noqa: BLE001 - PDF quebrado: guardamos vazio para não baixar de novo todo dia
                log.info("PDF ilegível %s: %s", url, e)
        arq.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return d


# ---------------------------------------------------------------- montagem

def montar(docs: list[dict], leitor: Leitor) -> dict | None:
    """Junta os documentos de uma proposta em {"favor": [...], "contra": [...]}.

    Cada documento chega como {"tipo": "justificativa"|"parecer"|"voto_separado", "quem", "papel", "casa", "data",
    "url", "conclusao"}. Justificação do autor conta a favor. Parecer e voto em separado contam pelo que concluem;
    os que falam só de constitucionalidade ou de orçamento, sem dizer se a ideia é boa ou ruim, ficam de fora."""
    if not docs:
        return None
    favor, contra, lidos = [], [], 0
    vistos: set[str] = set()
    for d in docs:
        url = url_segura(d.get("url"))
        if not url or url in vistos:
            continue
        vistos.add(url)
        lido = leitor.ler(url, d["tipo"])
        if lido is None:
            continue
        lidos += 1
        concl = d.get("conclusao") or lido.get("conclusao") or ""
        if d["tipo"] == "justificativa":
            lado = favor
        elif concl == "aprovação":
            lado = favor
        elif concl == "rejeição":
            lado = contra
        else:
            continue
        tr = trechos(lido.get("secao") or "")
        if d["tipo"] == "justificativa" and not tr:
            continue  # sem justificação legível não há o que mostrar
        if tr and any(tr == x["trechos"] for x in favor + contra):
            continue  # o mesmo parecer publicado duas vezes (proferido e reformulado)
        lado.append({k: v for k, v in {
            "quem": d.get("quem") or "", "papel": d.get("papel") or "", "casa": d.get("casa") or "",
            "data": (d.get("data") or "")[:10], "url": url, "conclusao": concl if d["tipo"] != "justificativa" else "",
            "trechos": tr}.items() if v or k == "trechos"})
    if not lidos:
        return None
    return {"favor": favor[:MAX_FAVOR], "contra": contra[:MAX_CONTRA], "documentos": lidos}
