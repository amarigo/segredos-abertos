"""Gera os arquivos JSON que o site lê.

Uso:
    python -m sa_etl.build --saida ../site/public/data --cache .cache --anos 2025 2026
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
from collections import Counter, defaultdict
from pathlib import Path

from . import camara, cnpj, ideologia, senado
from .categorias import GRUPOS
from .util import doc_kind, mask_cpf, write_json

log = logging.getLogger("sa_etl")


def coletar(anos: list[int], cache: Path, max_empresas: int) -> dict:
    deps = camara.deputados()
    sens = senado.senadores()
    politicos = deps + sens
    ids_c = {p["id"] for p in deps}
    ids_s = {p["id"] for p in sens}

    despesas = camara.despesas(anos, ids_c, cache) + senado.despesas(anos, ids_s)
    vc, votos_c = camara.votacoes(anos, ids_c, cache)
    vs, votos_s = senado.votacoes(anos, ids_s)

    por_cnpj = Counter()
    for d in despesas:
        if doc_kind(d["doc"]) == "cnpj":
            por_cnpj[d["doc"]] += d["valor"]
    alvo = [c for c, _ in por_cnpj.most_common(max_empresas)]
    emps = cnpj.empresas(alvo, cache / "cnpj")
    return {"politicos": politicos, "despesas": despesas, "votacoes": vc + vs,
            "votos": votos_c + votos_s, "empresas": emps}


def montar(dados: dict, saida: Path, anos: list[int]) -> None:
    politicos = dados["politicos"]
    despesas = dados["despesas"]
    votacoes = dados["votacoes"]
    votos = dados["votos"]
    emps = dados["empresas"]
    por_id = {p["id"]: p for p in politicos}
    partido_de = {p["id"]: p["partido"] for p in politicos}
    hoje = dt.date.today().isoformat()

    # ---------- Votos: posição, alinhamento, fidelidade ----------
    pos: dict[str, float] = {}
    for casa in ("camara", "senado"):
        vv = [v for v in votos if por_id[v["politico"]]["casa"] == casa]
        pos.update(ideologia.posicoes(vv, partido_de))
    alinh = ideologia.alinhamento_governo(votos, votacoes)

    votos_por_votacao = defaultdict(list)
    votos_por_politico = defaultdict(list)
    for v in votos:
        votos_por_votacao[v["votacao"]].append(v)
        votos_por_politico[v["politico"]].append(v)
    maioria_partido: dict[tuple[str, str], str] = {}
    for vid, vs in votos_por_votacao.items():
        cont = defaultdict(Counter)
        for v in vs:
            if v["voto"] in ("Sim", "Não"):
                cont[v["partido"]][v["voto"]] += 1
        for partido, c in cont.items():
            maioria_partido[(vid, partido)] = c.most_common(1)[0][0]
    fiel, tot = Counter(), Counter()
    for v in votos:
        m = maioria_partido.get((v["votacao"], v["partido"]))
        if m and v["voto"] in ("Sim", "Não"):
            tot[v["politico"]] += 1
            fiel[v["politico"]] += v["voto"] == m

    # ---------- Despesas ----------
    desp_por = defaultdict(list)
    for d in despesas:
        desp_por[d["politico"]].append(d)

    recebeu = defaultdict(lambda: defaultdict(float))  # cnpj -> politico -> valor
    nome_forn: dict[str, str] = {}
    primeiro_pag: dict[str, str] = {}
    for d in despesas:
        if doc_kind(d["doc"]) == "cnpj":
            recebeu[d["doc"]][d["politico"]] += d["valor"]
            nome_forn.setdefault(d["doc"], d["fornecedor"])
            if d["data"] and (d["doc"] not in primeiro_pag or d["data"] < primeiro_pag[d["doc"]]):
                primeiro_pag[d["doc"]] = d["data"]

    comuns = cnpj.socios_em_comum(emps)
    socio_empresas: dict[str, list[str]] = comuns

    votacao_por_id = {v["id"]: v for v in votacoes}
    resumo = []
    for p in politicos:
        ds = desp_por.get(p["id"], [])
        total = round(sum(d["valor"] for d in ds), 2)
        grupos = {g: 0.0 for g in GRUPOS}
        cat = defaultdict(lambda: [0.0, ""])
        mes = defaultdict(float)
        forn = defaultdict(lambda: {"valor": 0.0, "n": 0, "nome": ""})
        for d in ds:
            grupos[d["grupo"]] += d["valor"]
            cat[d["categoria"]][0] += d["valor"]
            cat[d["categoria"]][1] = d["grupo"]
            mes[(d["ano"], d["mes"])] += d["valor"]
            key = d["doc"] or d["fornecedor"]
            f = forn[key]
            f["valor"] += d["valor"]
            f["n"] += 1
            f["nome"] = f["nome"] or d["fornecedor"]
        fornecedores = []
        for key, f in sorted(forn.items(), key=lambda kv: -kv[1]["valor"])[:60]:
            kind = doc_kind(key)
            fornecedores.append({
                "doc": key if kind == "cnpj" else mask_cpf(key) if kind == "cpf" else "",
                "tipo": kind, "nome": f["nome"], "valor": round(f["valor"], 2), "n": f["n"],
                "ficha": kind == "cnpj",
                "socios": [s["nome"] for s in emps.get(key, {}).get("socios", [])][:4],
            })
        notas = sorted(ds, key=lambda d: -d["valor"])[:30]
        meus_votos = sorted(
            ({"votacao": v["votacao"], "voto": v["voto"],
              "partido": maioria_partido.get((v["votacao"], v["partido"]), "")}
             for v in votos_por_politico.get(p["id"], [])),
            key=lambda x: votacao_por_id[x["votacao"]]["data"], reverse=True)
        posicao = pos.get(p["id"])
        al = alinh.get(p["id"])
        fid = round(fiel[p["id"]] / tot[p["id"]], 3) if tot[p["id"]] >= ideologia.MIN_VOTOS else None
        base = {
            **p, "total": total,
            "grupos": {g: round(v, 2) for g, v in grupos.items()},
            "posicao": posicao, "rotulo": ideologia.rotulo(posicao),
            "alinhamento_governo": al, "campo": p.get("bloco") if p["casa"] == "senado" and al is None else ideologia.campo(al),
            "fidelidade_partido": fid, "n_votos": len(meus_votos),
        }
        resumo.append(base)
        write_json(saida / "p" / f"{p['id']}.json", {
            **base,
            "categorias": sorted(({"categoria": k, "grupo": g, "valor": round(v, 2)} for k, (v, g) in cat.items()),
                                 key=lambda x: -x["valor"]),
            "meses": [{"ano": a, "mes": m, "valor": round(v, 2)} for (a, m), v in sorted(mes.items())],
            "fornecedores": fornecedores,
            "maiores_notas": [{k: (mask_cpf(n["doc"]) if k == "doc" and doc_kind(n["doc"]) == "cpf" else n[k])
                               for k in ("data", "categoria", "fornecedor", "doc", "valor", "url")} for n in notas],
            "votos": meus_votos,
        })

    # médias por casa, para comparação didática
    medias = {}
    for casa in ("camara", "senado"):
        ts = [r["total"] for r in resumo if r["casa"] == casa and r["total"] > 0]
        medias[casa] = round(sum(ts) / len(ts), 2) if ts else 0
    write_json(saida / "politicos.json", resumo)

    # ---------- Empresas ----------
    lista_emp = []
    for doc, quem in recebeu.items():
        total = round(sum(quem.values()), 2)
        e = emps.get(doc)
        pagadores = sorted(({"politico": pid, "nome": por_id[pid]["nome"], "partido": por_id[pid]["partido"],
                             "uf": por_id[pid]["uf"], "valor": round(v, 2)} for pid, v in quem.items()),
                           key=lambda x: -x["valor"])
        resumo_e = {"cnpj": doc, "nome": (e or {}).get("razao_social") or nome_forn.get(doc, ""),
                    "total": total, "n_politicos": len(quem), "tem_socios": bool(e and e["socios"])}
        lista_emp.append(resumo_e)
        if e is None and total < 1000:
            continue
        socios = []
        for s in (e or {}).get("socios", []):
            outras = [c for c in socio_empresas.get(cnpj.chave_socio(s), []) if c != doc]
            socios.append({**s, "outras_empresas": [
                {"cnpj": c, "nome": emps[c]["razao_social"], "total": round(sum(recebeu[c].values()), 2)} for c in outras]})
        primeiro = primeiro_pag.get(doc, "")
        write_json(saida / "e" / f"{doc}.json", {
            **resumo_e, "empresa": {k: v for k, v in (e or {}).items() if k != "socios"} or None,
            "socios": socios, "pagadores": pagadores,
            "alertas": alertas(e, total, primeiro),
        })
    lista_emp.sort(key=lambda x: -x["total"])
    write_json(saida / "empresas.json", lista_emp[:1000])

    # ---------- Votações ----------
    lista_v = []
    for v in sorted(votacoes, key=lambda x: x["data"], reverse=True):
        vs = votos_por_votacao.get(v["id"], [])
        cont = Counter(x["voto"] for x in vs)
        por_partido = defaultdict(Counter)
        por_lado = defaultdict(Counter)
        for x in vs:
            por_partido[x["partido"]][x["voto"]] += 1
            por_lado[ideologia.rotulo(pos.get(x["politico"]))][x["voto"]] += 1
        r = {k: v[k] for k in ("id", "casa", "data", "descricao", "aprovada")}
        r["proposicao"] = v.get("proposicao")
        r["sim"], r["nao"] = cont.get("Sim", 0), cont.get("Não", 0)
        lista_v.append(r)
        write_json(saida / "v" / f"{v['id']}.json", {
            **v, "sim": r["sim"], "nao": r["nao"], "contagem": dict(cont),
            "por_partido": {k: dict(c) for k, c in sorted(por_partido.items())},
            "por_lado": {k: dict(c) for k, c in por_lado.items()},
            "votos": sorted(({"politico": x["politico"], "nome": por_id[x["politico"]]["nome"], "partido": x["partido"],
                              "uf": por_id[x["politico"]]["uf"], "voto": x["voto"],
                              "posicao": pos.get(x["politico"])} for x in vs), key=lambda y: y["nome"]),
        })
    write_json(saida / "votacoes.json", lista_v)

    # ---------- Partidos ----------
    part = defaultdict(list)
    for r in resumo:
        part[(r["casa"], r["partido"])].append(r)
    partidos = []
    for (casa, sigla), rs in sorted(part.items()):
        ps = [r["posicao"] for r in rs if r["posicao"] is not None]
        als = [r["alinhamento_governo"] for r in rs if r["alinhamento_governo"] is not None]
        fs = [r["fidelidade_partido"] for r in rs if r["fidelidade_partido"] is not None]
        partidos.append({"casa": casa, "sigla": sigla, "n": len(rs),
                         "posicao": round(sum(ps) / len(ps), 3) if ps else None,
                         "alinhamento_governo": round(sum(als) / len(als), 3) if als else None,
                         "fidelidade": round(sum(fs) / len(fs), 3) if fs else None,
                         "total": round(sum(r["total"] for r in rs), 2)})
    write_json(saida / "partidos.json", partidos)

    write_json(saida / "meta.json", {
        "atualizado_em": hoje, "anos": anos, "grupos": GRUPOS, "medias": medias,
        "contagens": {"politicos": len(politicos), "despesas": len(despesas), "votacoes": len(votacoes),
                      "empresas_com_socios": len(emps)},
        "total_gasto": round(sum(d["valor"] for d in despesas), 2),
    })
    log.info("Pronto: %d políticos, %d despesas, %d votações, %d empresas", len(politicos), len(despesas),
             len(votacoes), len(lista_emp))


def alertas(e: dict | None, total: float, primeiro_pagamento: str) -> list[str]:
    """Pontos de atenção objetivos. Não são acusação: servem para orientar quem quer olhar mais de perto."""
    if not e:
        return []
    out = []
    sit = (e.get("situacao") or "").upper()
    if sit and sit != "ATIVA":
        out.append(f"A empresa está com situação cadastral \"{e['situacao']}\" na Receita Federal.")
    try:
        cap = float(e.get("capital_social") or 0)
    except (TypeError, ValueError):
        cap = 0
    if 0 < cap < 10_000 and total > 100_000:
        out.append(f"Capital social de R$ {cap:,.0f} e recebeu R$ {total:,.0f} de parlamentares.".replace(",", "."))
    ab, pp = e.get("abertura") or "", primeiro_pagamento
    if ab and pp:
        try:
            dias = (dt.date.fromisoformat(pp[:10]) - dt.date.fromisoformat(ab[:10])).days
            if 0 <= dias < 180:
                out.append(f"A empresa foi aberta {dias} dias antes do primeiro pagamento registrado.")
        except ValueError:
            pass
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=Path(".cache"))
    ap.add_argument("--anos", type=int, nargs="+", default=[dt.date.today().year - 1, dt.date.today().year])
    ap.add_argument("--max-empresas", type=int, default=1500)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    dados = coletar(a.anos, a.cache, a.max_empresas)
    montar(dados, a.saida, a.anos)


if __name__ == "__main__":
    main()
