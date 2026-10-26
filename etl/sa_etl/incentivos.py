"""Dinheiro público para empresas e entidades: o que recebem e o que deixam de pagar.

Junta três fontes oficiais, todas do Portal da Transparência (CGU):
- Pagamentos do governo federal a empresas e entidades (arquivos diários de despesas; ver pagamentos.ler_geral):
  compras, obras e serviços, repasses a entidades (convênios, auxílios, subvenções sociais) e subsídios.
- Renúncia fiscal por empresa (dados da Receita Federal; ver renuncias.py): o imposto que deixou de ser cobrado.
- Pagamentos feitos com dinheiro de emendas (pagamentos.resumir): o único caso em que o dinheiro tem o nome de
  um parlamentar. Daí saem os gráficos de quem deu mais, por político, partido e estado.

Grava data/incentivos/indice.json, data/incentivos/{ano}.json (pagamentos e emendas, pelo ano do pagamento) e
data/incentivos/renuncia-{ano}.json (pelo ano-calendário da Receita).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

from . import emendas, pagamentos, renuncias
from .cnpj import chave_dono
from .util import write_json

log = logging.getLogger("sa_etl.incentivos")

N_TOP = 300
N_RECEITA_PAG = 400  # quantos dos que mais receberam buscamos na Receita (donos, natureza, UF)
N_RECEITA_REN = 300
FONTES = {
    "pagamentos": "https://portaldatransparencia.gov.br/download-de-dados/despesas",
    "renuncias": renuncias.FONTE,
    "emendas": "https://portaldatransparencia.gov.br/emendas",
    "receita": "https://minhareceita.org",
    "pessoa_juridica": "https://portaldatransparencia.gov.br/pessoa-juridica/{cnpj}",
}


def _top(d: dict, n: int) -> list:
    return [[k, round(v, 2)] for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:n] if v]


def cnpjs_para_receita(geral: dict | None, ren: dict | None) -> list[str]:
    """Os que mais receberam pagamentos (somando os anos) e os que mais deixaram de pagar (anos mais recentes)."""
    soma: dict[str, float] = defaultdict(float)
    for por in ((geral or {}).get("anos") or {}).values():
        for doc, e in por.items():
            soma[doc] += e["valor"]
    alvo = [c for c, _ in sorted(soma.items(), key=lambda kv: -kv[1])[:N_RECEITA_PAG]]
    ren_soma: dict[str, float] = defaultdict(float)
    for doc, por_ano in ((ren or {}).get("empresas") or {}).items():
        for x in por_ano.values():
            ren_soma[doc] += x["valor"]
    vistos = set(alvo)
    alvo += [c for c, _ in sorted(ren_soma.items(), key=lambda kv: -kv[1])[:N_RECEITA_REN] if c not in vistos]
    return alvo


class Receita:
    """O que sabemos de cada CNPJ pela Receita: tipo (empresa, entidade, público), UF e donos."""

    def __init__(self, emps: dict[str, dict], comuns: dict[str, list[str]] | None = None):
        self.emps = emps
        self.comuns = comuns or {}

    def tipo(self, doc: str) -> str:
        return emendas.tipo_pela_receita(self.emps.get(doc)) or "sem_dados"

    def uf(self, doc: str) -> str:
        return (self.emps.get(doc) or {}).get("uf") or ""

    def donos(self, doc: str) -> list[str]:
        return [s["nome"] for s in (self.emps.get(doc) or {}).get("socios", []) if s.get("nome")][:3]

    def n_outras(self, doc: str, no_site: set[str]) -> int:
        """Quantas outras empresas com página no site têm algum dono em comum com esta."""
        outras: set[str] = set()
        for s in (self.emps.get(doc) or {}).get("socios", []):
            outras |= set(self.comuns.get(chave_dono(s), []))
        return len((outras & no_site) - {doc})


def montar_pagamentos(por: dict[str, dict], cob: dict, rec: Receita, paginas: set[str]) -> dict:
    """Um ano de pagamentos a empresas e entidades. Ficam de fora os que a Receita diz serem órgãos ou empresas públicas."""
    publicos = {d for d in por if rec.tipo(d) == "publico"}
    itens = [(d, e) for d, e in por.items() if d not in publicos]
    itens.sort(key=lambda kv: -kv[1]["valor"])
    cats, orgs = defaultdict(lambda: [0.0, 0]), defaultdict(float)
    tipos = defaultdict(lambda: [0.0, 0])
    ufs = defaultdict(lambda: [0.0, 0])
    for d, e in itens:
        for c, v in e["cats"].items():
            cats[c][0] += v
            cats[c][1] += 1
        for o, v in e["orgaos"].items():
            orgs[o] += v
    for d, e in itens[:N_RECEITA_PAG]:  # tipo e UF: só de quem buscamos na Receita
        t = rec.tipo(d)
        tipos[t][0] += e["valor"]
        tipos[t][1] += 1
        u = rec.uf(d) or "Não identificado"
        ufs[u][0] += e["valor"]
        ufs[u][1] += 1
    total = sum(e["valor"] for _, e in itens)
    return {
        "total": round(total, 2), "n": len(itens), "cobertura": cob,
        "fora_publicos": round(sum(por[d]["valor"] for d in publicos), 2),
        "por_categoria": [{"cat": c, "rotulo": pagamentos.CATEGORIAS_GERAL[c], "valor": round(x[0], 2), "n": x[1]}
                          for c, x in sorted(cats.items(), key=lambda kv: -kv[1][0])],
        "orgaos": _top(orgs, 20),
        "top_n_receita": min(N_RECEITA_PAG, len(itens)),
        "por_tipo": [{"tipo": t, "valor": round(x[0], 2), "n": x[1]} for t, x in sorted(tipos.items(), key=lambda kv: -kv[1][0])],
        "por_uf": [[u, round(x[0], 2), x[1]] for u, x in sorted(ufs.items(), key=lambda kv: -kv[1][0])],
        "top": [{"cnpj": d, "nome": emendas.bonito((rec.emps.get(d) or {}).get("razao_social") or e["nome"]), "tipo": rec.tipo(d),
                 "uf": rec.uf(d), "valor": round(e["valor"], 2), "n": e["n"], "cats": _top(e["cats"], 4), "orgaos": _top(e["orgaos"], 3),
                 "donos": rec.donos(d), "n_outras": rec.n_outras(d, paginas), "pagina": d in paginas}
                for d, e in itens[:N_TOP]],
    }


def montar_emendas(pg: dict, nomes: dict[str, dict], rec: Receita, paginas: set[str]) -> dict:
    """Quem deu mais: pagamentos de emendas a empresas e entidades, por parlamentar, partido e estado."""
    brutos = {k: a["nome"] for k, a in pg["autores"].items()}
    favs = {d: f for d, f in pg["favorecidos"].items() if rec.tipo(d) != "publico"}
    autores: dict[str, dict] = {}
    for d, f in favs.items():
        for k, v in f["autores"].items():
            a = autores.setdefault(k, {"valor": 0.0, "recebedores": {}})
            a["valor"] += v
            a["recebedores"][d] = a["recebedores"].get(d, 0.0) + v
    politicos, coletivos = [], []
    partidos = defaultdict(lambda: {"valor": 0.0, "n": 0})
    ufs = defaultdict(lambda: [0.0, 0])
    sem_partido = 0.0
    for k, a in sorted(autores.items(), key=lambda kv: -kv[1]["valor"]):
        n = nomes.get(k) or {}
        nome = n.get("nome") or emendas.nome_autor(brutos.get(k, k))[1]
        top = [[emendas.bonito((rec.emps.get(d) or {}).get("razao_social") or favs[d]["nome"]), d, round(v, 2), d in paginas]
               for d, v in sorted(a["recebedores"].items(), key=lambda kv: -kv[1])[:5]]
        item = {"nome": nome, "valor": round(a["valor"], 2), "n": len(a["recebedores"]), "recebedores": top}
        if emendas.autor_coletivo(brutos.get(k, k), "outro"):
            coletivos.append(item)
            continue
        item.update({"politico": n.get("politico"), "partido": n.get("partido", ""), "uf": n.get("uf", ""), "casa": n.get("casa", "")})
        politicos.append(item)
        if item["partido"]:
            partidos[item["partido"]]["valor"] += a["valor"]
            partidos[item["partido"]]["n"] += 1
        else:
            sem_partido += a["valor"]
        u = item["uf"] or "Não identificado"
        ufs[u][0] += a["valor"]
        ufs[u][1] += 1
    rec_ufs = defaultdict(lambda: [0.0, 0])
    for d, f in favs.items():
        u = rec.uf(d) or "Não identificado"
        rec_ufs[u][0] += f["valor"]
        rec_ufs[u][1] += 1
    ordem = sorted(favs.items(), key=lambda kv: -kv[1]["valor"])

    def autor(k: str) -> dict:
        n = nomes.get(k) or {}
        return {"nome": n.get("nome") or emendas.nome_autor(brutos.get(k, k))[1], "politico": n.get("politico"), "partido": n.get("partido", "")}
    return {
        "total": round(sum(f["valor"] for f in favs.values()), 2), "n": len(favs),
        "politicos": politicos[:600], "n_politicos": len(politicos), "coletivos": coletivos[:40],
        "partidos": [{"sigla": s, "valor": round(x["valor"], 2), "n": x["n"]} for s, x in sorted(partidos.items(), key=lambda kv: -kv[1]["valor"])],
        "sem_partido": round(sem_partido, 2),
        "por_uf_politico": [[u, round(x[0], 2), x[1]] for u, x in sorted(ufs.items(), key=lambda kv: -kv[1][0])],
        "por_uf_recebedor": [[u, round(x[0], 2), x[1]] for u, x in sorted(rec_ufs.items(), key=lambda kv: -kv[1][0])],
        "top": [{"cnpj": d, "nome": emendas.bonito((rec.emps.get(d) or {}).get("razao_social") or f["nome"]), "tipo": rec.tipo(d),
                 "uf": rec.uf(d), "valor": round(f["valor"], 2), "n": f["n"],
                 "autores": [{**autor(k), "valor": round(v, 2)} for k, v in sorted(f["autores"].items(), key=lambda kv: -kv[1])[:3]],
                 "donos": rec.donos(d), "n_outras": rec.n_outras(d, paginas), "pagina": d in paginas}
                for d, f in ordem[:N_TOP]],
    }


def paginas_de(geral: dict | None, ren: dict | None, emps: dict[str, dict]) -> set[str]:
    """CNPJs que ganham página no site (com donos) por causa desta página: os buscados na Receita que não são públicos
    nos pagamentos; na renúncia, também as estatais (elas deixam de pagar imposto como qualquer empresa)."""
    alvo = set(cnpjs_para_receita(geral, ren))
    ren_docs = set(((ren or {}).get("empresas") or {}))
    return {d for d in alvo if d in emps and (emendas.tipo_pela_receita(emps[d]) != "publico" or d in ren_docs)}


def por_empresa(geral: dict | None, ren: dict | None, docs: set[str]) -> dict[str, dict]:
    """Para a página de cada empresa: pagamentos do governo federal e renúncia fiscal, por ano."""
    out: dict[str, dict] = {}
    for ano, por in sorted(((geral or {}).get("anos") or {}).items()):
        for d in docs & set(por):
            e = por[d]
            g = out.setdefault(d, {}).setdefault("governo", {"total": 0.0, "por_ano": {}, "cats": defaultdict(float), "orgaos": defaultdict(float)})
            g["total"] += e["valor"]
            g["por_ano"][str(ano)] = round(e["valor"], 2)
            for c, v in e["cats"].items():
                g["cats"][c] += v
            for o, v in e["orgaos"].items():
                g["orgaos"][o] += v
    for d in docs:
        por_ano = ((ren or {}).get("empresas") or {}).get(d)
        if por_ano:
            bens: dict[str, float] = defaultdict(float)
            for x in por_ano.values():
                for b, v in x["beneficios"]:
                    bens[b] += v
            out.setdefault(d, {})["renuncia"] = {"total": round(sum(x["valor"] for x in por_ano.values()), 2),
                                                 "por_ano": {str(a): x["valor"] for a, x in sorted(por_ano.items())},
                                                 "beneficios": _top(bens, 8), "fonte": renuncias.CONSULTA}
    for x in out.values():
        g = x.get("governo")
        if g:
            g["total"] = round(g["total"], 2)
            g["cats"] = [[pagamentos.CATEGORIAS_GERAL[c], round(v, 2)] for c, v in sorted(g["cats"].items(), key=lambda kv: -kv[1])]
            g["orgaos"] = _top(g["orgaos"], 6)
    return out


def gravar(saida: Path, anos: list[int], geral: dict | None, ren: dict | None, pag: dict | None, nomes: dict[str, dict],
           rec: Receita, paginas: set[str]) -> dict:
    pasta = saida / "incentivos"
    idx = {"anos": [], "anos_renuncia": [], "fontes": FONTES, "ate_emendas": (pag or {}).get("ate", "")}
    for ano in anos:
        por = ((geral or {}).get("anos") or {}).get(ano)
        pg = ((pag or {}).get("anos") or {}).get(ano)
        if not por and not pg:
            continue
        d = {"ano": ano,
             "pagamentos": montar_pagamentos(por, (geral or {}).get("cobertura", {}).get(ano, {}), rec, paginas) if por else None,
             "emendas": montar_emendas(pg, nomes, rec, paginas) if pg else None}
        write_json(pasta / f"{ano}.json", d)
        idx["anos"].append(ano)
    for ano, r in sorted(((ren or {}).get("anos") or {}).items()):
        for e in r["top"]:
            e["tipo"] = rec.tipo(e["cnpj"])
            e["donos"] = rec.donos(e["cnpj"])
            e["n_outras"] = rec.n_outras(e["cnpj"], paginas)
            e["pagina"] = e["cnpj"] in paginas
        write_json(pasta / f"renuncia-{ano}.json", {**r, "fonte": renuncias.FONTE, "url": renuncias.URLS[0].format(ano=ano)})
        idx["anos_renuncia"].append({"ano": ano, "total": r["total"], "parcial": r.get("parcial", False)})
    write_json(pasta / "indice.json", idx)
    log.info("Incentivos: anos %s, renúncia %s", idx["anos"], [x["ano"] for x in idx["anos_renuncia"]])
    return idx
