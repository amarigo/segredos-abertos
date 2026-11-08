"""Emendas federais que chegaram a cada cidade: qual deputado ou senador mandou, para quem e quanto foi pago.

Fonte: o mesmo arquivo do Portal da Transparência (CGU) que o coletor nacional baixa todo dia
(etl/.cache/EmendasParlamentares.zip), tabela "por favorecido": cada pagamento, com quem recebeu (prefeitura,
fundo municipal de saúde, hospital, associação...), o município de quem recebeu, o autor da emenda e o valor.

Só entram favorecidos com CNPJ (órgãos e entidades). Pagamentos a pessoas físicas não aparecem com nome nem número.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from pathlib import Path

from sa_etl import emendas as E
from sa_etl.util import digits, norm_name

from . import fontes

log = logging.getLogger("mg_etl.emendas_federais")

PAGINA = "https://portaldatransparencia.gov.br/emendas"
PAGINA_FAVORECIDO = "https://portaldatransparencia.gov.br/pessoa-juridica/{cnpj}"


def chave_cidade(nome: str) -> str:
    return re.sub(r"[^A-Z]", "", norm_name(nome))


def resumir(rows, cidades: dict[str, str], autores: dict[str, dict], uf: str = "MG") -> dict[str, dict]:
    """cidades: chave do município -> id; autores: nome do autor (chave) -> {nome, politico, partido}."""
    col = None
    acc: dict = defaultdict(lambda: {"anos": defaultdict(lambda: [0.0, 0]), "fav": defaultdict(lambda: {
        "nome": "", "cnpj": "", "valor": 0.0, "autores": defaultdict(float), "anos": set()}), "aut": defaultdict(lambda: [0.0, 0])})
    for r in rows:
        if col is None:
            col = E.achar_colunas(list(r.keys()), E.REGRAS_FAV)
            if not (col["valor"] and col["municipio"] and col["anomes"]):
                raise ValueError(f"arquivo de emendas sem as colunas esperadas ({col})")
        g = lambda k: (r.get(col[k]) or "").strip() if col.get(k) else ""  # noqa: E731
        if col.get("uf") and g("uf").upper() not in (uf, "MINAS GERAIS"):
            continue
        cid = cidades.get(chave_cidade(g("municipio")))
        if not cid:
            continue
        v = fontes.valor(g("valor"))
        am = digits(g("anomes"))
        if not v or len(am) < 6:
            continue
        ano = int(am[:4]) if am[:2] in ("19", "20") else int(am[-4:])
        doc = digits(g("doc"))
        cnpj = doc if len(doc) == 14 else ""
        nome = fontes.bonito(g("nome")) if cnpj else "Pessoa física"
        _, autor_nome = E.nome_autor(g("autor"))
        a = autores.get(E._chave(autor_nome)) or {}
        chave_aut = a.get("nome") or fontes.bonito(autor_nome) or "Não informado"
        d = acc[cid]
        d["anos"][ano][0] += v
        d["anos"][ano][1] += 1
        f = d["fav"][cnpj or "pf"]
        f["nome"], f["cnpj"] = f["nome"] or nome, cnpj
        f["valor"] += v
        f["autores"][chave_aut] += v
        f["anos"].add(ano)
        x = d["aut"][(chave_aut, a.get("politico") or "", a.get("partido") or "")]
        x[0] += v
        x[1] += 1
    out = {}
    for cid, d in acc.items():
        out[cid] = {
            "fonte": PAGINA,
            "por_ano": [{"ano": a, "valor": round(x[0], 2), "n": x[1]} for a, x in sorted(d["anos"].items(), reverse=True)],
            "favorecidos": [{"nome": f["nome"], "cnpj": f["cnpj"], "valor": round(f["valor"], 2),
                             "anos": sorted(f["anos"]), "url": PAGINA_FAVORECIDO.format(cnpj=f["cnpj"]) if f["cnpj"] else "",
                             "autores": [{"nome": k, "valor": round(v, 2)} for k, v in sorted(f["autores"].items(), key=lambda kv: -kv[1])[:6]]}
                            for f in sorted(d["fav"].values(), key=lambda f: -f["valor"])[:40]],
            "autores": [{"nome": k[0], "politico": k[1] or None, "partido": k[2], "valor": round(x[0], 2), "n": x[1]}
                        for k, x in sorted(d["aut"].items(), key=lambda kv: -kv[1][0])[:40]],
        }
    return out


def autores_nacionais(nacional: Path) -> dict[str, dict]:
    """Nome, partido e página (no site) de cada autor, dos arquivos de emendas que o coletor nacional já gerou."""
    import json
    out: dict[str, dict] = {}
    for f in sorted((nacional / "emendas").glob("[0-9]*.json"), reverse=True):  # o mais recente vale
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for a in (d.get("autores") or []) + (d.get("coletivos") or []):
            out.setdefault(E._chave(a.get("nome") or ""), {"nome": a.get("nome"), "politico": a.get("politico"),
                                                           "partido": a.get("partido") or ""})
    return out


def coletar(zip_nacional: Path, nacional: Path, cidades: dict[str, str], ids_mg: set[str]) -> dict[str, dict] | None:
    """ids_mg: políticos com página no Minas Nossa (os outros autores aparecem sem link)."""
    if not zip_nacional.exists():
        log.warning("Emendas federais: arquivo do Portal da Transparência não encontrado em %s", zip_nacional)
        fontes.avisar("Emendas federais nas cidades: o arquivo do Portal da Transparência não estava disponível")
        return None
    autores = autores_nacionais(nacional)
    for a in autores.values():
        if a.get("politico") not in ids_mg:
            a["politico"] = None
    try:
        return resumir(E.linhas(zip_nacional, "favorecido"), cidades, autores)
    except Exception as e:  # noqa: BLE001
        log.warning("Emendas federais nas cidades: %s", e)
        fontes.avisar("Emendas federais nas cidades: o arquivo veio num formato diferente; essa parte ficou sem atualização")
        return None


# ---------------------------------------------------------------- a história de cada emenda
#
# Para cada emenda federal que chegou a uma cidade de Minas, contamos a história inteira numa ficha só:
# 1. quem indicou, quando, de que tipo e para quê (tabela principal do arquivo do Portal: autor, função, ação);
# 2. quanto o governo reservou (empenhado) e pagou, e quando cada pagamento chegou e a quem (tabela por favorecido);
# 3. nas emendas Pix, o plano de ação que a prefeitura registrou no Transferegov (o que ia fazer, metas, quem executa);
# 4. nas emendas Pix, cada pagamento que a prefeitura informou ter feito com o dinheiro (a quem, para quê, quanto).
#
# Por que o arquivo e não a API do Portal: a API de emendas (api.portaldatransparencia.gov.br/api-de-dados/emendas)
# devolve as mesmas linhas da tabela principal, mas só página por página, e não traz quem recebeu mês a mês; para
# isso seria um pedido por emenda (milhares por dia só em Minas). O arquivo completo já é baixado todo dia pelo
# coletor nacional e traz as duas coisas. As partes 3 e 4 vêm da API do Transferegov, lida pelo coletor nacional
# (etl/sa_etl/transferegov.py), que grava data/emendas/destino/{ano}/{cnpj}.json; aqui só juntamos com a emenda.

PAGINA_EMENDA = "https://portaldatransparencia.gov.br/emendas/detalhe?codigoEmenda={codigo}&ano={ano}"


def anos_do_site(nacional: Path) -> list[int]:
    """Os anos de emendas que o site nacional mostra (os mesmos lidos no Transferegov)."""
    import json
    try:
        anos = json.loads((nacional / "emendas" / "anos.json").read_text(encoding="utf-8")).get("anos") or []
        return sorted({int(a) for a in anos})
    except (OSError, ValueError, TypeError):
        return []


def _cidade_da_linha(g, cidades: dict[str, str], uf: str) -> str | None:
    """A cidade onde a emenda é aplicada: colunas Município e UF, ou a localidade 'ITAJUBA - MG'."""
    u = g("uf").upper()
    if g("municipio") and u in (uf, "MINAS GERAIS"):
        return cidades.get(chave_cidade(g("municipio")))
    m = re.fullmatch(r"\s*(.+?)\s*-\s*([A-Z]{2})\s*", g("local").upper())
    if m and m.group(2) == uf:
        return cidades.get(chave_cidade(m.group(1)))
    return None


def _ler_destino(nacional: Path, anos: list[int]) -> tuple[dict, dict | None]:
    """Planos de ação das emendas Pix, por código da emenda, a partir dos arquivos do coletor nacional.
    Devolve ({código: plano}, informações da leitura) ou ({}, None) se o Transferegov ainda não foi lido."""
    import json
    planos: dict[str, dict] = {}
    info = None
    pasta = nacional / "emendas" / "destino"
    for ano in anos:
        try:
            idx = json.loads((pasta / f"{ano}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        info = info or {"fonte": idx.get("fonte"), "consulta": idx.get("consulta"), "atualizado": idx.get("atualizado"),
                        "completo": bool(idx.get("completo")), "anos": []}
        info["anos"].append(ano)
        info["completo"] = info["completo"] and bool(idx.get("completo"))
        if idx.get("atualizado") and (not info["atualizado"] or idx["atualizado"] < info["atualizado"]):
            info["atualizado"] = idx["atualizado"]
        # só os beneficiários de Minas (o arquivo de cada um traz todas as suas emendas Pix do ano)
        mg = {b["cnpj"] for b in idx.get("beneficiarios", []) if b.get("uf") == "MG"}
        for cnpj in sorted(mg):
            try:
                b = json.loads((pasta / str(ano) / f"{cnpj}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for p in b.get("planos", []):
                cod = digits(p.get("emenda") or "")
                if cod:
                    planos[cod] = {**p, "beneficiario": b.get("nome") or "", "cnpj_beneficiario": cnpj}
    return planos, info


def historias(zip_path: Path, nacional: Path, cidades: dict[str, str], autores: dict[str, dict],
              anos: list[int] | None = None, uf: str = "MG") -> dict:
    """Cada emenda federal que chegou a cada cidade de Minas, com a história inteira.

    {"cidades": {id: [emenda, ...]}, "transferegov": info ou None, "anos": [...]}"""
    anos = anos or anos_do_site(nacional)
    if not anos:
        raise ValueError("não há anos de emendas nos dados nacionais")
    anos_set = set(anos)
    emendas: dict[str, dict] = {}
    col = None
    for r in E.linhas(zip_path, ""):
        if col is None:
            col = E.achar_colunas(list(r.keys()), E.REGRAS)
            if not (col["codigo"] and col["ano"] and (col["pago"] or col["empenhado"])):
                raise ValueError(f"tabela principal de emendas sem as colunas esperadas ({col})")
        g = lambda k: (r.get(col[k]) or "").strip() if col.get(k) else ""  # noqa: E731
        cod = digits(g("codigo"))
        try:
            ano = int(fontes.valor(g("ano")))
        except (TypeError, ValueError):
            continue
        if not cod or ano not in anos_set:
            continue
        e = emendas.get(cod)
        if e is None:
            autor_bruto = g("autor") or "Sem autor informado"
            _, autor_nome = E.nome_autor(autor_bruto)
            a = autores.get(E._chave(autor_nome)) or autores.get(E._chave(autor_bruto)) or {}
            e = emendas[cod] = {
                "codigo": cod, "ano": ano, "tipo": E.tipo_curto(g("tipo")), "tipo_nome": g("tipo"),
                "autor": a.get("nome") or fontes.bonito(autor_nome) or "Não informado",
                "politico": a.get("politico"), "partido": a.get("partido") or "",
                "local": fontes.bonito(g("local")), "cidade": None,
                "funcao": "", "subfuncao": "", "acoes": [],
                "empenhado": 0.0, "liquidado": 0.0, "pago": 0.0,
            }
        e["cidade"] = e["cidade"] or _cidade_da_linha(g, cidades, uf)
        e["funcao"] = e["funcao"] or fontes.bonito(g("funcao"))
        e["subfuncao"] = e["subfuncao"] or fontes.bonito(g("subfuncao"))
        acao = fontes.bonito(g("acao"))
        if acao and acao not in e["acoes"]:
            e["acoes"].append(acao)
        e["empenhado"] += fontes.valor(g("empenhado"))
        e["liquidado"] += fontes.valor(g("liquidado"))
        # "pago" soma o que foi pago no ano e os restos a pagar já pagos, como na página nacional
        e["pago"] += fontes.valor(g("pago")) + fontes.valor(g("rap_pago"))

    # quem recebeu, mês a mês (só quem tem endereço numa cidade de Minas)
    recebido: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    col = None
    for r in E.linhas(zip_path, "favorecido"):
        if col is None:
            col = E.achar_colunas(list(r.keys()), E.REGRAS_FAV)
            if not (col["codigo"] and col["valor"] and col["municipio"] and col["anomes"]):
                raise ValueError(f"tabela por favorecido sem as colunas esperadas ({col})")
        g = lambda k: (r.get(col[k]) or "").strip() if col.get(k) else ""  # noqa: E731
        cod = digits(g("codigo"))
        if cod not in emendas:
            continue
        if col.get("uf") and g("uf").upper() not in (uf, "MINAS GERAIS"):
            continue
        cid = cidades.get(chave_cidade(g("municipio")))
        v = fontes.valor(g("valor"))
        am = digits(g("anomes"))
        if not cid or not v or len(am) < 6:
            continue
        mes = f"{am[:4]}-{am[4:6]}" if am[:2] in ("19", "20") else f"{am[-4:]}-{am[:2]}"
        doc = digits(g("doc"))
        cnpj = doc if len(doc) == 14 else ""
        recebido[cid][cod].append({"mes": mes, "nome": fontes.bonito(g("nome")) if cnpj else "Pessoa física",
                                   "cnpj": cnpj, "valor": round(v, 2)})

    planos, info = _ler_destino(nacional, anos)

    por_cidade: dict[str, set] = defaultdict(set)
    for cod, e in emendas.items():
        if e["cidade"]:
            por_cidade[e["cidade"]].add(cod)
    for cid, cods in recebido.items():
        por_cidade[cid].update(cods)

    out: dict[str, list] = {}
    for cid, cods in por_cidade.items():
        lista = []
        for cod in cods:
            e = emendas[cod]
            rec = sorted(recebido.get(cid, {}).get(cod, []), key=lambda x: (x["mes"], -x["valor"]))
            p = planos.get(cod) if e["tipo"] == "pix" else None
            lista.append({
                **{k: e[k] for k in ("codigo", "ano", "tipo", "tipo_nome", "autor", "politico", "partido", "local",
                                     "funcao", "subfuncao", "acoes")},
                "na_cidade": e["cidade"] == cid,  # aplicada na cidade (e não só paga a alguém daqui)
                "empenhado": round(e["empenhado"], 2), "liquidado": round(e["liquidado"], 2), "pago": round(e["pago"], 2),
                "recebido": rec, "recebido_aqui": round(sum(x["valor"] for x in rec), 2),
                "plano": p,
                "url": PAGINA_EMENDA.format(codigo=cod, ano=e["ano"]),
            })
        lista.sort(key=lambda x: (-x["ano"], -max(x["pago"], x["recebido_aqui"]), x["codigo"]))
        out[cid] = lista
    n = sum(len(v) for v in out.values())
    log.info("Histórias das emendas federais: %d emendas em %d cidades (%s); %d com plano de ação no Transferegov",
             n, len(out), ", ".join(map(str, anos)), sum(1 for v in out.values() for x in v if x["plano"]))
    return {"cidades": out, "transferegov": info, "anos": anos}


def coletar_historias(zip_nacional: Path, nacional: Path, cidades: dict[str, str], ids_mg: set[str]) -> dict | None:
    if not zip_nacional.exists():
        fontes.avisar("Histórias das emendas federais: o arquivo do Portal da Transparência não estava disponível")
        return None
    autores = autores_nacionais(nacional)
    for a in autores.values():
        if a.get("politico") not in ids_mg:
            a["politico"] = None
    try:
        h = historias(zip_nacional, nacional, cidades, autores)
    except Exception as e:  # noqa: BLE001
        log.warning("Histórias das emendas federais: %s", e)
        fontes.avisar("Histórias das emendas federais: o arquivo veio num formato diferente; essa parte ficou sem atualização")
        return None
    if h["transferegov"] is None:
        fontes.avisar("Emendas Pix nas cidades: o Transferegov ainda não foi lido; as fichas mostram só o que o Portal da "
                      "Transparência informa, sem o plano de ação e os gastos da prefeitura")
    return h
