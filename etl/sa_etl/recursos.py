"""Salário, verba de gabinete, benefícios e equipe de cada parlamentar, por ano.

Esses dados não estão nos arquivos da cota. Vêm das páginas oficiais:
- Câmara: https://www.camara.leg.br/deputados/{id}?ano=AAAA (resumo), /pessoal-gabinete e /remuneracao
- Senado: https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/{cod}/recursos-utilizados?ano=AAAA
          e https://www6g.senado.leg.br/transparencia/sen/{cod}/pessoal/?local=gabinete&ano=AAAA

Anos passados ficam guardados no cache; o ano corrente é baixado de novo a cada execução.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .util import _session, to_float

log = logging.getLogger("sa_etl.recursos")

CAMARA = "https://www.camara.leg.br/deputados/{id}{sub}?ano={ano}"
SENADO_JSON = "https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/{cod}/recursos-utilizados?ano={ano}"
SENADO_LEGIS = "https://legis.senado.leg.br/dadosabertos"
SENADO_AUTORIA = SENADO_LEGIS + "/processo?codigoParlamentarAutor={cod}&ano={ano}"
SENADO_RELATORIA = SENADO_LEGIS + "/processo/relatoria?codigoParlamentar={cod}&dataInicio={ano}-01-01&dataFim={ano}-12-31"
SENADO_DISCURSOS = SENADO_LEGIS + "/senador/{cod}/discursos.json?dataInicio={ano}0101&dataFim={ano}1231"
SENADO_PESSOAL = "https://www6g.senado.leg.br/transparencia/sen/{cod}/pessoal/?local=gabinete&ano={ano}&vinculo=TODOS"
VERSAO = 3  # aumente quando mudar o que é lido das páginas, para não reaproveitar cache antigo
MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
NUM = r"(-?[\d.]+,\d+)"


def _texto(h: str) -> str:
    h = re.sub(r"(?s)<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(h)).strip()


def _get_text(url: str, timeout: int = 60, tentativas: int = 3) -> str | None:
    for tentativa in range(tentativas):
        try:
            r = _session.get(url, timeout=timeout, headers={"Accept": "text/html,application/json"})
            if r.status_code == 404:
                return None
            if r.status_code < 500:
                r.raise_for_status()
                r.encoding = r.encoding or "utf-8"
                return r.text
        except Exception as e:  # noqa: BLE001
            log.debug("Falha em %s: %s", url, e)
    return None


# ---------------------------------------------------------------- Câmara

def parse_camara_resumo(h: str) -> dict:
    """Lê a página principal do deputado num ano."""
    t = _texto(h)
    out: dict = {}
    i_cota, i_verba = t.find("Cota parlamentar"), t.find("Verba de gabinete")
    if i_cota >= 0:
        bloco = t[i_cota:i_verba if i_verba > i_cota else None]
        m = re.search(r"Gasto " + NUM, bloco)
        if m:
            out["cota_oficial"] = round(to_float(m.group(1)), 2)
        mensal = bloco[bloco.find("Gasto mensal"):] if "Gasto mensal" in bloco else ""
        meses = [{"mes": MESES.index(mes) + 1, "valor": round(to_float(val), 2)}
                 for mes, val in re.findall(r"\b(" + "|".join(MESES) + r") " + NUM, mensal)]
        if meses:
            out["cota_meses"] = meses
    if i_verba >= 0:
        fim = t.find("Pessoal de gabinete", i_verba)
        bloco = t[i_verba:fim if fim > 0 else None]
        m = re.search(r"Gasto " + NUM + r" [\d.,]+% Não utilizado " + NUM, bloco)
        if m:
            out["verba_gasto"] = round(to_float(m.group(1)), 2)
            out["verba_disponivel"] = round(to_float(m.group(1)) + to_float(m.group(2)), 2)
        mensal = bloco[bloco.find("Gasto mensal"):] if "Gasto mensal" in bloco else ""
        meses = []
        for mes, val in re.findall(r"\b(" + "|".join(MESES) + r") " + NUM, mensal):
            meses.append({"mes": MESES.index(mes) + 1, "valor": round(to_float(val), 2)})
        if meses:
            out["verba_meses"] = meses
    m = re.search(r"Pessoal de gabinete \?? ?(\d+) pessoas?", t)
    if m:
        out["n_pessoal"] = int(m.group(1))
    m = re.search(r"Salário mensal bruto \?? ?R\$ ?" + NUM, t)
    if m:
        out["salario_bruto"] = round(to_float(m.group(1)), 2)
    m = re.search(r"Imóvel funcional \?? ?(.+?) (?=Auxílio-moradia)", t)
    if m:
        out["imovel_funcional"] = m.group(1).strip()
    m = re.search(r"Auxílio-moradia \?? ?(.+?) (?=Viagens em missão)", t)
    if m:
        out["auxilio_moradia"] = m.group(1).strip()
    m = re.search(r"Viagens em missão oficial \?? ?(\d+)", t)
    if m:
        out["viagens_missao"] = int(m.group(1))
    m = re.search(r"Passaporte diplomático \?? ?(Possui|Não possui)", t)
    if m:
        out["passaporte_diplomatico"] = m.group(1)
    return out


def parse_camara_atuacao(t: str, ano: int) -> dict | None:
    """Bloco "Atuação no Plenário e Comissões" da página do deputado: propostas, relatorias, votações,
    discursos e presença. Quando o deputado não teve mandato no ano, a página mostra outro ano: aí não usamos."""
    m = re.search(r"Atuação no Plenário e Comissões (\d{4})", t)
    if not m or int(m.group(1)) != ano:
        return None
    b = t[m.end():m.end() + 1500]

    def n(padrao):
        x = re.search(padrao, b, re.I)
        return int(x.group(1).replace(".", "")) if x else None

    out = {"autoria": n(r"de sua autoria\D*?(\d[\d.]*)"), "relatadas": n(r"relatadas\D*?(\d[\d.]*)"),
           "votacoes": n(r"Votações nominais[\s?]*em Plenário (\d[\d.]*)"), "discursos": n(r"Discursos[\s?]*em Plenário (\d[\d.]*)")}
    for chave, local, unidade in (("plenario", "Plenário", "dias?"), ("comissoes", "comissões", "reuniões|reunião")):
        x = re.search(rf"Presença em {local}.*?Presenças\D*(\d+) (?:{unidade}) Ausências justificadas (\d+) (?:{unidade}) "
                      rf"Ausências não justificadas (\d+) (?:{unidade})", b, re.I)
        if x:
            out[chave] = [int(x.group(1)), int(x.group(2)), int(x.group(3))]
    return {k: v for k, v in out.items() if v is not None} or None


def parse_camara_pessoal(h: str) -> list[dict]:
    corpo = h[h.find("<tbody"):h.find("</tbody>")] if "<tbody" in h else ""
    out = []
    for tr in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", corpo):
        cels = [_texto(c) for c in re.findall(r"(?s)<td[^>]*>(.*?)</td>", tr)]
        if len(cels) >= 4 and cels[0]:
            out.append({"nome": cels[0], "grupo": cels[1].capitalize(), "cargo": cels[2], "periodo": cels[3]})
    return out


def parse_camara_remuneracao(h: str) -> list[dict]:
    corpo = h[h.find("<tbody"):h.find("</tbody>")] if "<tbody" in h else ""
    out = []
    for tr in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", corpo):
        cels = [_texto(c) for c in re.findall(r"(?s)<td[^>]*>(.*?)</td>", tr)]
        if len(cels) >= 2 and cels[0].isdigit():
            out.append({"mes": int(cels[0]), "valor": round(to_float(cels[1]), 2)})
    return out


def camara_ano(dep_id: str, ano: int) -> dict | None:
    h = _get_text(CAMARA.format(id=dep_id, sub="", ano=ano))
    if not h:
        return None
    out = parse_camara_resumo(h)
    at = parse_camara_atuacao(_texto(h), ano)
    if at:
        out["atuacao"] = at
    p = _get_text(CAMARA.format(id=dep_id, sub="/pessoal-gabinete", ano=ano))
    out["equipe"] = parse_camara_pessoal(p) if p else []
    r = _get_text(CAMARA.format(id=dep_id, sub="/remuneracao", ano=ano))
    out["salario_meses"] = parse_camara_remuneracao(r) if r else []
    out["salario_ano"] = round(sum(x["valor"] for x in out["salario_meses"]), 2) or None
    return out


# ---------------------------------------------------------------- Senado

def parse_senado_json(d: dict) -> dict:
    dados = (d.get("data") or [{}])[0] if isinstance(d, dict) else {}
    cotas = dados.get("cotas") or {}
    outros = dados.get("gastosNaoInclusos") or {}
    pessoal = dados.get("pessoal") or []
    return {
        "cota_oficial": round(float(cotas.get("totalValor") or 0), 2),
        "outros_gastos": [{"recurso": x.get("recurso", ""), "valor": round(float(x.get("valor") or 0), 2)}
                          for x in outros.get("despesas") or [] if x.get("valor")],
        "outros_total": round(float(outros.get("totalValor") or 0), 2),
        "beneficios": [{"beneficio": b.get("beneficio", ""), "utilizacao": b.get("utilizacao", "")}
                       for b in dados.get("beneficios") or []],
        "n_pessoal": sum(int(p.get("quantidade") or 0) for p in pessoal) or None,
        "vinculos": [{"vinculo": v.get("vinculo", ""), "quantidade": v.get("quantidade", 0)}
                     for p in pessoal for v in p.get("vinculos") or []],
    }


def parse_senado_pessoal(h: str) -> list[dict]:
    out = []
    for cap, corpo in re.findall(r"(?s)<caption>(.*?)</caption>.*?<tbody>(.*?)</tbody>", h):
        vinculo = _texto(cap).replace("Funcionários", "").strip().capitalize()
        for tr in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", corpo):
            cels = [_texto(c) for c in re.findall(r"(?s)<td[^>]*>(.*?)</td>", tr)]
            if len(cels) >= 3 and cels[0]:
                out.append({"nome": cels[0], "grupo": vinculo, "cargo": f"{cels[2].capitalize()} ({cels[1]})", "periodo": ""})
    return out


def _lista_json(txt: str | None) -> list | None:
    try:
        d = json.loads(txt) if txt else None
    except ValueError:
        return None
    return d if isinstance(d, list) else None


def parse_senado_discursos(txt: str | None) -> int | None:
    """Pronunciamentos no Senado (sem os do Congresso, em sessão conjunta)."""
    try:
        p = (json.loads(txt or "") or {}).get("DiscursosParlamentar", {}).get("Parlamentar", {})
    except (ValueError, AttributeError):
        return None
    lista = (p.get("Pronunciamentos") or {}).get("Pronunciamento") or []
    lista = lista if isinstance(lista, list) else [lista]
    return sum(1 for x in lista if (x.get("SiglaCasaPronunciamento") or "SF") == "SF")


def senado_atuacao(cod: str, ano: int) -> dict:
    """Propostas de autoria, relatorias e discursos do senador no ano (dados abertos do Senado)."""
    out = {}
    autorias = _lista_json(_get_text(SENADO_AUTORIA.format(cod=cod, ano=ano)))
    if autorias is not None:
        out["autoria"] = len(autorias)
    relatorias = _lista_json(_get_text(SENADO_RELATORIA.format(cod=cod, ano=ano)))
    if relatorias is not None:
        out["relatadas"] = len({r.get("codigoMateria") or r.get("idProcesso") for r in relatorias})
    d = parse_senado_discursos(_get_text(SENADO_DISCURSOS.format(cod=cod, ano=ano)))
    if d is not None:
        out["discursos"] = d
    return out


def senado_ano(cod: str, ano: int) -> dict | None:
    j = _get_text(SENADO_JSON.format(cod=cod, ano=ano))
    if not j:
        return None
    try:
        out = parse_senado_json(json.loads(j))
    except (ValueError, IndexError, TypeError):
        return None
    p = _get_text(SENADO_PESSOAL.format(cod=cod, ano=ano))
    out["equipe"] = parse_senado_pessoal(p) if p else []
    at = senado_atuacao(cod, ano)
    if at:
        out["atuacao"] = at
    return out


# ---------------------------------------------------------------- todos

def coletar(politicos: list[dict], anos: list[int], cache: Path, workers: int = 6) -> dict[str, dict[int, dict]]:
    """Devolve {politico_id: {ano: recursos}}."""
    atual = dt.date.today().year
    cache.mkdir(parents=True, exist_ok=True)
    tarefas = [(p, a) for p in politicos for a in anos]

    def um(pa):
        p, ano = pa
        f = cache / f"{p['id']}-{ano}-v{VERSAO}.json"
        if ano < atual and f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                pass
        num = p["id"].split("-", 1)[1]
        r = camara_ano(num, ano) if p["casa"] == "camara" else senado_ano(num, ano)
        if r is not None:
            f.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        elif f.exists():  # falhou agora: usa o que já tinha
            return json.loads(f.read_text(encoding="utf-8"))
        return r

    out: dict[str, dict[int, dict]] = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for (p, ano), r in zip(tarefas, ex.map(um, tarefas)):
            if r:
                out.setdefault(p["id"], {})[ano] = r
    log.info("Recursos (salário, verba, equipe): %d de %d políticos", len(out), len(politicos))
    return out
