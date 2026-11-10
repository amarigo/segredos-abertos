"""Média da Casa para mostrar ao lado de cada número do perfil (meta.json, chave "medias_casa").

Por que não a média simples de todos: na legislatura passam pela Câmara mais de 900 pessoas para 513 vagas. Um
suplente que ficou dois meses gasta pouco e puxa a média para baixo: em 2025 a média de todos com cota foi cerca de
R$ 350 mil, e a dos deputados que usaram a cota o ano inteiro, cerca de R$ 470 mil. Comparar um deputado que ficou o
ano todo com a média de todos faria parecer que ele gasta muito mais do que gasta.

Regras (as mesmas para Câmara e Senado):
- Dinheiro e equipe (cota, custo conhecido, verba de gabinete, pessoas na equipe): média de quem ficou o período
  inteiro, contado pelos meses com nota da cota ("meses_com_nota" em cada ano do político). Fica o período inteiro
  quem tem nota em todos os meses do período, com folga de um mês (um mês sem nota não tira ninguém).
  O site usa a média por mês (media / meses) para comparar quem ficou só parte do ano.
- Taxas (presença no Plenário, voto igual ao partido, voto igual ao governo): média de todos que têm a taxa, porque
  a taxa já não depende de quanto tempo a pessoa ficou.

Cada média leva "n", quantos políticos entraram na conta, para o rótulo do site dizer exatamente de quem é a média.
"""
from __future__ import annotations

import datetime as dt

from .ideologia import MIN_VOTOS

FOLGA_MESES = 1


def meses_do_periodo(despesas: list[dict], anos: list[int], hoje: dt.date | None = None) -> dict[str, int]:
    """Quantos meses cada ano tem até agora: 12 nos anos fechados; no ano em andamento, até o último mês com nota,
    sem contar o mês que ainda não acabou (mesma regra de build.mesmo_periodo)."""
    hoje = hoje or dt.date.today()
    out: dict[str, int] = {}
    for ano in anos:
        meses = [d["mes"] for d in despesas if d["ano"] == ano and 1 <= (d.get("mes") or 0) <= 12]
        ate = max(meses) if meses else 12
        if ano == hoje.year:
            ate = min(ate, hoje.month - 1)
        elif ano < hoje.year:
            ate = 12
        out[str(ano)] = max(ate, 1)
    return out


def meses_com_nota(despesas: list[dict], ano: int, ate: int) -> int:
    """Em quantos meses do período (1 até `ate`) há pelo menos uma nota da cota."""
    return len({d["mes"] for d in despesas if d["ano"] == ano and 1 <= (d.get("mes") or 0) <= ate})


def periodo_inteiro(meses: int | None, periodo: int) -> bool:
    return (meses or 0) >= max(periodo - FOLGA_MESES, 1)


def taxa_presenca(plenario: list | None) -> float | None:
    t = sum(plenario) if plenario else 0
    return plenario[0] / t if t else None


def _media(xs: list[float], casas: int = 2) -> dict | None:
    return {"media": round(sum(xs) / len(xs), casas), "n": len(xs)} if xs else None


def medias_da_casa(resumo: list[dict], meses: dict[str, int]) -> dict:
    """{"folga_meses": 1, "anos": {ano: {casa: {"meses": n, "total": {media, n}, ...}}}, "votos": {casa: {...}}}"""
    out: dict = {"folga_meses": FOLGA_MESES, "anos": {}, "votos": {}}
    for a, periodo in sorted(meses.items()):
        out["anos"][a] = {}
        for casa in ("camara", "senado"):
            linhas = [r["por_ano"][a] for r in resumo if r["casa"] == casa and a in (r.get("por_ano") or {})]
            cheio = [x for x in linhas if periodo_inteiro(x.get("meses_com_nota"), periodo)]
            taxas = [t for t in (taxa_presenca((x.get("atuacao") or {}).get("plenario")) for x in linhas) if t is not None]
            d = {
                "total": _media([x["total"] for x in cheio]),
                "custo_total": _media([x["custo_total"] for x in cheio if x.get("custo_total")]),
                "verba_gabinete": _media([x["verba_gabinete"] for x in cheio if x.get("verba_gabinete")]),
                "n_pessoal": _media([x["n_pessoal"] for x in cheio if x.get("n_pessoal")], 1),
                "presenca_plenario": _media(taxas, 4),
            }
            d = {k: v for k, v in d.items() if v is not None}
            if d:
                out["anos"][a][casa] = {"meses": periodo, **d}
    for casa in ("camara", "senado"):
        rs = [r for r in resumo if r["casa"] == casa]
        d = {"fidelidade_partido": _media([r["fidelidade_partido"] for r in rs if r.get("fidelidade_partido") is not None], 4),
             "alinhamento_governo": _media([r["alinhamento_governo"] for r in rs if r.get("alinhamento_governo") is not None], 4)}
        d = {k: v for k, v in d.items() if v is not None}
        if d:
            out["votos"][casa] = {"min_votos": MIN_VOTOS, **d}  # só tem taxa quem teve pelo menos MIN_VOTOS votos
    return out
