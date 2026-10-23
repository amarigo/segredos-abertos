"""Governo de Minas: quem foi eleito governador e vice, e links para o que o governo publica.

Fontes:
- TSE: resultado da eleição para governador (arquivo de votação) e o vice da chapa (lista de candidatos).
- Portal da Transparência de MG e Dados MG: salários, viagens, diárias e pagamentos do governo (links).

O TSE registra quem foi eleito. Se o governador deixar o cargo (por exemplo, para disputar outra eleição), quem
assume é o vice; essa troca não aparece nos arquivos do TSE, e a página avisa.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from . import partidos_hist, tse
from .cidades import _int, _nome, _ordinaria, _partido, _votos

log = logging.getLogger("mg_etl.governo")

LINKS = [
    {"nome": "Portal da Transparência de Minas Gerais", "url": "https://www.transparencia.mg.gov.br/",
     "explica": "Salário de cada servidor, despesas, contratos, convênios e repasses aos municípios."},
    {"nome": "Dados abertos do Governo de Minas", "url": "https://dados.mg.gov.br/",
     "explica": "Os arquivos completos: despesa por favorecido, remuneração, viagens e diárias."},
    {"nome": "Emendas estaduais (Dados MG)", "url": "https://dados.mg.gov.br/dataset/portal_emendas_estaduais",
     "explica": "Execução das emendas dos deputados estaduais: empenhos e pagamentos."},
    {"nome": "Assembleia Legislativa (ALMG)", "url": "https://www.almg.gov.br/",
     "explica": "Leis, projetos, gastos dos deputados estaduais e prestação de contas."},
    {"nome": "Tribunal de Contas do Estado (TCE-MG)", "url": "https://www.tce.mg.gov.br/",
     "explica": "Fiscaliza as contas do governo do estado e das prefeituras."},
]


FONTE_TSE = "https://dadosabertos.tse.jus.br/"


def eleicao(ano: int, cache: Path, uf: str = "MG") -> dict | None:
    """Governador e vice eleitos em `ano` (eleição geral), com votos no estado."""
    vot = tse.linhas_estaduais("votacao", ano, uf, {"GOVERNADOR"}, cache)
    if not vot:
        return None
    soma: dict = {}
    for r in vot:
        if not _ordinaria(r):
            continue
        k = (_int(r.get("NR_TURNO")) or 1, r.get("SQ_CANDIDATO") or r.get("NR_CANDIDATO"))
        c = soma.setdefault(k, {"nome": _nome(r), "numero": r.get("NR_CANDIDATO") or "", "partido": _partido(r),
                                "votos": 0, "sit": (r.get("DS_SIT_TOT_TURNO") or "").upper()})
        c["votos"] += _votos(r)
    if not soma:
        return None
    turno = max(t for t, _ in soma)
    cs = [c for (t, _), c in soma.items() if t == turno]
    total = sum(c["votos"] for c in cs) or 1
    eleitos = [c for c in cs if c["sit"].startswith("ELEITO")]
    if len(eleitos) != 1:
        log.warning("Governador %s: %d eleitos", ano, len(eleitos))
        return None
    g = eleitos[0]
    vice = None
    cand = tse.linhas_estaduais("cand", ano, uf, {"VICEGOVERNADOR"}, cache)
    for r in cand or []:
        if _int(r.get("NR_CANDIDATO")) == _int(g["numero"]) and _ordinaria(r):
            if vice is None or re.search(r"\b(APTO|DEFERIDO)\b", r.get("DS_SITUACAO_CANDIDATURA") or "", re.I):
                vice = r
    def pessoa(nome: str, partido: str) -> dict:
        h = partidos_hist.hoje(partido, ano)
        return {"nome": nome, "partido": partido, "partido_hoje": h["sigla"], "mudou": h["mudou"]}
    return {
        "eleicao": ano, "inicio": ano + 1, "fim": ano + 4, "turnos": turno,
        "governador": {**pessoa(g["nome"], g["partido"]), "votos": g["votos"], "pct": round(100 * g["votos"] / total, 2)},
        "vice": pessoa(_nome(vice), _partido(vice)) if vice else None,
        "candidatos": [{"nome": c["nome"], "partido": c["partido"], "votos": c["votos"], "pct": round(100 * c["votos"] / total, 2),
                        "eleito": c is g} for c in sorted(cs, key=lambda c: -c["votos"])[:6]],
    }


def coletar(cache: Path) -> dict:
    _, gerais = tse.anos_ate()
    eleicoes = []
    for ano in gerais[-2:][::-1]:  # as duas últimas eleições gerais
        e = eleicao(ano, cache / "tse")
        if e:
            eleicoes.append(e)
    return {"eleicoes": eleicoes, "links": LINKS, "fonte_tse": FONTE_TSE}
