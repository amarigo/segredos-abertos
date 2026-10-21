"""Câmara dos Deputados: deputados em exercício, cota parlamentar (CEAP) e votações nominais do plenário.

Fontes:
- API: https://dadosabertos.camara.leg.br/api/v2/deputados
- Cota anual: https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip
- Votações: https://dadosabertos.camara.leg.br/arquivos/votacoes*/csv/*-{ano}.csv
"""
from __future__ import annotations

import datetime as dt
import logging
from collections import defaultdict
from pathlib import Path

from .categorias import categoria_curta, grupo_de
from .util import digits, download, get_json, read_csv_file, to_float

log = logging.getLogger("sa_etl.camara")

API = "https://dadosabertos.camara.leg.br/api/v2"
COTA_URL = "https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip"
ARQ = "https://dadosabertos.camara.leg.br/arquivos"
VOT_URLS = {
    "votacoes": ARQ + "/votacoes/csv/votacoes-{ano}.csv",
    "votos": ARQ + "/votacoesVotos/csv/votacoesVotos-{ano}.csv",
    "orientacoes": ARQ + "/votacoesOrientacoes/csv/votacoesOrientacoes-{ano}.csv",
    "proposicoes": ARQ + "/votacoesProposicoes/csv/votacoesProposicoes-{ano}.csv",
}


def pid(dep_id: str | int) -> str:
    return f"dep-{dep_id}"


def deputados() -> list[dict]:
    out: list[dict] = []
    url = f"{API}/deputados"
    params: dict | None = {"itens": 100, "ordem": "ASC", "ordenarPor": "nome"}
    while url:
        data = get_json(url, params=params)
        for d in data.get("dados", []):
            out.append({
                "id": pid(d["id"]),
                "casa": "camara",
                "cargo": "Deputado(a) Federal",
                "nome": d.get("nome", "").strip(),
                "partido": d.get("siglaPartido") or "",
                "uf": d.get("siglaUf") or "",
                "foto": d.get("urlFoto") or "",
                "fonte": f"https://www.camara.leg.br/deputados/{d['id']}",
            })
        url = next((l["href"] for l in data.get("links", []) if l.get("rel") == "next"), None)
        params = None
    log.info("Câmara: %d deputados em exercício", len(out))
    return out


def _validade(ano: int) -> float | None:
    """Arquivos do ano atual e do anterior mudam (notas lançadas com atraso): baixa de novo a cada 20 horas."""
    return 20 if ano >= dt.date.today().year - 1 else None


def parse_cota(rows, ids: set[str]) -> list[dict]:
    """Converte linhas do arquivo da cota em despesas no formato comum."""
    out = []
    for r in rows:
        # ideCadastro é o mesmo id da API; nuDeputadoId é um número interno diferente
        dep = (r.get("ideCadastro") or "").strip()
        if not dep or pid(dep) not in ids:
            dep = (r.get("nuDeputadoId") or "").strip()
        if not dep or pid(dep) not in ids:
            continue
        valor = to_float(r.get("vlrLiquido"))
        if valor == 0:
            continue
        cat = r.get("txtDescricao") or ""
        out.append({
            "politico": pid(dep),
            "ano": int(to_float(r.get("numAno"))),
            "mes": int(to_float(r.get("numMes"))),
            "data": (r.get("datEmissao") or "")[:10],
            "categoria": categoria_curta(cat),
            "grupo": grupo_de(cat),
            "fornecedor": (r.get("txtFornecedor") or "").strip(),
            "doc": digits(r.get("txtCNPJCPF")),
            "valor": round(valor, 2),
            "url": (r.get("urlDocumento") or "").strip(),
        })
    return out


def despesas(anos: list[int], ids: set[str], cache: Path) -> list[dict]:
    out: list[dict] = []
    for ano in anos:
        try:
            f = download(COTA_URL.format(ano=ano), cache / f"camara-cota-{ano}.csv.zip", max_horas=_validade(ano))
        except Exception as e:  # noqa: BLE001 - um ano faltando não deve parar tudo
            log.warning("Cota da Câmara %s indisponível: %s", ano, e)
            continue
        rows = parse_cota(read_csv_file(f), ids)
        log.info("Câmara: %d despesas em %s", len(rows), ano)
        out.extend(rows)
    return out


def parse_votacoes(votacoes_rows, votos_rows, orient_rows, prop_rows, ids: set[str]) -> tuple[list[dict], list[dict]]:
    """Monta as votações nominais do plenário e os votos de cada deputado."""
    votos_por = defaultdict(list)
    for r in votos_rows:
        dep = (r.get("deputado_id") or "").strip()
        if not dep:
            continue
        votos_por[r["idVotacao"]].append({
            "politico": pid(dep),
            "voto": normaliza_voto(r.get("voto", "")),
            "partido": r.get("deputado_siglaPartido") or "",
        })

    orient = defaultdict(dict)
    for r in orient_rows:
        sigla = (r.get("siglaBancada") or "").strip()
        if sigla:
            orient[r["idVotacao"]][sigla] = normaliza_voto(r.get("orientacao", ""))

    props: dict[str, dict] = {}
    for r in prop_rows:
        if r["idVotacao"] in props:
            continue
        props[r["idVotacao"]] = {
            "sigla": r.get("proposicao_siglaTipo") or "",
            "numero": r.get("proposicao_numero") or "",
            "ano": r.get("proposicao_ano") or "",
            "ementa": (r.get("proposicao_ementa") or "").strip(),
            "titulo": (r.get("proposicao_titulo") or "").strip(),
            "url": f"https://www.camara.leg.br/propostas-legislativas/{r.get('proposicao_id')}" if r.get("proposicao_id") else "",
        }

    votacoes, votos = [], []
    for r in votacoes_rows:
        vid = r.get("id", "")
        if (r.get("siglaOrgao") or "").upper() != "PLEN" or vid not in votos_por:
            continue
        vs = [v for v in votos_por[vid] if v["politico"] in ids]
        if not vs:
            continue
        votacoes.append({
            "id": f"cd-{vid}",
            "casa": "camara",
            "data": (r.get("data") or r.get("dataHoraRegistro") or "")[:10],
            "descricao": (r.get("descricao") or "").strip(),
            "aprovada": (r.get("aprovacao") or "").strip() == "1",
            "proposicao": props.get(vid),
            "orientacoes": orient.get(vid, {}),
            "fonte": f"{API}/votacoes/{vid}",
        })
        for v in vs:
            votos.append({"votacao": f"cd-{vid}", **v})
    return votacoes, votos


def votacoes(anos: list[int], ids: set[str], cache: Path) -> tuple[list[dict], list[dict]]:
    all_v, all_votos = [], []
    for ano in anos:
        try:
            files = {k: download(u.format(ano=ano), cache / f"camara-{k}-{ano}.csv", max_horas=_validade(ano))
                     for k, u in VOT_URLS.items()}
        except Exception as e:  # noqa: BLE001
            log.warning("Votações da Câmara %s indisponíveis: %s", ano, e)
            continue
        v, vs = parse_votacoes(
            read_csv_file(files["votacoes"]), read_csv_file(files["votos"]),
            read_csv_file(files["orientacoes"]), read_csv_file(files["proposicoes"]), ids,
        )
        log.info("Câmara: %d votações nominais e %d votos em %s", len(v), len(vs), ano)
        all_v += v
        all_votos += vs
    return all_v, all_votos


def normaliza_voto(v: str) -> str:
    v = (v or "").strip().lower()
    if v.startswith("sim"):
        return "Sim"
    if v.startswith("n"):
        return "Não"
    if v.startswith("abst"):
        return "Abstenção"
    if v.startswith("obstr"):
        return "Obstrução"
    if v.startswith("libera"):
        return "Liberado"
    if v.startswith("art"):
        return "Art. 17"
    return v.capitalize() if v else "—"
