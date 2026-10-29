"""Projetos em andamento na Câmara e no Senado: o que está na pauta dos próximos dias, o que acabou de ser
apresentado e as medidas provisórias que ainda esperam votação.

Tudo pelas APIs oficiais:
- Câmara (https://dadosabertos.camara.leg.br/api/v2): /eventos (reuniões e sessões marcadas), /eventos/{id}/pauta
  (o que vai ser votado), /proposicoes (apresentadas no período e medidas provisórias), /proposicoes/{id} (situação
  atual), /proposicoes/{id}/autores e /proposicoes/{id}/tramitacoes (últimos passos).
- Senado (https://legis.senado.leg.br/dadosabertos): /plenario/agenda/mes/{data} (sessões do Plenário com as
  matérias), /comissao/agenda/{inicio}/{fim} (reuniões das comissões com os itens da pauta) e /processo (autoria,
  situação atual e apresentadas no período).

O resumo em linguagem simples é feito por regras públicas (resumo_simples): troca o número da lei pelo nome
pelo qual ela é conhecida e o juridiquês mais comum por palavras do dia a dia. A ementa oficial aparece sempre ao
lado, e o link leva à página oficial.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .temas import temas_de
from .util import avisar, get_json, id_seguro, norm_name, url_segura, write_json

log = logging.getLogger("sa_etl.tramitacao")

CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
SENADO = "https://legis.senado.leg.br/dadosabertos"
PAGINA_CAMARA = "https://www.camara.leg.br/propostas-legislativas/{id}"
EVENTO_CAMARA = "https://www.camara.leg.br/evento-legislativo/{id}"
PAGINA_SENADO = "https://www25.senado.leg.br/web/atividade/materias/-/materia/{cod}"
REUNIAO_SENADO = "https://legis.senado.leg.br/comissoes/reuniao?reuniao={cod}"

TIPOS = ("PEC", "PLP", "PL", "MPV", "PDL")  # as propostas que viram regra para todo mundo
DIAS_PAUTA = 14  # quanto à frente olhar a agenda
DIAS_NOVAS = 14  # "apresentadas nos últimos N dias"
MAX_AUTORES = 6
PARALELO = 6  # consultas ao mesmo tempo (as APIs aguentam bem; mais que isso começa a dar 429)

O_QUE_E = {
    "PEC": "Proposta de Emenda à Constituição: muda a Constituição. Precisa de 3/5 dos votos (308 deputados e 49 "
           "senadores) em dois turnos em cada Casa. Não passa pelo presidente: é promulgada pelo Congresso.",
    "PLP": "Projeto de Lei Complementar: regula pontos que a Constituição manda tratar por lei complementar. Precisa "
           "da maioria absoluta (257 deputados e 41 senadores) e depois vai para o presidente sancionar ou vetar.",
    "PL": "Projeto de Lei: cria ou muda uma lei. Passa pela Câmara e pelo Senado e depois vai para o presidente "
          "sancionar (virar lei) ou vetar.",
    "MPV": "Medida Provisória: o presidente edita e ela já vale como lei, mas o Congresso tem até 120 dias (sem contar "
           "o recesso) para aprovar. Se não votar a tempo, ela perde a validade.",
    "PDL": "Projeto de Decreto Legislativo: decisão só do Congresso, sem sanção do presidente. Serve, por exemplo, "
           "para suspender um ato do governo ou aprovar um acordo internacional.",
}

ETAPAS = ["Apresentada", "Comissões", "Plenário", "Outra Casa", "Sanção ou promulgação"]

# Leis que as pessoas conhecem pelo nome, não pelo número
LEIS = {
    ("lei", "9504", "1997"): "a Lei das Eleições", ("lei", "4737", "1965"): "o Código Eleitoral",
    ("lei", "9096", "1995"): "a Lei dos Partidos Políticos", ("lei complementar", "64", "1990"): "a Lei de Inelegibilidade (Ficha Limpa)",
    ("lei", "8069", "1990"): "o Estatuto da Criança e do Adolescente (ECA)", ("lei", "10406", "2002"): "o Código Civil",
    ("decreto-lei", "2848", "1940"): "o Código Penal", ("decreto-lei", "3689", "1941"): "o Código de Processo Penal",
    ("decreto-lei", "5452", "1943"): "a CLT (leis do trabalho)", ("lei", "13105", "2015"): "o Código de Processo Civil",
    ("lei", "8078", "1990"): "o Código de Defesa do Consumidor", ("lei", "9503", "1997"): "o Código de Trânsito",
    ("lei", "8213", "1991"): "a lei dos benefícios do INSS", ("lei", "8212", "1991"): "a lei de custeio da Previdência",
    ("lei", "9394", "1996"): "a Lei de Diretrizes e Bases da Educação (LDB)", ("lei", "11340", "2006"): "a Lei Maria da Penha",
    ("lei", "8080", "1990"): "a Lei Orgânica da Saúde (SUS)", ("lei", "10741", "2003"): "o Estatuto da Pessoa Idosa",
    ("lei", "13146", "2015"): "o Estatuto da Pessoa com Deficiência", ("lei", "8112", "1990"): "o estatuto dos servidores federais",
    ("lei", "11343", "2006"): "a Lei de Drogas", ("lei", "10826", "2003"): "o Estatuto do Desarmamento",
    ("lei", "12764", "2012"): "a lei do autismo (Lei Berenice Piana)", ("lei", "13709", "2018"): "a LGPD (proteção de dados)",
    ("lei", "14133", "2021"): "a Lei de Licitações", ("lei", "5172", "1966"): "o Código Tributário Nacional",
    ("lei", "12965", "2014"): "o Marco Civil da Internet", ("lei", "7210", "1984"): "a Lei de Execução Penal",
    ("lei", "9605", "1998"): "a Lei de Crimes Ambientais", ("lei", "12651", "2012"): "o Código Florestal",
    ("lei", "8429", "1992"): "a Lei de Improbidade Administrativa", ("lei", "8742", "1993"): "a Lei da Assistência Social (LOAS)",
    ("lei", "8072", "1990"): "a Lei de Crimes Hediondos", ("lei", "9099", "1995"): "a lei dos Juizados Especiais",
    ("lei complementar", "123", "2006"): "o Estatuto da Micro e Pequena Empresa (Simples)",
    ("lei complementar", "101", "2000"): "a Lei de Responsabilidade Fiscal", ("lei", "8987", "1995"): "a Lei de Concessões",
    ("lei", "8629", "1993"): "a Lei da Reforma Agrária", ("lei", "9433", "1997"): "a Lei das Águas",
    ("lei", "11079", "2004"): "a lei das Parcerias Público-Privadas (PPP)", ("lei", "12846", "2013"): "a Lei Anticorrupção",
    ("lei", "12527", "2011"): "a Lei de Acesso à Informação", ("lei", "13460", "2017"): "o Código de Defesa do Usuário do Serviço Público",
    ("lei", "6015", "1973"): "a Lei de Registros Públicos", ("lei", "9472", "1997"): "a Lei Geral de Telecomunicações",
    ("lei", "13675", "2018"): "a lei do Sistema Único de Segurança Pública (Susp)", ("lei", "14230", "2021"): "a nova Lei de Improbidade",
}

_LEI = re.compile(r"(?P<tipo>Lei Complementar|Decreto-Lei|Lei)\s+n[ºo°.]*\s*(?P<num>[\d.]+),?\s+de\s+"
                  r"(?:\d{1,2}[º°]?\s+de\s+\w+\s+de\s+)?(?P<ano>\d{4})(?:\s*[-–(]\s*(?P<apelido>[^,;)]{3,80}?)\)?(?=[,;.]|\s+para|\s+a fim|$))?", re.I)
_TROCAS = [
    (r"^Altera\b", "Muda"), (r"^Acrescenta\b", "Inclui"), (r"^Revoga\b", "Cancela"), (r"^Institui\b", "Cria"),
    (r"^Dispõe sobre\b", "Trata de"), (r"^Autoriza\b", "Permite"), (r"^Susta\b", "Suspende"),
    (r"^Abre ao Orçamento Fiscal da União.*?crédito extraordinário", "Libera dinheiro extra no Orçamento"),
    (r"^Abre crédito extraordinário", "Libera dinheiro extra no Orçamento (crédito extraordinário)"),
    (r",? para o fim que especifica", ""), (r",? nos termos que especifica", ""),
    (r"^Aprova o texto do\b", "Aprova o"),
    (r"\bpara dispor sobre\b", "para tratar de"), (r"\bdispor sobre\b", "tratar de"), (r"\bdispõe sobre\b", "trata de"),
    (r"\ba fim de\b", "para"), (r"\bdá outras providências\b", "outras mudanças"), (r"\be outras providências\b", ""),
    (r"\bno âmbito do\b", "no"), (r"\bno âmbito da\b", "na"), (r"\btipificar\b", "tornar crime"), (r"\bmajorar\b", "aumentar"),
    (r"\bvedar\b", "proibir"), (r"\bveda\b", "proíbe"), (r"\bensejar\b", "causar"),
]
def _num(s: str) -> str:
    return s.replace(".", "").lstrip("0") or "0"


def resumo_simples(ementa: str) -> str:
    """A ementa oficial em palavras do dia a dia. Devolve "" quando nada mudou (aí o site mostra só a ementa)."""
    e = re.sub(r"\s+", " ", ementa or "").strip()
    if not e:
        return ""
    orig = e

    def lei(m: re.Match) -> str:
        chave = (m["tipo"].lower(), _num(m["num"]), m["ano"])
        nome = LEIS.get(chave)
        if nome:
            return nome
        if m["apelido"]:
            return "a " + m["apelido"].strip() if not m["apelido"].strip().lower().startswith(("o ", "a ")) else m["apelido"].strip()
        return f"{m['tipo']} {m['num']}/{m['ano']}"

    e = _LEI.sub(lei, e)
    e = re.sub(r"\b(a|o)\s+(a|o)\s+", r"\2 ", e)  # "Altera a a Lei das Eleições" -> "Altera a Lei..."
    e = re.sub(r"\bd(a|o)\s+(a|o)\s+", lambda m: "d" + m[2] + " ", e)
    e = re.sub(r"\b(?:Altera|Acrescenta)\b[^.;]*?(?:art(?:igo)?s?\.?\s*[\d.ºo°, e-]+)?\s*(?:da|à)\s+Constituição Federal",
               "Muda a Constituição", e, count=1)
    for de, para in _TROCAS:
        e = re.sub(de, para, e, count=1, flags=re.I)
    e = re.sub(r"\b([Tt]ratar?|[Tt]rata) de (o|a|os|as)\b", r"\1 d\2", e)
    e = re.sub(r"\s+,", ",", e).strip().rstrip(",;")
    e = re.sub(r"\s{2,}", " ", e)
    if e and not e.endswith("."):
        e += "."
    return "" if e.rstrip(".") == orig.rstrip(".") else e[:1].upper() + e[1:]


# ---------------------------------------------------------------- etapa e próximo passo

def etapa_camara(status: dict) -> int:
    s = (status.get("descricaoSituacao") or "").lower()
    org = (status.get("siglaOrgao") or "").upper()
    if re.search(r"san[çc][ãa]o|promulga", s):
        return 4
    if re.search(r"senado|remetid[ao] ao", s) or org in ("SF", "CN"):
        return 3
    if re.search(r"despacho|recebimento|apresenta[çc][ãa]o|leitura", s) or org in ("MESA", ""):
        return 0
    if org == "PLEN":
        return 2
    return 1


def etapa_senado(situacao: str, revisora: bool) -> int:
    s = (situacao or "").upper()
    if re.search(r"SAN[ÇC][ÃA]O|PROMULGA", s):
        return 4
    if re.search(r"REMETIDA À CÂMARA|REMETIDA A CÂMARA|CÂMARA DOS DEPUTADOS", s):
        return 3
    if revisora:
        return 3
    if re.search(r"PAUTA NO PLEN|ORDEM DO DIA|PLENÁRIO", s):
        return 2
    if re.search(r"AGUARDANDO (DESPACHO|LEITURA)|PROTOCOLAD|APRESENTAD", s):
        return 0
    return 1


PASSOS = [  # (expressão na situação oficial, explicação do próximo passo)
    (r"designa[çc][ãa]o de relator", "A comissão precisa escolher um relator, o parlamentar que estuda a proposta e recomenda aprovar ou rejeitar."),
    (r"parecer|relatoria|com a relatoria|relator", "O relator está preparando o parecer. Depois a comissão vota esse parecer."),
    (r"pronta para (a )?pauta", "Já pode ser votada. Falta o presidente {onde} colocá-la na pauta."),
    (r"inclu[ií]da em ordem do dia|aguardando delibera[çc][ãa]o|aguardando vota[çc][ãa]o", "Espera a votação {onde}."),
    (r"aguardando (autoriza[çc][ãa]o do )?despacho|aguardando leitura|recebimento",
     "O presidente da Casa vai decidir por quais comissões a proposta passa."),
    (r"aguardando san[çc][ãa]o|remetida [àa] san[çc][ãa]o", "Foi aprovada. O presidente da República tem 15 dias úteis para sancionar (virar lei) ou vetar."),
    (r"audi[êe]ncia p[úu]blica", "A comissão está ouvindo especialistas e a sociedade antes de votar."),
    (r"aguardando (cria[çc][ãa]o|instala[çc][ãa]o) de comiss[ãa]o", "Espera a criação da comissão que vai analisar a proposta."),
    (r"apensad[ao]", "Foi juntada a outra proposta parecida e anda junto com ela."),
    (r"aguardando emendas|prazo para emendas|abertura de prazo", "Está aberto o prazo para os parlamentares sugerirem mudanças (emendas)."),
]


def proximo_passo(it: dict) -> str:
    p = it.get("pauta") or []
    if p:
        x = p[0]
        quando = data_hora_br(x["data"])
        if x.get("urgencia"):
            return f"{x['onde']} vota em {quando} um pedido de urgência para esta proposta: se aprovado, ela pode ir direto ao Plenário, sem esperar as comissões."
        return f"Está na pauta {de_onde(x['onde'])} em {quando}: pode ser votada nesse dia (a pauta pode mudar)."
    s = (it.get("situacao") or "")
    onde = de_onde(it.get("onde") or "")
    for rx, txt in PASSOS:
        if re.search(rx, s, re.I):
            return txt.format(onde=onde or "da comissão")
    if it.get("sigla") == "MPV":
        if it.get("suspenso"):
            return "O prazo para votar está suspenso por decisão do Congresso. Enquanto isso, a medida continua valendo."
        if it.get("prazo"):
            return (f"O Congresso tem até {data_hora_br(it['prazo'])}/{it['prazo'][:4]} para aprovar na Câmara e no Senado. "
                    "Se não votar até lá, a medida perde a validade.")
        return "Precisa ser aprovada pela Câmara e pelo Senado antes do prazo, senão perde a validade."
    return f"Situação oficial: {s.strip().rstrip('.').capitalize()}." if s.strip() else ""


def de_onde(orgao: str) -> str:
    o = (orgao or "").strip()
    if not o:
        return ""
    if o.lower().startswith(("plenário", "plenario")):
        return "do " + o
    if o.lower().startswith("comissão") or o.lower().startswith("comissao"):
        return "da " + o
    return "de " + o


def data_hora_br(s: str) -> str:
    d = (s or "")[:10]
    h = (s or "")[11:16]
    try:
        x = dt.date.fromisoformat(d)
    except ValueError:
        return s or ""
    dias = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    txt = f"{dias[x.weekday()]}, {x.day:02d}/{x.month:02d}"
    return txt + (f", às {h.replace(':', 'h')}" if h and h != "00:00" else "")


# ---------------------------------------------------------------- consultas

def _dados(url: str, params: dict | None = None) -> list:
    d = get_json(url, params=params, timeout=60)
    return d.get("dados", []) if isinstance(d, dict) else []


def _paginas(url: str, params: dict) -> list:
    out, pagina = [], 1
    while pagina <= 30:
        d = get_json(url, params={**params, "pagina": pagina, "itens": 100}, timeout=60)
        out += d.get("dados", [])
        if not any(l.get("rel") == "next" for l in d.get("links", [])):
            break
        pagina += 1
    return out


def _em_paralelo(fn, itens: list) -> list:
    with ThreadPoolExecutor(PARALELO) as ex:
        return list(ex.map(fn, itens))


# ---------------------------------------------------------------- Câmara

def _id_camara(uri: str) -> str:
    m = re.search(r"/(\d+)$", uri or "")
    return m.group(1) if m else ""


def pauta_camara(hoje: dt.date) -> tuple[list[dict], dict[str, list[dict]]]:
    """Reuniões deliberativas e sessões marcadas, e para cada proposta da pauta: onde e quando."""
    fim = hoje + dt.timedelta(days=DIAS_PAUTA)
    eventos = _paginas(f"{CAMARA}/eventos", {"dataInicio": hoje.isoformat(), "dataFim": fim.isoformat()})
    eventos = [e for e in eventos if "deliberativ" in (e.get("descricaoTipo") or "").lower()
               and "não deliberativ" not in (e.get("descricaoTipo") or "").lower()
               and not re.search(r"cancelad|encerrad", e.get("situacao") or "", re.I) and id_seguro(e.get("id"))]

    def pauta(e):
        try:
            return e, _dados(f"{CAMARA}/eventos/{e['id']}/pauta")
        except Exception as x:  # noqa: BLE001 - uma pauta faltando não derruba as outras
            log.warning("Câmara: pauta do evento %s indisponível: %s", e.get("id"), x)
            return e, []

    agenda, por_prop = [], {}
    for e, itens in _em_paralelo(pauta, eventos):
        orgaos = e.get("orgaos") or [{}]
        o = orgaos[0]
        onde = "Plenário da Câmara" if o.get("sigla") == "PLEN" else (o.get("nomePublicacao") or o.get("nome") or o.get("sigla") or "")
        if o.get("sigla") and onde:
            _ORGAOS.setdefault(o["sigla"], onde)
        ev = {"id": f"cd-ev-{e['id']}", "casa": "camara", "data": e.get("dataHoraInicio") or "", "onde": onde,
              "tipo": e.get("descricaoTipo") or "", "situacao": e.get("situacao") or "",
              "url": EVENTO_CAMARA.format(id=e["id"]), "itens": []}
        for it in itens:
            p = it.get("proposicao_") or {}
            urg = False
            if p.get("siglaTipo") == "REQ" and it.get("proposicaoRelacionada_"):
                p, urg = it["proposicaoRelacionada_"], True
            if p.get("siglaTipo") not in TIPOS or not str(p.get("id") or "").isdigit():
                continue
            pid = f"cd-{p['id']}"
            rel = it.get("relator") or {}
            x = {"data": ev["data"], "onde": onde, "url": ev["url"], "urgencia": urg, "regime": it.get("regime") or "",
                 "relator": f"{rel['nome']} ({rel.get('siglaPartido', '')}-{rel.get('siglaUf', '')})" if rel.get("nome") else ""}
            por_prop.setdefault(pid, []).append(x)
            if pid not in ev["itens"]:
                ev["itens"].append(pid)
        if ev["itens"]:
            agenda.append(ev)
    return agenda, por_prop


def novas_camara(hoje: dt.date) -> list[str]:
    ini = hoje - dt.timedelta(days=DIAS_NOVAS)
    ps = _paginas(f"{CAMARA}/proposicoes", {"siglaTipo": ",".join(TIPOS), "dataApresentacaoInicio": ini.isoformat(),
                                             "dataApresentacaoFim": hoje.isoformat(), "ordem": "DESC", "ordenarPor": "id"})
    return [str(p["id"]) for p in ps if str(p.get("id", "")).isdigit() and p.get("siglaTipo") in TIPOS]


FINAL = re.compile(r"finalizad|transformad|arquivad|perdeu|encerrad|vetad|rejeitad|prejudicad|retirad|devolvid|sem efic", re.I)


_DATA_BR = r"(\d{1,2})/(\d{1,2})/(\d{4})"


def _iso(m: re.Match) -> str:
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"


def prazo_mpv(tram: list[dict]) -> dict:
    """Prazo da medida provisória como a Câmara registra nos passos: "Congresso Nacional: 11/09/2026 a 09/11/2026",
    "Data final após prorrogação: 10/12/2026" e "Sobrestar Pauta: a partir de 26/10/2026"."""
    out: dict = {}
    for t in sorted(tram, key=lambda t: (t.get("dataHora") or "", t.get("sequencia") or 0)):
        x = t.get("despacho") or ""
        m = re.search(r"Congresso Nacional:\s*" + _DATA_BR + r"\s*a\s*" + _DATA_BR, x)
        if m:
            out["prazo"] = f"{m.group(6)}-{int(m.group(5)):02d}-{int(m.group(4)):02d}"
            out["suspenso"] = False
        m = re.search(r"Data final após prorrogação:\s*" + _DATA_BR, x, re.I)
        if m:
            out["prazo"], out["suspenso"] = _iso(m), False
        m = re.search(r"Sobrestar Pauta:\s*a partir de\s*" + _DATA_BR, x, re.I)
        if m:
            out["tranca_pauta"] = _iso(m)
        if re.search(r"prazos.{0,40}ficar[ãa]o suspensos|vig[êe]ncia.{0,40}suspens", x, re.I):
            out["suspenso"] = True
    return out


def mpvs_camara(hoje: dt.date) -> list[str]:
    ids = []
    for ano in (hoje.year - 1, hoje.year):
        for p in _paginas(f"{CAMARA}/proposicoes", {"siglaTipo": "MPV", "ano": ano}):
            if str(p.get("id", "")).isdigit():
                ids.append(str(p["id"]))
    return ids


_ORGAOS: dict[str, str] = {"PLEN": "Plenário da Câmara"}


def nome_orgao(sigla: str) -> str:
    """Nome da comissão pela sigla (a situação da proposta traz só a sigla, como CCJC)."""
    sigla = (sigla or "").strip()
    if not sigla or sigla in _ORGAOS:
        return _ORGAOS.get(sigla, "")
    try:
        os_ = _dados(f"{CAMARA}/orgaos", {"sigla": sigla})
        nome = next((o.get("nomePublicacao") or o.get("nome") for o in os_ if o.get("sigla") == sigla), "") or sigla
    except Exception:  # noqa: BLE001
        nome = sigla
    _ORGAOS[sigla] = nome
    return nome


def detalhe_camara(pid: str, deputados: dict[str, dict], hoje: dt.date | None = None) -> dict | None:
    d = get_json(f"{CAMARA}/proposicoes/{pid}", timeout=60).get("dados") or {}
    if d.get("siglaTipo") not in TIPOS:
        return None
    st = d.get("statusProposicao") or {}
    try:
        autores = _dados(f"{CAMARA}/proposicoes/{pid}/autores")
    except Exception:  # noqa: BLE001
        autores = []
    try:
        tram = _dados(f"{CAMARA}/proposicoes/{pid}/tramitacoes")
    except Exception:  # noqa: BLE001
        tram = []
    lista = []
    for a in sorted(autores, key=lambda a: (-(a.get("proponente") or 0), a.get("ordemAssinatura") or 999)):
        nome = (a.get("nome") or "").strip()
        dep = _id_camara(a.get("uri") or "") if "/deputados/" in (a.get("uri") or "") else ""
        pol = deputados.get(f"dep-{dep}") if dep else None
        lista.append({"nome": pol["nome"] if pol else nome, "partido": pol.get("partido", "") if pol else "",
                      "uf": pol.get("uf", "") if pol else "", "id": f"dep-{dep}" if pol else ""})
    org = st.get("siglaOrgao") or ""
    passos = [{"data": (t.get("dataHora") or "")[:10], "onde": t.get("siglaOrgao") or "",
               "texto": (t.get("despacho") or t.get("descricaoTramitacao") or "").strip()[:300]}
              for t in tram[-5:]][::-1]
    final = bool(FINAL.search(st.get("descricaoSituacao") or ""))
    extra = {}
    if d["siglaTipo"] == "MPV":
        extra = prazo_mpv(tram)
        hoje = hoje or dt.date.today()
        if extra.get("prazo") and extra["prazo"] < hoje.isoformat() and not extra.get("suspenso"):
            final = True  # o prazo acabou: a MP perdeu a validade ou já foi votada
    return {
        **extra,
        "id": f"cd-{pid}", "casa": "camara", "sigla": d["siglaTipo"], "numero": str(d.get("numero") or ""),
        "ano": str(d.get("ano") or ""), "ementa": (d.get("ementa") or "").strip(),
        "apresentada": (d.get("dataApresentacao") or "")[:10],
        "autores": lista[:MAX_AUTORES], "n_autores": len(lista),
        "situacao": (st.get("descricaoSituacao") or "").strip(), "atualizada": (st.get("dataHora") or "")[:10],
        "onde": nome_orgao(org) if etapa_camara(st) in (1, 2) else "", "etapa": etapa_camara(st),
        "regime": (st.get("regime") or "").strip(" ."), "url": PAGINA_CAMARA.format(id=pid),
        "texto": url_segura(d.get("urlInteiroTeor")), "passos": passos,
        "final": final,
    }


def juntar_pauta(xs: list[dict]) -> list[dict]:
    """Uma linha por reunião. Quando a proposta e o pedido de urgência dela estão na mesma sessão, vale a proposta."""
    por: dict[tuple, dict] = {}
    for x in sorted(xs, key=lambda x: x["data"]):
        k = (x["data"], x["onde"])
        if k in por:
            por[k]["urgencia"] = por[k]["urgencia"] and x["urgencia"]
            por[k]["relator"] = por[k]["relator"] or x["relator"]
        else:
            por[k] = dict(x)
    return list(por.values())


def camara(hoje: dt.date, deputados: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    agenda, por_prop = pauta_camara(hoje)
    novas = set(novas_camara(hoje))
    mpvs = set(mpvs_camara(hoje))
    ids = sorted({p[3:] for p in por_prop} | novas | mpvs, key=int, reverse=True)

    def det(pid):
        try:
            return detalhe_camara(pid, deputados, hoje)
        except Exception as e:  # noqa: BLE001
            log.warning("Câmara: proposição %s indisponível: %s", pid, e)
            return None

    itens = []
    for it in _em_paralelo(det, ids):
        if not it:
            continue
        pid = it["id"][3:]
        grupos = []
        if it["id"] in por_prop:
            it["pauta"] = juntar_pauta(por_prop[it["id"]])
            grupos.append("pauta")
            em_plen = any(x["onde"].startswith("Plenário") and not x["urgencia"] for x in it["pauta"])
            it["etapa"] = max(it["etapa"], 2 if em_plen else 1)
        if pid in novas:
            grupos.append("nova")
        if pid in mpvs and not it["final"]:
            grupos.append("mpv")
        if not grupos:
            continue
        it["grupos"] = grupos
        itens.append(it)
    log.info("Câmara: %d propostas acompanhadas, %d reuniões com pauta", len(itens), len(agenda))
    return itens, agenda


# ---------------------------------------------------------------- Senado

_IDENT = re.compile(r"^\s*([A-Z]+)\s+(\d+)/(\d{4})")


def _lista(x) -> list:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _autores_texto(autoria: str, senadores: dict[str, str], todos: dict[str, dict]) -> tuple[list[dict], int]:
    partes = [p.strip() for p in re.split(r",\s*(?=(?:Senador|Senadora|Deputad|Comiss|Presid|Poder|Câmara|CPI|Mesa))", autoria or "") if p.strip()]
    out = []
    for p in partes:
        m = re.match(r"^(?:Senadora?|Deputad[oa](?: Federal)?)\s+(.+?)\s*\(([^/)]*)/([A-Z]{2})\)\s*$", p)
        if m:
            nome, partido, uf = m.group(1), m.group(2), m.group(3)
            pid = senadores.get(norm_name(nome)) or senadores.get(norm_name(p.split("(")[0])) or ""
            pol = todos.get(pid) if pid else None
            out.append({"nome": pol["nome"] if pol else nome, "partido": partido if partido != "S" else "",
                        "uf": uf, "id": pid if pol else ""})
        else:
            out.append({"nome": p, "partido": "", "uf": "", "id": ""})
    return out[:MAX_AUTORES], len(out)


def pauta_senado(hoje: dt.date) -> tuple[list[dict], dict[tuple, list[dict]]]:
    fim = hoje + dt.timedelta(days=DIAS_PAUTA)
    agenda, por_prop = [], {}

    def guarda(chave, x, ev):
        por_prop.setdefault(chave, []).append(x)
        k = "-".join(chave)
        if k not in ev["itens"]:
            ev["itens"].append(k)

    meses = {hoje.replace(day=1)}
    meses.add(fim.replace(day=1))
    for m in sorted(meses):
        ini = max(m, hoje)
        d = get_json(f"{SENADO}/plenario/agenda/mes/{ini:%Y%m%d}", timeout=60)
        sessoes = _lista(((d.get("AgendaPlenario") or {}).get("Sessoes") or {}).get("Sessao"))
        for s in sessoes:
            data = (s.get("Data") or "")[:10]
            if not data or not (hoje.isoformat() <= data <= fim.isoformat()):
                continue
            if "DELIBERATIVA" not in (s.get("TipoSessao") or "").upper() or "NÃO" in (s.get("TipoSessao") or "").upper():
                continue
            casa_s = "Plenário do Congresso" if s.get("Casa") == "CN" else "Plenário do Senado"
            hora = (s.get("Hora") or "").strip()
            ev = {"id": f"sf-ses-{id_seguro(s.get('CodigoSessao')) or data}", "casa": "senado",
                  "data": f"{data}T{hora}" if hora else data, "onde": casa_s, "tipo": (s.get("TipoSessao") or "").strip().capitalize(),
                  "situacao": (s.get("SituacaoSessao") or "").strip(), "url": "", "itens": []}
            for mt in _lista((s.get("Materias") or {}).get("Materia")):
                sig = (mt.get("SiglaMateria") or "").upper()
                if sig not in TIPOS:
                    continue
                chave = (sig, str(int(mt.get("NumeroMateria") or 0)), str(mt.get("AnoMateria") or ""))
                guarda(chave, {"data": ev["data"], "onde": casa_s, "url": "", "urgencia": False,
                                   "relator": "", "regime": (mt.get("Apreciacao") or "").strip(" -"),
                                   "parecer": (mt.get("Parecer") or "").strip()[:400], "codigo": mt.get("CodigoMateria")}, ev)
            if ev["itens"]:
                agenda.append(ev)

    d = get_json(f"{SENADO}/comissao/agenda/{hoje:%Y%m%d}/{fim:%Y%m%d}", timeout=60)
    for r in _lista(((d.get("AgendaReuniao") or {}).get("reunioes") or {}).get("reuniao")):
        if re.search(r"cancelad|realizad|encerrad", r.get("situacao") or "", re.I) or not id_seguro(r.get("codigo")):
            continue
        col = r.get("colegiadoCriador") or {}
        onde = col.get("nome") or col.get("sigla") or ""
        ev = {"id": f"sf-reu-{r['codigo']}", "casa": "senado", "data": (r.get("dataInicio") or "")[:16], "onde": onde,
              "tipo": (r.get("titulo") or "").strip(), "situacao": r.get("situacao") or "",
              "url": REUNIAO_SENADO.format(cod=r["codigo"]), "itens": []}
        for parte in _lista(r.get("partes")):
            if not isinstance(parte, dict) or parte.get("isDeliberativa") != "true":
                continue
            for it in _lista(parte.get("itens")):
                m = _IDENT.match(it.get("nome") or "")
                if not m or m.group(1) not in TIPOS:
                    continue
                guarda((m.group(1), str(int(m.group(2))), m.group(3)), {
                    "data": ev["data"], "onde": onde, "url": ev["url"], "urgencia": False, "regime": "",
                    "relator": "", "parecer": (it.get("relatorio") or "").strip()[:400],
                    "terminativo": it.get("isTerminativo") == "true"}, ev)
        if ev["itens"]:
            agenda.append(ev)
    return agenda, por_prop


def _item_senado(p: dict, senadores: dict[str, str], todos: dict[str, dict]) -> dict | None:
    m = _IDENT.match(p.get("identificacao") or "")
    if not m or m.group(1) not in TIPOS or not str(p.get("codigoMateria") or "").isdigit():
        return None
    autores, n = _autores_texto(p.get("autoria") or "", senadores, todos)
    revisora = (p.get("objetivo") or "").lower().startswith("revisora")
    sit = (p.get("situacaoAtual") or "").strip()
    return {
        "id": f"sf-{p['codigoMateria']}", "casa": "senado", "sigla": m.group(1), "numero": str(int(m.group(2))),
        "ano": m.group(3), "ementa": (p.get("ementa") or "").strip(), "apresentada": (p.get("dataApresentacao") or "")[:10],
        "autores": autores, "n_autores": n, "situacao": sit.capitalize(), "atualizada": (p.get("dataSituacaoAtual") or "")[:10],
        "onde": "", "etapa": etapa_senado(sit, revisora), "regime": "", "veio_da_camara": revisora,
        "url": PAGINA_SENADO.format(cod=p["codigoMateria"]), "texto": url_segura(p.get("urlDocumento")), "passos": [],
        "final": (p.get("tramitando") or "").lower().startswith("n") or bool(FINAL.search(sit)),
    }


def senado(hoje: dt.date, politicos: list[dict]) -> tuple[list[dict], list[dict]]:
    todos = {p["id"]: p for p in politicos}
    senadores = {norm_name(p["nome"]): p["id"] for p in politicos if p.get("casa") == "senado"}
    agenda, por_prop = pauta_senado(hoje)
    ini = hoje - dt.timedelta(days=DIAS_NOVAS)
    novas = get_json(f"{SENADO}/processo", params={"dataInicioApresentacao": ini.isoformat(),
                                                    "dataFimApresentacao": hoje.isoformat()}, timeout=90)
    itens: dict[str, dict] = {}
    for p in novas if isinstance(novas, list) else []:
        it = _item_senado(p, senadores, todos)
        if it and (p.get("objetivo") or "").lower().startswith("iniciadora"):
            it["grupos"] = ["nova"]
            itens[it["id"]] = it

    def busca(chave):
        sig, num, ano = chave
        try:
            r = get_json(f"{SENADO}/processo", params={"sigla": sig, "numero": num, "ano": ano}, timeout=60)
        except Exception as e:  # noqa: BLE001
            log.warning("Senado: %s %s/%s indisponível: %s", sig, num, ano, e)
            return chave, None
        rs = [x for x in (r if isinstance(r, list) else []) if (x.get("casaIdentificadora") or "SF") in ("SF", "CN")]
        return chave, (rs[0] if rs else None)

    for (sig, num, ano), p in _em_paralelo(busca, list(por_prop)):
        if not p:
            continue
        it = itens.get(f"sf-{p.get('codigoMateria')}") or _item_senado(p, senadores, todos)
        if not it:
            continue
        it["pauta"] = sorted(por_prop[(sig, num, ano)], key=lambda x: x["data"])
        for x in it["pauta"]:
            x["url"] = x["url"] or it["url"]
        it["grupos"] = ["pauta"] + [g for g in it.get("grupos", []) if g != "pauta"]
        em_plen = any(x["onde"].startswith("Plenário") for x in it["pauta"])
        it["etapa"] = max(it["etapa"], 2 if em_plen else 1) if not it.get("veio_da_camara") else it["etapa"]
        itens[it["id"]] = it
    # A agenda passa a apontar para o id do item (sf-{codigoMateria}) e não para a sigla
    por_chave = {(i["sigla"], i["numero"], i["ano"]): i["id"] for i in itens.values()}
    for ev in agenda:
        ev["itens"] = [por_chave[tuple(k.split("-"))] for k in ev["itens"] if tuple(k.split("-")) in por_chave]
    agenda = [ev for ev in agenda if ev["itens"]]
    log.info("Senado: %d propostas acompanhadas, %d reuniões com pauta", len(itens), len(agenda))
    return list(itens.values()), agenda


# ---------------------------------------------------------------- montagem

def completar(it: dict) -> dict:
    it["nome"] = f"{it['sigla']} {it['numero']}/{it['ano']}"
    it["resumo"] = resumo_simples(it["ementa"])
    it["o_que_e"] = O_QUE_E.get(it["sigla"], "")
    it["etapa_nome"] = ETAPAS[it["etapa"]]
    it["temas"] = temas_de(it["ementa"])
    it["proximo"] = proximo_passo(it)
    it.setdefault("pauta", [])
    it.pop("final", None)
    for a in it["autores"]:
        a["id"] = a["id"] if id_seguro(a.get("id")) else ""
    return it


def _com_reserva(nome: str, cache: Path, fn):
    """Se a API falhar, usa a última coleta boa (e avisa no site)."""
    arq = cache / f"tramitacao-{nome}.json"
    try:
        r = fn()
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        return r, ""
    except Exception as e:  # noqa: BLE001
        log.warning("Projetos em andamento (%s): %s", nome, e)
        if arq.exists():
            avisar(f"Projetos em andamento: a API {'da Câmara' if nome == 'camara' else 'do Senado'} não respondeu; "
                   "mostramos a última lista que conseguimos")
            return json.loads(arq.read_text(encoding="utf-8")), "reserva"
        avisar(f"Projetos em andamento: a API {'da Câmara' if nome == 'camara' else 'do Senado'} não respondeu; essa Casa está faltando")
        return [[], []], "faltando"


def coletar(saida: Path, cache: Path, politicos: list[dict], hoje: dt.date | None = None) -> dict:
    hoje = hoje or dt.date.today()
    deputados = {p["id"]: p for p in politicos if p.get("casa") == "camara"}
    (ic, ac), sc = _com_reserva("camara", cache, lambda: camara(hoje, deputados))
    (is_, as_), ss = _com_reserva("senado", cache, lambda: senado(hoje, politicos))
    itens = [completar(dict(i)) for i in ic + is_]
    ordem = {"pauta": 0, "mpv": 1, "nova": 2}
    # Primeiro o que está na pauta (pela data), depois as MPs e as novas (as mais recentes primeiro)
    itens.sort(key=lambda i: (min(ordem[g] for g in i["grupos"]),
                              i["pauta"][0]["data"] if i["pauta"] else "",
                              -int(i["apresentada"].replace("-", "") or 0) if not i["pauta"] else 0))
    # A agenda só aponta para propostas da lista. Se a API não devolveu o detalhe de uma proposta, ela fica de fora
    # da lista e também da agenda (antes a reunião continuava apontando para ela e a conferência barrava o site).
    ids = {i["id"] for i in itens}
    agenda = []
    for ev in sorted(ac + as_, key=lambda e: e["data"]):
        fora = [x for x in ev["itens"] if x not in ids]
        if fora:
            log.warning("Agenda %s: propostas sem detalhe na API ficam de fora: %s", ev.get("id"), fora)
        ev = {**ev, "itens": [x for x in ev["itens"] if x in ids]}
        if ev["itens"]:
            agenda.append(ev)
    out = {"atualizado_em": hoje.isoformat(), "dias_pauta": DIAS_PAUTA, "dias_novas": DIAS_NOVAS,
           "etapas": ETAPAS, "o_que_e": O_QUE_E, "situacao_fontes": {"camara": sc or "ok", "senado": ss or "ok"},
           "fontes": {"camara": CAMARA, "senado": SENADO}, "itens": itens, "agenda": agenda}
    write_json(saida / "tramitacao.json", out)
    log.info("Projetos em andamento: %d propostas, %d reuniões com pauta", len(itens), len(agenda))
    return out

