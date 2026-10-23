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
