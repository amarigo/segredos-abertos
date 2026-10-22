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

from . import camara, cnpj, ideologia, passagens, recursos, senado, temas
from .categorias import GRUPOS
from .util import cnpj_valido, doc_kind, mask_cpf, write_json

log = logging.getLogger("sa_etl")


def coletar(anos: list[int], cache: Path, max_empresas: int, com_recursos: bool = True) -> dict:
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
        if cnpj_valido(d["doc"]):
            por_cnpj[d["doc"]] += d["valor"]
    alvo = [c for c, _ in por_cnpj.most_common(max_empresas)]
    emps = cnpj.empresas(alvo, cache / "cnpj")
    socias = cnpj.buscar_socias(emps, cache / "cnpj")  # holdings: sócios que são empresas
    rec = recursos.coletar(politicos, anos, cache / "recursos") if com_recursos else {}
    if rec:
        despesas += buscar_passagens(despesas, politicos, rec, cache / "passagens")
    return {"politicos": politicos, "despesas": despesas, "votacoes": vc + vs,
            "votos": votos_c + votos_s, "empresas": emps,
            "empresas_socias": socias, "recursos": rec}


SEM_NOTA = "Despesas sem nota nos dados abertos"
SUMARIO_MES = ("https://www.camara.leg.br/cota-parlamentar/sumarizado?nuDeputadoId={nu}&dataInicio={mes}/{ano}&dataFim={mes}/{ano}"
               "&despesa=&nomeHospede=&nomePassageiro=&nomeFornecedor=&cnpjFornecedor=&numDocumento=&sguf=&filtroNivel1=1&filtroNivel2=2&filtroNivel3=3")


def meses_faltando(despesas: list[dict], politicos: list[dict], rec: dict) -> dict[tuple[str, int, int], float]:
    """(deputado, ano, mês) em que a página oficial da Câmara soma mais do que as notas que temos, e quanto falta."""
    soma = defaultdict(float)
    for d in despesas:
        soma[(d["politico"], d["ano"], d["mes"])] += d["valor"]
    out = {}
    for p in politicos:
        if p["casa"] != "camara":
            continue
        for ano, r in (rec.get(p["id"]) or {}).items():
            for m in (r or {}).get("cota_meses") or []:
                falta = round(m["valor"] - soma[(p["id"], int(ano), m["mes"])], 2)
                if falta > 1:
                    out[(p["id"], int(ano), m["mes"])] = falta
    return out


def buscar_passagens(despesas: list[dict], politicos: list[dict], rec: dict, cache: Path) -> list[dict]:
    """Nos meses em que falta valor, busca as passagens na lista oficial da Câmara (ver passagens.py)."""
    nu_de = {}
    for d in despesas:
        if d.get("nu"):
            nu_de.setdefault(d["politico"], d["nu"])
    falta = meses_faltando(despesas, politicos, rec)
    meses = [(pid, nu_de[pid], ano, mes) for (pid, ano, mes) in sorted(falta) if pid in nu_de]
    pids = {m[0] for m in meses}
    return passagens.coletar(meses, [d for d in despesas if d["politico"] in pids], falta, cache)


def completar_com_oficial(despesas: list[dict], politicos: list[dict], rec: dict) -> list[dict]:
    """Acrescenta o que a página oficial da Câmara mostra a mais que as notas publicadas, mês a mês.

    Os dados abertos da Câmara não trazem todas as despesas que a página de cada deputado soma. Na
    conferência com Minas Gerais, a diferença era toda de passagens aéreas compradas pelo sistema da
    própria Câmara (SIGEPA), a partir de agosto de 2025. Sem isso, o total ficaria menor que o oficial.
    """
    nu_de = {}
    for d in despesas:
        if d.get("nu"):
            nu_de.setdefault(d["politico"], d["nu"])
    extras = []
    for (pid, ano, mes), falta in sorted(meses_faltando(despesas, politicos, rec).items()):
        nu = nu_de.get(pid)
        extras.append({"politico": pid, "ano": ano, "mes": mes, "data": f"{ano}-{mes:02d}-01",
                       "categoria": SEM_NOTA, "grupo": "pessoal", "fornecedor": "Diferença sem detalhe publicado",
                       "doc": "", "valor": falta, "sem_nota": True, "link": "lista" if nu else "",
                       "url": SUMARIO_MES.format(nu=nu, mes=mes, ano=ano) if nu else "",
                       "detalhe": "Valor que a página oficial soma neste mês e que não aparece em nenhuma nota nem na lista de despesas"})
    if extras:
        log.info("Câmara: %d meses completados com o valor oficial (R$ %.2f)", len(extras), sum(e["valor"] for e in extras))
    return despesas + extras


def salario_senadores(politicos: list[dict], rec: dict) -> dict:
    """O salário de senador é igual ao de deputado federal (mesmo subsídio). O Senado não o publica junto
    dos outros recursos, então usamos o valor pago aos deputados em cada mês (a mediana, que é o subsídio cheio)."""
    import statistics
    por_mes = defaultdict(list)
    for p in politicos:
        if p["casa"] == "camara":
            for ano, r in (rec.get(p["id"]) or {}).items():
                for m in (r or {}).get("salario_meses") or []:
                    por_mes[(int(ano), m["mes"])].append(m["valor"])
    if not por_mes:
        return rec
    subsidio = {k: round(statistics.median(v), 2) for k, v in por_mes.items()}
    out = dict(rec)
    for p in politicos:
        if p["casa"] != "senado":
            continue
        anos_p = {}
        for ano, r in (rec.get(p["id"]) or {}).items():
            meses = [{"mes": m, "valor": v} for (a, m), v in sorted(subsidio.items()) if a == int(ano)]
            anos_p[ano] = {**(r or {}), "salario_meses": meses, "salario_ano": round(sum(x["valor"] for x in meses), 2),
                           "salario_bruto": meses[-1]["valor"] if meses else None, "salario_estimado": True}
        out[p["id"]] = anos_p
    return out


def montar(dados: dict, saida: Path, anos: list[int]) -> None:
    politicos = dados["politicos"]
    despesas = completar_com_oficial(dados["despesas"], politicos, dados.get("recursos") or {})
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
    notas_emp = defaultdict(list)  # cnpj -> notas fiscais
    nome_forn: dict[str, str] = {}
    primeiro_pag: dict[str, str] = {}
    for d in despesas:
        if doc_kind(d["doc"]) == "cnpj":
            recebeu[d["doc"]][d["politico"]] += d["valor"]
            notas_emp[d["doc"]].append(d)
            nome_forn.setdefault(d["doc"], d["fornecedor"])
            if d["data"] and (d["doc"] not in primeiro_pag or d["data"] < primeiro_pag[d["doc"]]):
                primeiro_pag[d["doc"]] = d["data"]

    socias = dados.get("empresas_socias") or {}
    todas_emps = {**socias, **emps}
    comuns = cnpj.socios_em_comum(emps, socias)
    socio_empresas: dict[str, list[str]] = comuns
    vizinhas: dict[str, list[str]] = {}  # cnpj -> outras fornecedoras registradas no mesmo endereço
    for grupo in cnpj.mesmo_endereco(emps).values():
        for c in grupo:
            vizinhas[c] = [x for x in grupo if x != c]

    for v in votacoes:
        v["temas"] = temas.temas_da_votacao(v)
    votacao_por_id = {v["id"]: v for v in votacoes}
    rec_todos = salario_senadores(politicos, dados.get("recursos") or {})
    resumo = []
    for p in politicos:
        ds = desp_por.get(p["id"], [])
        rec = rec_todos.get(p["id"], {})
        por_ano, detalhe = {}, {}
        for ano in anos:
            d_ano = [d for d in ds if d["ano"] == ano]
            r = rec.get(ano) or rec.get(str(ano)) or {}
            if not d_ano and not r:
                continue
            det = gastos_do_ano(d_ano, emps)
            extra = custos_extras(p["casa"], r)
            extra.update(fora_do_periodo_oficial(d_ano, r))
            extra["custo_total"] = round(det["total"] + (extra["salario"] or 0) + (extra["verba_gabinete"] or 0)
                                         + (extra["outros_gastos"] or 0), 2)
            por_ano[str(ano)] = {"total": det["total"], "grupos": det["grupos"], **extra}
            detalhe[str(ano)] = {**det, "recursos": r or None, **extra}
        meus_votos = sorted(
            ({"votacao": v["votacao"], "voto": v["voto"],
              "partido": maioria_partido.get((v["votacao"], v["partido"]), "")}
             for v in votos_por_politico.get(p["id"], [])),
            key=lambda x: votacao_por_id[x["votacao"]]["data"], reverse=True)
        posicao = pos.get(p["id"])
        al = alinh.get(p["id"])
        fid = round(fiel[p["id"]] / tot[p["id"]], 3) if tot[p["id"]] >= ideologia.MIN_VOTOS else None
        base = {
            **p, "total": round(sum(x["total"] for x in por_ano.values()), 2), "por_ano": por_ano,
            "posicao": posicao, "rotulo": ideologia.rotulo(posicao),
            "alinhamento_governo": al, "campo": p.get("bloco") if p["casa"] == "senado" and al is None else ideologia.campo(al),
            "fidelidade_partido": fid, "n_votos": len(meus_votos),
        }
        resumo.append(base)
        por_tema = defaultdict(Counter)
        for v in meus_votos:
            for t in votacao_por_id[v["votacao"]]["temas"]:
                c = por_tema[t]
                c[v["voto"] if v["voto"] in ("Sim", "Não") else "Outros"] += 1
                if v["partido"] and v["voto"] in ("Sim", "Não") and v["voto"] != v["partido"]:
                    c["contra_partido"] += 1
        write_json(saida / "p" / f"{p['id']}.json", {**base, "anos": detalhe, "votos": meus_votos,
                                                     "temas": {t: dict(c) for t, c in sorted(por_tema.items())}})

    # médias por casa e ano, para comparação didática
    medias = {}
    for ano in anos:
        a = str(ano)
        medias[a] = {}
        for casa in ("camara", "senado"):
            ts = [r["por_ano"][a]["total"] for r in resumo if r["casa"] == casa and r["por_ano"].get(a, {}).get("total", 0) > 0]
            medias[a][casa] = round(sum(ts) / len(ts), 2) if ts else 0
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
                    "total": total, "n_politicos": len(quem), "tem_socios": bool(e and e["socios"]),
                    "n_mesmo_endereco": len(vizinhas.get(doc, []))}
        lista_emp.append(resumo_e)
        def outras_de(s: dict) -> list[dict]:
            return [{"cnpj": c, "nome": emps[c]["razao_social"], "total": round(sum(recebeu[c].values()), 2)}
                    for c in socio_empresas.get(cnpj.chave_dono(s), []) if c != doc and c in recebeu]
        socios = [{**s, "tipo": cnpj.tipo_socio(s), "outras_empresas": outras_de(s),
                   "doc": cnpj.cnpj_socio(s) if cnpj.tipo_socio(s) == "empresa" else s["doc"]}
                  for s in (e or {}).get("socios", [])]
        finais = cnpj.donos_finais(doc, todas_emps) if e else []
        tem_holding = any(d["cadeia"] for d in finais)
        donos = [{**d, "outras_empresas": outras_de(d) if d["fim"] == "pessoa" else []} for d in finais] if tem_holding else []
        resumo_e["tem_holding"] = tem_holding
        primeiro = primeiro_pag.get(doc, "")
        ns = sorted(notas_emp[doc], key=lambda n: (n["data"], n["valor"]), reverse=True)
        mensal = defaultdict(float)  # (politico, ano, mes) -> valor
        por_ano_notas = defaultdict(list)
        for n in ns:
            mensal[(n["politico"], n["ano"], n["mes"])] += n["valor"]
            por_ano_notas[n["ano"]].append([n["data"], n["politico"], n["categoria"], n["valor"], n["url"],
                                            n.get("link") or ("nota" if n["url"] else ""), n.get("detalhe", "")])
        for a, lista in por_ano_notas.items():  # todas as notas, num arquivo por ano (carregado só quando aberto)
            write_json(saida / "e" / "notas" / f"{doc}-{a}.json", lista)
        write_json(saida / "e" / f"{doc}.json", {
            "n_notas": len(ns),
            "notas_por_ano": {str(a): sum(1 for n in ns if n["ano"] == a) for a in sorted({n["ano"] for n in ns})},
            "por_mes": [{"politico": pid, "nome": por_id[pid]["nome"], "ano": a, "mes": m, "valor": round(v, 2)}
                        for (pid, a, m), v in sorted(mensal.items(), key=lambda kv: (kv[0][1], kv[0][2], -kv[1]))],
            **resumo_e, "empresa": {k: v for k, v in (e or {}).items() if k != "socios"} or None,
            "socios": socios, "donos_finais": donos, "pagadores": pagadores,
            "mesmo_endereco": [{"cnpj": c, "nome": emps[c]["razao_social"], "total": round(sum(recebeu[c].values()), 2),
                                "mesmos_socios": bool(cnpj.chaves_de_dono(c, todas_emps) & cnpj.chaves_de_dono(doc, todas_emps))}
                               for c in vizinhas.get(doc, []) if c in recebeu],
            "alertas": alertas(e, total, primeiro) + alertas_donos(donos) + ([
                f"Há outras {len(vizinhas[doc])} empresas fornecedoras registradas no mesmo endereço. Isso pode indicar o mesmo dono."
                if len(vizinhas[doc]) > 1 else
                "Há outra empresa fornecedora registrada no mesmo endereço. Isso pode indicar o mesmo dono."]
                if vizinhas.get(doc) else []),
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
        r["temas"] = v["temas"]
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
        anos_p = {}
        for ano in anos:
            a = str(ano)
            com = [r["por_ano"][a] for r in rs if a in r["por_ano"]]
            if not com:
                continue
            cota = round(sum(x["total"] for x in com), 2)
            todos = round(sum(x["custo_total"] for x in com), 2)
            anos_p[a] = {"n": len(com), "cota": cota, "cota_por_membro": round(cota / len(com), 2),
                         "custo_total": todos, "custo_por_membro": round(todos / len(com), 2)}
        partidos.append({"casa": casa, "sigla": sigla, "n": len(rs),
                         "posicao": round(sum(ps) / len(ps), 3) if ps else None,
                         "alinhamento_governo": round(sum(als) / len(als), 3) if als else None,
                         "fidelidade": round(sum(fs) / len(fs), 3) if fs else None,
                         "total": round(sum(r["total"] for r in rs), 2), "por_ano": anos_p})
    write_json(saida / "partidos.json", partidos)

    write_json(saida / "meta.json", {
        "atualizado_em": hoje, "anos": anos, "grupos": GRUPOS, "medias": medias,
        "contagens": {"politicos": len(politicos), "despesas": len(despesas), "votacoes": len(votacoes),
                      "empresas_com_socios": len(emps)},
        "total_gasto": round(sum(d["valor"] for d in despesas), 2),
        "total_por_ano": {str(a): round(sum(d["valor"] for d in despesas if d["ano"] == a), 2) for a in anos},
        "custo_por_ano": {str(a): round(sum(r["por_ano"].get(str(a), {}).get("custo_total", 0) for r in resumo), 2) for a in anos},
    })
    log.info("Pronto: %d políticos, %d despesas, %d votações, %d empresas", len(politicos), len(despesas),
             len(votacoes), len(lista_emp))


def gastos_do_ano(ds: list[dict], emps: dict) -> dict:
    """Resumo da cota de um político num ano: totais, categorias, meses, fornecedores e maiores notas."""
    grupos = {g: 0.0 for g in GRUPOS}
    cat = defaultdict(lambda: [0.0, ""])
    mes = defaultdict(float)
    forn = defaultdict(lambda: {"valor": 0.0, "n": 0, "nome": ""})
    for d in ds:
        grupos[d["grupo"]] += d["valor"]
        cat[d["categoria"]][0] += d["valor"]
        cat[d["categoria"]][1] = d["grupo"]
        mes[d["mes"]] += d["valor"]
        f = forn[d["doc"] or d["fornecedor"]]
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
    notas = sorted((d for d in ds if not d.get("sem_nota")), key=lambda d: -d["valor"])[:30]
    sem_nota = [{"mes": d["mes"], "valor": d["valor"], "url": d.get("url", "")} for d in sorted(ds, key=lambda d: d["mes"]) if d.get("sem_nota")]
    passagens_lista = [d for d in ds if d.get("fonte_lista")]
    return {
        "total": round(sum(d["valor"] for d in ds), 2),
        "grupos": {g: round(v, 2) for g, v in grupos.items()},
        "categorias": sorted(({"categoria": k, "grupo": g, "valor": round(v, 2)} for k, (v, g) in cat.items()),
                             key=lambda x: -x["valor"]),
        "meses": [{"mes": m, "valor": round(v, 2)} for m, v in sorted(mes.items())],
        "fornecedores": fornecedores,
        "sem_nota_meses": sem_nota,
        "passagens_da_lista": {"n": len(passagens_lista), "valor": round(sum(d["valor"] for d in passagens_lista), 2)},
        "maiores_notas": [{k: (mask_cpf(n["doc"]) if k == "doc" and doc_kind(n["doc"]) == "cpf" else n[k])
                           for k in ("data", "categoria", "fornecedor", "doc", "valor", "url")}
                          | {"link": n.get("link") or ("nota" if n["url"] else ""), "detalhe": n.get("detalhe", "")} for n in notas],
    }


def fora_do_periodo_oficial(ds: list[dict], r: dict) -> dict:
    """Notas de meses que a página oficial do ano não mostra.

    A página de cada deputado só conta os meses do mandato atual em que ele estava no cargo. Ficam de fora,
    por exemplo, janeiro de 2023 (ainda era a legislatura anterior) e devoluções de passagens que caem em meses
    em que o deputado estava licenciado (como ministro). As notas continuam na soma, porque foram pagas;
    este valor serve para comparar com a página oficial e explicar a diferença.
    """
    meses = {m["mes"] for m in (r or {}).get("cota_meses") or []}
    if not meses:
        return {}
    fora = defaultdict(float)
    for d in ds:
        if d["mes"] not in meses:
            fora[d["mes"]] += d["valor"]
    if not fora or abs(sum(fora.values())) < 0.01:
        return {}
    return {"fora_do_periodo": round(sum(fora.values()), 2), "meses_fora": sorted(fora)}


def custos_extras(casa: str, r: dict) -> dict:
    """Salário e verba de gabinete do ano (quando a fonte oficial informa) e o custo total conhecido."""
    salario = (r or {}).get("salario_ano") or 0
    verba = (r or {}).get("verba_gasto") or 0
    outros = (r or {}).get("outros_total") or 0  # Senado: gastos fora da cota (correios, diárias...)
    cota = (r or {}).get("cota_oficial")
    return {"salario": round(salario, 2) or None, "verba_gabinete": round(verba, 2) or None,
            "outros_gastos": round(outros, 2) or None, "cota_oficial": cota,
            "n_pessoal": (r or {}).get("n_pessoal")}


def alertas_donos(donos: list[dict]) -> list[str]:
    fins = {d["fim"] for d in donos}
    out = []
    if "estrangeiro" in fins:
        out.append("Parte da empresa pertence a alguém no exterior. A Receita não mostra quem está por trás de sócios estrangeiros.")
    if fins & {"sem_socios", "sem_dados"}:
        out.append("Parte da empresa pertence a outra empresa cujos sócios a Receita não informa (comum em sociedades anônimas). "
                   "Não foi possível chegar a todas as pessoas donas.")
    return out


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
    ap.add_argument("--anos", type=int, nargs="+", default=list(range(2023, dt.date.today().year + 1)))
    ap.add_argument("--sem-recursos", action="store_true", help="não baixa salário, verba de gabinete e equipe")
    ap.add_argument("--max-empresas", type=int, default=1500)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    dados = coletar(a.anos, a.cache, a.max_empresas, not a.sem_recursos)
    montar(dados, a.saida, a.anos)


if __name__ == "__main__":
    main()
