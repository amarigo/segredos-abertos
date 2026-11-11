"""Quem foi eleito para os mandatos de agora: governadores e assembleias de todos os estados, prefeitos e vereadores
de todas as cidades, com o partido e o patrimônio declarado ao TSE.

Fonte: dados abertos do TSE de cada eleição (tse.py): "Candidatos" (quem foi eleito, DS_SIT_TOT_TURNO), "Bens de
candidatos" (patrimônio) e "Vagas" (quantas cadeiras há em cada lugar, para conferir). O endereço de cada arquivo vem
da API do portal de dados abertos do TSE; a API do DivulgaCandContas recusa acesso automático (veja tse.py).

Eleito não é o mesmo que quem está no cargo hoje: há cassação, renúncia, morte e suplente que assume. O TSE publica
quem foi eleito; o site diz isso com essas palavras. Eleição suplementar (quando a eleição da cidade foi anulada) é
publicada no mesmo arquivo: o prefeito e o vice eleitos nela substituem os da eleição normal.

Gastos das assembleias e câmaras municipais não têm uma fonte nacional: cada casa publica do seu jeito. O Minas
Nossa (/mg/) mostra os da Assembleia de Minas.

Grava data/eleitos/estados.json, data/eleitos/cidades/{UF}.json e data/eleitos/indice.json.
"""
from __future__ import annotations

import datetime as dt
import logging
from collections import Counter, defaultdict
from pathlib import Path

from . import tse
from .patrimonio import GERAIS, MUNICIPAIS, resultado, titulo
from .util import avisar, write_json

log = logging.getLogger("sa_etl.eleitos")

CARGOS_ESTADO = {"GOVERNADOR": "governador", "VICE-GOVERNADOR": "vice", "DEPUTADO ESTADUAL": "deputados",
                 "DEPUTADO DISTRITAL": "deputados"}
CARGOS_CIDADE = {"PREFEITO": "prefeito", "VICE-PREFEITO": "vice", "VEREADOR": "vereadores"}
ELEICAO_2026 = "https://amarigo.github.io/segredos-abertos/eleicao2026/"


def mandato_atual(anos: list[int], hoje: dt.date) -> int:
    """A eleição cujo mandato está valendo: o mandato começa em 1º de janeiro do ano seguinte à eleição."""
    return max(a for a in anos if dt.date(a + 1, 1, 1) <= hoje)


def _pessoa(c: dict, bens: dict[str, list], com_tipos: bool) -> dict:
    b = bens.get(c["sq"])
    out = {"sq": c["sq"], "nome": c["urna"], "civil": titulo(c["nome"]), "partido": c["partido"], "numero": c["nr"],
           "resultado": resultado(c["resultado"]), "patrimonio": b[0] if b else 0.0}
    if c.get("da_suplementar"):
        out["suplementar"] = c["da_suplementar"]
    if not b:
        out["sem_bens"] = True
    elif com_tipos:
        out["tipos"] = [{"tipo": t, "valor": v} for t, v in sorted(b[1].items(), key=lambda x: -x[1])[:6]]
    return out


def finais(cands: list[dict]) -> list[dict]:
    """Uma linha por candidato: a do último turno (o 2º turno diz o resultado final)."""
    por_sq: dict[str, dict] = {}
    for c in cands:
        if c["sq"] not in por_sq or c["turno"] > por_sq[c["sq"]]["turno"]:
            por_sq[c["sq"]] = c
    return list(por_sq.values())


def eleitos_por_lugar(cands: list[dict], cargos: dict[str, str]) -> dict[tuple[str, str], dict]:
    """{(UF, UE): {"nome": ..., "governador"/"prefeito": [...], ..., "suplementar": {...}, "sem_eleito": [...]}}.

    Se houve eleição suplementar com eleito para um cargo, ela substitui a normal para esse cargo (a mais recente).
    Cargo com candidatos e nenhum eleito no arquivo vai em "sem_eleito": o TSE marca o resultado como "#NULO" quando a
    eleição do cargo foi anulada ou está em julgamento (em 2024, por exemplo, os vereadores de Ananindeua) e "NÃO
    ELEITO" para todos quando o mais votado teve o registro negado. O site diz isso; não escolhemos ninguém."""
    lugares: dict[tuple[str, str], dict] = {}
    por_cargo: dict[tuple[str, str, str], dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    disputados: set[tuple[str, str, str]] = set()
    for c in finais(cands):
        if c["cargo"] not in cargos:
            continue
        k = (c["uf"], c["ue"])
        lugares.setdefault(k, {"uf": c["uf"], "ue": c["ue"], "nome": titulo(c["nm_ue"])})
        disputados.add((c["uf"], c["ue"], c["cargo"]))
        if tse.eleito(c):
            por_cargo[(c["uf"], c["ue"], c["cargo"])][f"{c['tipo']}|{c['data']}"].append(c)
    for (uf, ue, cargo), por_eleicao in por_cargo.items():
        chave = max(por_eleicao, key=lambda e: (e.startswith("sup"), e.split("|")[1]))
        lug = lugares[(uf, ue)]
        data = chave.split("|")[1]
        ords = [e for e in por_eleicao if e.startswith("ord")]
        if chave.startswith("sup") and ords and len(por_eleicao[chave]) < len(por_eleicao[ords[0]]):
            # suplementar só para parte das cadeiras (em 2025, Braga-RS elegeu 1 vereador de 9): o TSE não diz quem
            # saiu, então mostramos os eleitos da eleição normal e o da suplementar, com aviso
            lug.setdefault(cargos[cargo], []).extend(por_eleicao[ords[0]])
            lug[cargos[cargo]].extend({**c, "da_suplementar": data} for c in por_eleicao[chave])
            lug.setdefault("suplementar_parcial", {})[cargos[cargo]] = data
            continue
        lug.setdefault(cargos[cargo], []).extend(por_eleicao[chave])
        if chave.startswith("sup"):
            lug.setdefault("suplementar", {})[cargos[cargo]] = data
    ordem = list(cargos)
    for uf, ue, cargo in sorted(disputados - set(por_cargo), key=lambda x: (x[0], x[1], ordem.index(x[2]))):
        sem = lugares[(uf, ue)].setdefault("sem_eleito", [])
        if cargos[cargo] not in sem:
            sem.append(cargos[cargo])
    return lugares


def _montar_lugar(lug: dict, bens: dict[str, list], com_tipos: bool) -> dict:
    out = {k: v for k, v in lug.items() if k == "sem_eleito" or not isinstance(v, list)}
    for k, v in lug.items():
        if isinstance(v, list) and k != "sem_eleito":
            pessoas = sorted((_pessoa(c, bens, com_tipos) for c in v), key=lambda p: (p["partido"], p["nome"]))
            out[k] = pessoas
    return out


def estados(cache: Path, hoje: dt.date) -> dict:
    ano = mandato_atual(GERAIS, hoje)
    cands, bens, vagas = tse.candidatos(ano, cache), tse.bens(ano, cache), tse.vagas(ano, cache)
    lugares = eleitos_por_lugar(cands, CARGOS_ESTADO)
    ufs = {}
    for (uf, _), lug in sorted(lugares.items()):
        x = _montar_lugar(lug, bens, com_tipos=True)
        cargo = "DEPUTADO DISTRITAL" if uf == "DF" else "DEPUTADO ESTADUAL"
        x["vagas"] = vagas.get(f"{uf}|{uf}|{cargo}")
        x["casa"] = "Câmara Legislativa do Distrito Federal" if uf == "DF" else "Assembleia Legislativa"
        ufs[uf] = x
    return {"ano": ano, "mandato": f"{ano + 1}–{ano + 4}", "ufs": ufs,
            "fonte": tse.PAGINA.format(pacote=tse.pacote(ano)), "proxima": ELEICAO_2026 if ano < max(a for a in GERAIS if dt.date(a, 11, 1) <= hoje) else ""}


def cidades(cache: Path, hoje: dt.date) -> dict:
    ano = mandato_atual(MUNICIPAIS, hoje)
    cands, bens, vagas = tse.candidatos(ano, cache), tse.bens(ano, cache), tse.vagas(ano, cache)
    lugares = eleitos_por_lugar(cands, CARGOS_CIDADE)
    por_uf: dict[str, list] = defaultdict(list)
    for (uf, ue), lug in lugares.items():
        x = _montar_lugar(lug, bens, com_tipos=False)
        x["vagas"] = vagas.get(f"{uf}|{ue}|VEREADOR")
        por_uf[uf].append(x)
    for v in por_uf.values():
        v.sort(key=lambda c: c["nome"])
    return {"ano": ano, "mandato": f"{ano + 1}–{ano + 4}", "ufs": dict(sorted(por_uf.items())),
            "fonte": tse.PAGINA.format(pacote=tse.pacote(ano))}


def coletar(saida: Path, cache: Path, hoje: dt.date | None = None) -> dict:
    hoje = hoje or dt.date.today()
    resumo = {}
    try:
        e = estados(cache, hoje)
        write_json(saida / "eleitos" / "estados.json", {**e, "atualizado": hoje.isoformat()})
        resumo["estados"] = {"ano": e["ano"], "ufs": len(e["ufs"])}
    except Exception:  # noqa: BLE001
        log.exception("Eleitos dos estados: erro")
        avisar("Governadores e assembleias: os dados do TSE não puderam ser lidos; a página ficou de fora desta atualização")
    try:
        c = cidades(cache, hoje)
        indice = []
        for uf, lista in c["ufs"].items():
            write_json(saida / "eleitos" / "cidades" / f"{uf}.json", {"ano": c["ano"], "mandato": c["mandato"], "uf": uf,
                                                                      "cidades": lista, "fonte": c["fonte"],
                                                                      "atualizado": hoje.isoformat()})
            indice += [[x["uf"], x["ue"], x["nome"]] for x in lista]
        n = Counter()
        for lista in c["ufs"].values():
            for x in lista:
                n["prefeitos"] += len(x.get("prefeito") or [])
                n["vereadores"] += len(x.get("vereadores") or [])
                n["sem_eleito"] += bool(x.get("sem_eleito"))
        write_json(saida / "eleitos" / "indice.json", {"ano": c["ano"], "mandato": c["mandato"], "cidades": indice,
                                                       "fonte": c["fonte"], "atualizado": hoje.isoformat(), **n})
        resumo["cidades"] = {"ano": c["ano"], "cidades": len(indice), **n}
    except Exception:  # noqa: BLE001
        log.exception("Eleitos das cidades: erro")
        avisar("Prefeitos e vereadores: os dados do TSE não puderam ser lidos; a página ficou de fora desta atualização")
    log.info("Eleitos: %s", resumo)
    return resumo
