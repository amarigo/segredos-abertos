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
SENADO_PESSOAL = "https://www6g.senado.leg.br/transparencia/sen/{cod}/pessoal/?local=gabinete&ano={ano}&vinculo=TODOS"
MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
NUM = r"(-?[\d.]+,\d+)"


def _texto(h: str) -> str:
    h = re.sub(r"(?s)<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(h)).strip()


def _get_text(url: str) -> str | None:
    for tentativa in range(3):
        try:
            r = _session.get(url, timeout=60, headers={"Accept": "text/html,application/json"})
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
        m = re.search(r"Gasto " + NUM, t[i_cota:i_verba if i_verba > i_cota else None])
        if m:
            out["cota_oficial"] = round(to_float(m.group(1)), 2)
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
    return out


# ---------------------------------------------------------------- todos

def coletar(politicos: list[dict], anos: list[int], cache: Path, workers: int = 6) -> dict[str, dict[int, dict]]:
    """Devolve {politico_id: {ano: recursos}}."""
    atual = dt.date.today().year
    cache.mkdir(parents=True, exist_ok=True)
    tarefas = [(p, a) for p in politicos for a in anos]

    def um(pa):
        p, ano = pa
        f = cache / f"{p['id']}-{ano}.json"
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
