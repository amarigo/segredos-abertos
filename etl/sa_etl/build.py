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

from . import (autorias, camara, cnpj, emendas, financas, ideologia, incentivos, links_notas, pagamentos, passagens, recursos,
               renuncias, senado, temas)
from .categorias import GRUPOS
from . import util
from .util import cnpj_valido, doc_kind, mask_cpf, write_json

log = logging.getLogger("sa_etl")


def coletar(anos: list[int], cache: Path, max_empresas: int, com_recursos: bool = True,
            cnpjs_emendas: list[str] | None = None) -> dict:
    """cnpjs_emendas: empresas pagas com emendas, para buscar os donos junto com as fornecedoras da cota."""
    util.AVISOS.clear()
    deps = sem_repetidos(camara.deputados(), "id")
    sens = sem_repetidos(senado.senadores(), "id")
    if not deps or not sens:
        # Sem a lista de parlamentares não há site: melhor falhar e manter no ar a versão anterior
        raise RuntimeError(f"Lista de parlamentares vazia (Câmara: {len(deps)}, Senado: {len(sens)})")
    politicos = deps + sens
    ids_c = {p["id"] for p in deps}
    ids_s = {p["id"] for p in sens}

    despesas = camara.despesas(anos, ids_c, cache) + senado.despesas(anos, ids_s, cache)
    vc, votos_c = camara.votacoes(anos, ids_c, cache)
    vs, votos_s = senado.votacoes(anos, ids_s, cache / "senado-votacoes")

    por_cnpj = Counter()
    for d in despesas:
        if cnpj_valido(d["doc"]):
            por_cnpj[d["doc"]] += d["valor"]
    alvo = [c for c, _ in por_cnpj.most_common(max_empresas)]
    alvo += [c for c in cnpjs_emendas or [] if c not in set(alvo) and cnpj_valido(c)]
    emps = cnpj.empresas(alvo, cache / "cnpj")
    socias = cnpj.buscar_socias(emps, cache / "cnpj")  # holdings: sócios que são empresas
    rec = recursos.coletar(politicos, anos, cache / "recursos") if com_recursos else {}
    aut = autorias.coletar(politicos, anos, cache / "autorias") if com_recursos else {}
    if rec:
        despesas += buscar_passagens(despesas, politicos, rec, cache / "passagens")
    try:
        links_notas.conferir(despesas, cache)
    except Exception as e:  # noqa: BLE001 - sem a conferência, os links ficam como a Câmara publicou
        log.warning("Não foi possível conferir os links das notas: %s", e)
    return {"politicos": politicos, "despesas": despesas, "votacoes": vc + vs,
            "votos": votos_c + votos_s, "empresas": emps,
            "empresas_socias": socias, "recursos": rec, "autorias": aut}


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


def sem_repetidos(itens: list[dict], *chaves: str) -> list[dict]:
    """Remove itens repetidos (mesma chave), mantendo o primeiro. As APIs às vezes repetem linhas ao paginar."""
    vistos, out = set(), []
    for x in itens:
        k = tuple(x.get(c) for c in chaves)
        if k not in vistos:
            vistos.add(k)
            out.append(x)
    return out


def montar(dados: dict, saida: Path, anos: list[int]) -> None:
    politicos = sem_repetidos(dados["politicos"], "id")
    por_id = {p["id"]: p for p in politicos}
    despesas = [d for d in dados["despesas"] if d["ano"] in anos and d["politico"] in por_id]
    if len(despesas) != len(dados["despesas"]):  # uma linha de outro ano no arquivo deixaria os totais do site sem bater
        log.warning("Despesas: %d fora dos anos pedidos ou de parlamentar desconhecido foram descartadas",
                    len(dados["despesas"]) - len(despesas))
    despesas = completar_com_oficial(despesas, politicos, dados.get("recursos") or {})
    votacoes = sem_repetidos(dados["votacoes"], "id")
    ids_v = {v["id"] for v in votacoes}
    # um voto por parlamentar em cada votação, e só de votações e parlamentares conhecidos
    votos = [v for v in sem_repetidos(dados["votos"], "votacao", "politico")
             if v["votacao"] in ids_v and v["politico"] in por_id]
    if len(votos) != len(dados["votos"]):
        log.warning("Votos: %d repetidos ou sem votação/parlamentar conhecido foram descartados", len(dados["votos"]) - len(votos))
    emps = dados["empresas"]
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

    emd = dados.get("emendas_empresas") or {}  # cnpj -> o que recebeu de emendas (pagamentos.por_empresa)
    inc = dados.get("incentivos_empresas") or {}  # cnpj -> pagamentos do governo federal e renúncia fiscal (incentivos.py)
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
    autorias_todas = dados.get("autorias") or {}
    resumo = []
    for p in politicos:
        ds = desp_por.get(p["id"], [])
        rec = rec_todos.get(p["id"], {})
        por_ano, detalhe = {}, {}
        pres_senado = presenca_por_votos(votos_por_politico.get(p["id"], []), votacao_por_id) if p["casa"] == "senado" else {}
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
            atuacao = dict(r.get("atuacao") or {})
            aut = autorias_todas.get(p["id"], {})
            atuacao.update(aut.get(ano) or aut.get(str(ano)) or {})
            if p["casa"] == "senado" and sum(pres_senado.get(ano, [])):
                atuacao["plenario"] = pres_senado[ano]
                atuacao["votacoes"] = pres_senado[ano][0]
            if atuacao:
                extra["atuacao"] = atuacao
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
    no_site = set(recebeu) | set(emd) | set(inc)
    for doc in list(recebeu) + [c for c in emd if c not in recebeu] + [c for c in inc if c not in recebeu and c not in emd]:
        quem = recebeu.get(doc, {})
        total = round(sum(quem.values()), 2)
        de_emendas = emd.get(doc)
        e = emps.get(doc)
        pagadores = sorted(({"politico": pid, "nome": por_id[pid]["nome"], "partido": por_id[pid]["partido"],
                             "uf": por_id[pid]["uf"], "valor": round(v, 2)} for pid, v in quem.items()),
                           key=lambda x: -x["valor"])
        # Cota recebida em cada ano, para as listas mostrarem o ano escolhido no site (o total de todos os anos fica em segundo plano)
        cota_ano = defaultdict(lambda: [0.0, set()])
        for n in notas_emp[doc]:
            cota_ano[str(n["ano"])][0] += n["valor"]
            cota_ano[str(n["ano"])][1].add(n["politico"])
        resumo_e = {"cnpj": doc, "nome": (e or {}).get("razao_social") or nome_forn.get(doc, "") or (de_emendas or {}).get("nome", ""),
                    "total": total, "n_politicos": len(quem), "tem_socios": bool(e and e["socios"]),
                    "por_ano": {a: {"valor": round(v, 2), "n_politicos": len(ps)} for a, (v, ps) in sorted(cota_ano.items())},
                    "n_mesmo_endereco": len(vizinhas.get(doc, [])),
                    **_emd(emd, doc), **_inc(inc, doc)}
        if quem:  # a lista de empresas é a da cota; as pagas só com emendas aparecem na página de emendas
            lista_emp.append(resumo_e)
        def outras_de(s: dict) -> list[dict]:
            return [{"cnpj": c, "nome": emps[c]["razao_social"], "total": round(sum(recebeu.get(c, {}).values()), 2),
                     **_emd(emd, c), **_inc(inc, c)}
                    for c in socio_empresas.get(cnpj.chave_dono(s), []) if c != doc and c in no_site]
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
            "mesmo_endereco": [{"cnpj": c, "nome": emps[c]["razao_social"], "total": round(sum(recebeu.get(c, {}).values()), 2),
                                **_emd(emd, c), **_inc(inc, c),
                                "mesmos_socios": bool(cnpj.chaves_de_dono(c, todas_emps) & cnpj.chaves_de_dono(doc, todas_emps))}
                               for c in vizinhas.get(doc, []) if c in no_site],
            "emendas": {k: v for k, v in de_emendas.items() if k != "nome"} if de_emendas else None,
            "governo": (inc.get(doc) or {}).get("governo"), "renuncia": (inc.get(doc) or {}).get("renuncia"),
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
        "atualizado_em": hoje, "anos": anos, "avisos": list(util.AVISOS), "grupos": GRUPOS, "medias": medias,
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


PRESENTE = {"Sim", "Não", "Abstenção", "Presente sem votar", "Obstrução"}
AUSENCIA_JUSTIFICADA = {"Em missão", "Licença", "Em atividade parlamentar"}


def presenca_por_votos(votos: list[dict], votacao_por_id: dict) -> dict[int, list[int]]:
    """Senado: presença no Plenário contada pelas votações nominais. [presente, ausência justificada, não justificada]."""
    out: dict[int, list[int]] = defaultdict(lambda: [0, 0, 0])
    for v in votos:
        voto = v["voto"]
        i = (0 if voto in PRESENTE or voto.startswith("Presidente") else 1 if voto in AUSENCIA_JUSTIFICADA
             else 2 if voto == "Ausente" else None)
        if i is not None:
            out[int(votacao_por_id[v["votacao"]]["data"][:4])][i] += 1
    return out


def custos_extras(casa: str, r: dict) -> dict:
    """Salário e verba de gabinete do ano (quando a fonte oficial informa) e o custo total conhecido."""
    salario = (r or {}).get("salario_ano") or 0
    verba = (r or {}).get("verba_gasto") or 0
    outros = (r or {}).get("outros_total") or 0  # Senado: gastos fora da cota (correios, diárias...)
    cota = (r or {}).get("cota_oficial")
    return {"salario": round(salario, 2) or None, "verba_gabinete": round(verba, 2) or None,
            "outros_gastos": round(outros, 2) or None, "cota_oficial": cota,
            "n_pessoal": (r or {}).get("n_pessoal")}


def _emd(emd: dict, c: str) -> dict:
    """{"emendas": total} se a empresa recebeu pagamentos de emendas."""
    v = (emd.get(c) or {}).get("total", 0)
    return {"emendas": v} if v else {}


def _inc(inc: dict, c: str) -> dict:
    """{"governo": total, "renuncia": total} se a empresa recebeu pagamentos do governo federal ou teve renúncia fiscal."""
    x = inc.get(c) or {}
    return {k: x[k]["total"] for k in ("governo", "renuncia") if x.get(k) and x[k]["total"]}


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
    ap.add_argument("--sem-emendas", action="store_true", help="não baixa as emendas parlamentares (Portal da Transparência)")
    ap.add_argument("--minutos-pagamentos", type=float, default=45,
                    help="tempo máximo, por execução, para ler os arquivos diários de pagamentos das emendas")
    ap.add_argument("--sem-incentivos", action="store_true",
                    help="não monta a página de incentivos (pagamentos a empresas e renúncia fiscal)")
    ap.add_argument("--sem-financas", action="store_true",
                    help="não monta a aba de arrecadação e gastos do Brasil (Tesouro, Receita, Portal, IBGE)")
    ap.add_argument("--minutos-pagamentos-gerais", type=float, default=40,
                    help="tempo máximo, por execução, para completar os dias antigos dos pagamentos a empresas")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    executar(a.anos, a.cache, a.saida, max_empresas=a.max_empresas, com_recursos=not a.sem_recursos,
             com_emendas=not a.sem_emendas, com_incentivos=not a.sem_incentivos,
             minutos_pagamentos=a.minutos_pagamentos, minutos_gerais=a.minutos_pagamentos_gerais,
             com_financas=not a.sem_financas)


def executar(anos: list[int], cache: Path, saida: Path, max_empresas: int = 1500, com_recursos: bool = True,
             com_emendas: bool = True, com_incentivos: bool = True, minutos_pagamentos: float = 45,
             minutos_gerais: float = 40, com_financas: bool = True) -> None:
    """A coleta inteira, na ordem certa (usada também pelos testes)."""
    # A renúncia vem antes dos arquivos diários: o Portal passa a recusar downloads (HTTP 405) depois de muitos
    # pedidos seguidos, e os arquivos de renúncia são poucos (e ficam uma semana no cache)
    ren = coletar_renuncia(anos, cache) if com_incentivos else None
    # Depois, os dias mais recentes dos pagamentos a empresas (2026 primeiro), com um limite por execução para sobrar
    # downloads para os pagamentos das emendas, que precisam ser lidos em ordem, do mais antigo para o mais novo
    if com_incentivos:
        coletar_incentivos(anos, cache, minutos_gerais, max_dias=DIAS_RECENTES_POR_EXECUCAO)
    pag = pagamentos_emendas(anos, cache, minutos_pagamentos) if com_emendas else None
    inc = (coletar_incentivos(anos, cache, minutos_gerais), ren) if com_incentivos else None
    avisos = list(util.AVISOS)  # coletar() recomeça a lista de avisos
    dados = coletar(anos, cache, max_empresas, com_recursos,
                    cnpjs_emendas=pagamentos.cnpjs_empresas(pag) + incentivos.cnpjs_para_receita(*(inc or (None, None))))
    for x in avisos:
        util.avisar(x)
    if com_emendas:  # antes de montar(), para os avisos das emendas entrarem no meta.json
        juntar_emendas(dados, anos, cache, saida, pag)
    if inc:
        juntar_incentivos(dados, inc)
    montar(dados, saida, anos)
    if inc:
        gravar_incentivos(dados, saida, anos, inc, pag)
    if com_financas:  # depois de tudo: usa as emendas e a verba de gabinete já gravadas
        coletar_financas(saida, cache)


def coletar_financas(saida: Path, cache: Path) -> None:
    """Aba de arrecadação e gastos. Se falhar, o resto do site segue."""
    try:
        financas.coletar(saida, cache)
    except Exception:  # noqa: BLE001
        log.exception("Arrecadação e gastos: erro; a aba não foi atualizada")


def pagamentos_emendas(anos: list[int], cache: Path, minutos: float) -> dict | None:
    """Pagamentos feitos com dinheiro de emendas (arquivos diários do Portal). Se falhar, o resto do site segue."""
    try:
        return pagamentos.resumir(pagamentos.coletar(anos, cache / "pagamentos", minutos), anos)
    except Exception:  # noqa: BLE001
        log.exception("Pagamentos de emendas: erro; a página de emendas fica sem os documentos de pagamento")
        return None


def coletar_renuncia(anos: list[int], cache: Path) -> dict | None:
    try:
        return renuncias.coletar(cache / "renuncias", max(anos))
    except Exception:  # noqa: BLE001
        log.exception("Incentivos: erro na renúncia fiscal")
        util.avisar("Incentivos: a renúncia fiscal não foi atualizada")
        return None


DIAS_RECENTES_POR_EXECUCAO = 20


def coletar_incentivos(anos: list[int], cache: Path, minutos: float, max_dias: int | None = None) -> dict | None:
    """Pagamentos a empresas e entidades. Se falhar, o resto do site segue."""
    try:
        arqs = pagamentos.coletar_geral(anos, cache / "pagamentos", minutos, max_dias=max_dias)
        if max_dias is not None:
            return None
        geral = pagamentos.resumir_geral(arqs, anos)
        for ano, c in sorted(geral["cobertura"].items()):
            log.info("Pagamentos gerais %s: %s de %s dias lidos (%s a %s)", ano, c["dias"], c["dias_ano"], c["de"], c["ate"])
        return geral
    except Exception:  # noqa: BLE001
        log.exception("Incentivos: erro nos pagamentos a empresas")
        util.avisar("Incentivos: os pagamentos do governo federal a empresas não foram atualizados")
        return None


def juntar_incentivos(dados: dict, inc: tuple[dict | None, dict | None]) -> None:
    """Põe em dados["incentivos_empresas"] o que cada empresa recebeu do governo e deixou de pagar, para as páginas."""
    geral, ren = inc
    docs = incentivos.paginas_de(geral, ren, dados["empresas"])
    dados["incentivos_empresas"] = incentivos.por_empresa(geral, ren, docs)


def gravar_incentivos(dados: dict, saida: Path, anos: list[int], inc: tuple[dict | None, dict | None], pag: dict | None) -> None:
    """Depois de montar(): já sabemos quais empresas têm página e quais têm donos em comum."""
    try:
        emps, socias = dados["empresas"], dados.get("empresas_socias") or {}
        paginas = {f.stem for f in (saida / "e").glob("*.json")}
        rec = incentivos.Receita(emps, cnpj.socios_em_comum(emps, socias))
        incentivos.gravar(saida, anos, inc[0], inc[1], pag, dados.get("emendas_autores") or {}, rec, paginas)
    except Exception:  # noqa: BLE001
        log.exception("Incentivos: erro ao gravar a página")


def juntar_emendas(dados: dict, anos: list[int], cache: Path, saida: Path, pag: dict | None) -> None:
    """Grava as emendas e põe em dados["emendas_empresas"] as empresas pagas com emendas, para as páginas de empresa."""
    emps = dados["empresas"]
    alvo = pagamentos.cnpjs_empresas(pag)
    publicas = {c for c in alvo if emendas.tipo_pela_receita(emps.get(c)) == "publico"}
    da_cota = {d["doc"] for d in dados["despesas"]}
    for c in publicas - da_cota:  # prefeituras e órgãos públicos não entram na análise de donos
        emps.pop(c, None)
    paginas = set(alvo) - publicas
    r = emendas.coletar(dados["politicos"], anos, cache / emendas.PASTA_CACHE, saida, pag, emps, paginas)
    dados["emendas_autores"] = (r or {}).get("autores") or {}
    dados["emendas_empresas"] = pagamentos.por_empresa(pag, dados["emendas_autores"], paginas)


if __name__ == "__main__":
    main()
