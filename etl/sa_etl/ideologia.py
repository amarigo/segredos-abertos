"""Posição esquerda/direita estimada pelos votos.

Método: cada parlamentar vira uma linha de votos (Sim = +1, Não = -1, outros = vazio) nas votações
nominais. Centralizamos cada votação e extraímos o primeiro eixo (decomposição SVD), que em
parlamentos costuma separar governo e oposição / esquerda e direita. O sinal é orientado para que
os partidos de referência da direita fiquem do lado positivo. É a mesma ideia do W-NOMINATE /
Voteview, numa versão simples e transparente.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

# Partidos usados só para decidir qual lado do eixo é "direita". Não afetam a posição de ninguém.
REFERENCIA_DIREITA = {"PL", "NOVO"}
REFERENCIA_ESQUERDA = {"PT", "PSOL", "PCDOB", "PC do B"}

MIN_VOTOS = 15


def posicoes(votos: list[dict], partido_de: dict[str, str]) -> dict[str, float]:
    """Retorna {politico: posição} de -1 (esquerda) a +1 (direita)."""
    pols = sorted({v["politico"] for v in votos})
    vots = sorted({v["votacao"] for v in votos})
    if len(pols) < 5 or len(vots) < 5:
        return {}
    pi = {p: i for i, p in enumerate(pols)}
    vi = {v: i for i, v in enumerate(vots)}
    m = np.full((len(pols), len(vots)), np.nan)
    for v in votos:
        x = 1.0 if v["voto"] == "Sim" else -1.0 if v["voto"] == "Não" else np.nan
        m[pi[v["politico"]], vi[v["votacao"]]] = x

    validos = (~np.isnan(m)).sum(axis=1) >= MIN_VOTOS
    m = m[validos]
    pols = [p for p, ok in zip(pols, validos) if ok]
    # Ignora votações quase unânimes (não dizem nada sobre lado)
    sim = np.sum(m == 1, axis=0)
    nao = np.sum(m == -1, axis=0)
    tot = sim + nao
    minoria = np.minimum(sim, nao) / np.maximum(tot, 1)
    m = m[:, minoria >= 0.1]
    if m.shape[1] < 5 or m.shape[0] < 5:
        return {}

    media = np.nanmean(m, axis=0)
    c = np.where(np.isnan(m), 0.0, m - media)
    u, s, _ = np.linalg.svd(c, full_matrices=False)
    eixo = u[:, 0] * s[0]
    # normaliza pela quantidade de votos de cada um, para não puxar quem votou pouco
    n = np.maximum((~np.isnan(m)).sum(axis=1), 1)
    eixo = eixo / np.sqrt(n)

    dir_ = [eixo[i] for i, p in enumerate(pols) if partido_de.get(p, "").upper() in REFERENCIA_DIREITA]
    esq = [eixo[i] for i, p in enumerate(pols) if partido_de.get(p, "").upper() in {x.upper() for x in REFERENCIA_ESQUERDA}]
    if dir_ and esq and np.mean(dir_) < np.mean(esq):
        eixo = -eixo
    lim = np.percentile(np.abs(eixo), 98) or 1.0
    eixo = np.clip(eixo / lim, -1, 1)
    return {p: round(float(x), 3) for p, x in zip(pols, eixo)}


def rotulo(pos: float | None) -> str:
    if pos is None:
        return "Sem dados suficientes"
    if pos <= -0.5:
        return "Esquerda"
    if pos <= -0.15:
        return "Centro-esquerda"
    if pos < 0.15:
        return "Centro"
    if pos < 0.5:
        return "Centro-direita"
    return "Direita"


def alinhamento_governo(votos: list[dict], votacoes: list[dict]) -> dict[str, float]:
    """Percentual de votos iguais à orientação do governo (quando o governo orientou Sim ou Não)."""
    gov = {}
    for v in votacoes:
        for sigla, o in (v.get("orientacoes") or {}).items():
            if sigla.strip().lower().startswith("gov") and o in ("Sim", "Não"):
                gov[v["id"]] = o
    acertos, total = defaultdict(int), defaultdict(int)
    for v in votos:
        g = gov.get(v["votacao"])
        if g and v["voto"] in ("Sim", "Não"):
            total[v["politico"]] += 1
            acertos[v["politico"]] += v["voto"] == g
    return {p: round(acertos[p] / total[p], 3) for p in total if total[p] >= MIN_VOTOS}


def campo(alinh: float | None) -> str:
    if alinh is None:
        return "Sem dados"
    if alinh >= 0.7:
        return "Base do governo"
    if alinh <= 0.35:
        return "Oposição"
    return "Independente"
