"""Emendas estaduais: dinheiro do orçamento de Minas que cada deputado estadual indicou, para onde e para quem.

Fonte: arquivo de emendas parlamentares da Assembleia (ALMG), com todas as indicações desde 2019:
    página: https://www.almg.gov.br/atividade-parlamentar/emendas-parlamentares/inicial/
    arquivo (CSV): achado nessa página; se a página mudar, usamos o último endereço conhecido (ARQUIVO).

Cada linha é uma indicação: o deputado (autor), o ano, o município, quem recebe (prefeitura, hospital, escola,
associação...), o que é (descrição), quanto foi indicado e quanto já foi pago. O CNPJ desse arquivo vem estragado
(o Excel transforma em "1,6695E+13"), por isso mostramos só o nome de quem recebe.

Os nomes das colunas são achados por palavras-chave, para o coletor não quebrar se a ALMG mudar um acento.
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from pathlib import Path

from sa_etl.util import get, norm_name

from . import fontes

log = logging.getLogger("mg_etl.emendas_mg")

PAGINA = "https://www.almg.gov.br/atividade-parlamentar/emendas-parlamentares/inicial/"
ARQUIVO = "https://mediaserver.almg.gov.br/acervo/497/469/2497469.csv"

REGRAS = {
    "ano": [["ano", "indicacao"]],
    "numero": [["numero", "indicacao"]],
    "autor": [["autor"]],
    "status_indicacao": [["status", "indicacao"]],
    "tipo_indicacao": [["tipo", "indicacao"]],
    "uo": [["unidade", "orcamentaria", "sigla"]],
    "uo_nome": [["unidade", "orcamentaria", "descricao"]],
    "funcao": [["funcao", "descricao"]],
    "municipio": [["municipio"]],
    "tipo_beneficiario": [["tipo", "beneficiario"]],
    "beneficiario": [["nome", "beneficiario"]],
    "descricao": [["descricao", "indicacao"]],
    "indicado": [["valor", "indicado"]],
    "pago": [["valor", "pago"]],
    "status": [["status"]],
}
OBRIGATORIOS = ("ano", "autor", "municipio", "beneficiario", "indicado", "pago")


def _palavras(c: str) -> list[str]:
    return re.sub(r"[^a-z0-9]+", " ", norm_name(c).lower()).split()


def achar_colunas(cab: list[str]) -> dict[str, str | None]:
    """Coluna de cada campo: a de nome mais curto que tem todas as palavras da regra."""
    ws = {c: _palavras(c) for c in cab}
    out = {}
    for campo, regras in REGRAS.items():
        out[campo] = None
        for r in regras:
            cands = [c for c, w in ws.items() if all(p in w for p in r)]
            if campo == "status":  # "Status" sozinho, não "Status da Indicação"
                cands = [c for c in cands if len(ws[c]) == 1] or cands
            if cands:
                out[campo] = min(cands, key=lambda c: len(ws[c]))
                break
    return out


def achar_arquivo() -> str:
    """O endereço do CSV muda quando a ALMG publica uma versão nova: procuramos na página de emendas."""
    try:
        html = get(PAGINA, timeout=60).text
        links = re.findall(r"""https?://mediaserver\.almg\.gov\.br/[^"'\s<>]+\.csv""", html)
        if links:
            return links[0]
    except Exception as e:  # noqa: BLE001
        log.warning("Emendas ALMG: página fora do ar (%s); usando o último endereço conhecido", e)
    return ARQUIVO


def linhas(texto: str) -> list[dict]:
    """Indicações normalizadas. Linhas repetidas (mesmo ano e número) entram uma vez só."""
    rows = list(fontes.ler_csv(texto, sep=";"))
    if not rows:
        raise ValueError("arquivo de emendas da ALMG vazio")
    col = achar_colunas(list(rows[0]))
    falta = [k for k in OBRIGATORIOS if not col[k]]
    if falta:
        raise ValueError(f"arquivo de emendas da ALMG sem as colunas {falta}")
    g = lambda r, k: (r.get(col[k]) or "").strip() if col[k] else ""  # noqa: E731
    vistos, out = set(), []
    for r in rows:
        ano = re.sub(r"\D", "", g(r, "ano"))[:4]
        if len(ano) != 4:
            continue
        chave = (ano, g(r, "numero")) if g(r, "numero") else None
        if chave and chave in vistos:
            continue
        if chave:
            vistos.add(chave)
        out.append({
            "ano": int(ano), "numero": g(r, "numero"), "autor": g(r, "autor"),
            "municipio": g(r, "municipio"), "beneficiario": fontes.sem_cpf(fontes.bonito(g(r, "beneficiario"))),
            "tipo_beneficiario": fontes.bonito(g(r, "tipo_beneficiario")),
            "descricao": fontes.sem_cpf(g(r, "descricao"))[:220], "area": fontes.bonito(g(r, "funcao")), "orgao": g(r, "uo"),
            "indicado": round(fontes.valor(g(r, "indicado")), 2), "pago": round(fontes.valor(g(r, "pago")), 2),
            "situacao": g(r, "status") if g(r, "status") not in ("-", "") else g(r, "status_indicacao"),
            "aprovada": not re.search(r"REPROV|CANCEL|EXCLU|INDEFER", norm_name(g(r, "status_indicacao"))),
        })
    log.info("Emendas ALMG: %d indicações (%d linhas no arquivo); colunas %s", len(out), len(rows), col)
    return out


def chave_cidade(nome: str) -> str:
    return re.sub(r"[^A-Z]", "", norm_name(nome))


def _top(d: dict, n: int) -> list:
    return sorted(d.items(), key=lambda kv: -kv[1][0])[:n]


def resumir(rows: list[dict], deputados: dict[str, str], cidades: dict[str, str]) -> dict:
    """deputados: nome-chave -> id; cidades: chave do município -> id da cidade acompanhada.

    Devolve {"por_deputado": {id: {ano: {...}}}, "por_cidade": {id: [...]}, "estado": {ano: {...}}}.
    Só entram indicações aprovadas (as reprovadas não viram dinheiro)."""
    por_dep: dict = defaultdict(lambda: defaultdict(lambda: {"indicado": 0.0, "pago": 0.0, "n": 0,
                                                            "mun": defaultdict(lambda: [0.0, 0.0, 0]),
                                                            "ben": defaultdict(lambda: [0.0, 0.0, 0, "", ""])}))
    estado: dict = defaultdict(lambda: {"indicado": 0.0, "pago": 0.0, "n": 0, "mun": defaultdict(lambda: [0.0, 0.0, 0]),
                                        "autor": defaultdict(lambda: [0.0, 0.0, 0])})
    por_cidade: dict = defaultdict(list)
    for r in rows:
        if not r["aprovada"]:
            continue
        dep = deputados.get(fontes.chave_nome(r["autor"]))
        mun = fontes.bonito(r["municipio"]) or "Sem município"
        e = estado[r["ano"]]
        e["indicado"] += r["indicado"]; e["pago"] += r["pago"]; e["n"] += 1
        m = e["mun"][mun]; m[0] += r["indicado"]; m[1] += r["pago"]; m[2] += 1
        a = e["autor"][r["autor"]]; a[0] += r["indicado"]; a[1] += r["pago"]; a[2] += 1
        if dep:
            d = por_dep[dep][r["ano"]]
            d["indicado"] += r["indicado"]; d["pago"] += r["pago"]; d["n"] += 1
            m = d["mun"][mun]; m[0] += r["indicado"]; m[1] += r["pago"]; m[2] += 1
            b = d["ben"][(r["beneficiario"], mun)]; b[0] += r["indicado"]; b[1] += r["pago"]; b[2] += 1
            b[3] = b[3] or r["descricao"]; b[4] = b[4] or r["area"]
        cid = cidades.get(chave_cidade(r["municipio"]))
        if cid:
            por_cidade[cid].append({k: r[k] for k in ("ano", "autor", "beneficiario", "tipo_beneficiario", "descricao", "area",
                                                     "orgao", "indicado", "pago", "situacao")} | {"deputado": dep})
    out_dep = {}
    for dep, anos in por_dep.items():
        out_dep[dep] = {}
        for ano, d in anos.items():
            out_dep[dep][ano] = {
                "indicado": round(d["indicado"], 2), "pago": round(d["pago"], 2), "n": d["n"],
                "municipios": [{"nome": k, "indicado": round(v[0], 2), "pago": round(v[1], 2), "n": v[2]} for k, v in _top(d["mun"], 12)],
                "n_municipios": len(d["mun"]),
                "beneficiarios": [{"nome": k[0], "municipio": k[1], "indicado": round(v[0], 2), "pago": round(v[1], 2), "n": v[2],
                                   "descricao": v[3], "area": v[4]} for k, v in _top(d["ben"], 20)],
            }
    out_estado = {}
    for ano, e in estado.items():
        out_estado[ano] = {
            "indicado": round(e["indicado"], 2), "pago": round(e["pago"], 2), "n": e["n"],
            "municipios": [{"nome": k, "indicado": round(v[0], 2), "pago": round(v[1], 2), "n": v[2]} for k, v in _top(e["mun"], 30)],
            "n_municipios": len(e["mun"]),
            "autores": [{"nome": fontes.bonito(k), "deputado": deputados.get(fontes.chave_nome(k)), "indicado": round(v[0], 2),
                         "pago": round(v[1], 2), "n": v[2]} for k, v in _top(e["autor"], 100)],
        }
    for cid in por_cidade:
        por_cidade[cid].sort(key=lambda x: (-x["ano"], -x["indicado"]))
    return {"por_deputado": out_dep, "por_cidade": dict(por_cidade), "estado": out_estado}


def coletar(cache: Path, deputados: dict[str, str], cidades: dict[str, str]) -> dict | None:
    """Baixa (cópia de até 20 horas) e resume. None se não houver arquivo nem cópia: as páginas ficam sem emendas."""
    texto = fontes.baixar(achar_arquivo(), cache / "almg" / "emendas.csv", 20, "Emendas estaduais (ALMG)", minimo=10_000)
    if texto is None:
        return None
    try:
        return resumir(linhas(texto), deputados, cidades)
    except ValueError as e:
        log.warning("Emendas ALMG: %s", e)
        fontes.avisar("Emendas estaduais (ALMG): o arquivo veio num formato diferente; essa parte ficou sem atualização")
        return None
