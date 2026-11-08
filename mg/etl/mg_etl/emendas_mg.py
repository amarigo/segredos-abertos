"""Emendas estaduais: dinheiro do orçamento de Minas que cada deputado estadual indicou, para onde e para quem.

Fonte: arquivo de emendas parlamentares da Assembleia (ALMG), com todas as indicações desde 2019:
    página: https://www.almg.gov.br/atividade-parlamentar/emendas-parlamentares/inicial/
    arquivo (CSV): achado nessa página; se a página mudar, usamos o último endereço conhecido (ARQUIVO).

Cada linha é uma indicação: o deputado (autor), o ano, o município, quem recebe (prefeitura, hospital, escola,
associação...), o que é (descrição e objeto), o órgão do estado que executa, a ação do orçamento, o tipo de despesa
(investimento ou custeio), a forma de execução (convênio, transferência especial, execução direta...), quanto foi
indicado, empenhado e pago. Não há API para essas indicações: a ALMG publica só este arquivo e um painel (Power BI).

A descrição vem "Não há" quando o deputado não escreveu nada (comum nas transferências para prefeituras e fundos
municipais): tratamos como vazia e mostramos o órgão, a ação e o objeto no lugar. O CNPJ desse arquivo vem estragado
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
ARQUIVO_USADO: str | None = None  # o endereço achado na última coleta, para o link "baixar o arquivo" da página

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
    "uf": [["estado"]],
    "tipo_beneficiario": [["tipo", "beneficiario"]],
    "beneficiario": [["nome", "beneficiario"]],
    "descricao": [["descricao", "indicacao"]],
    "indicado": [["valor", "indicado"]],
    "pago": [["valor", "pago"]],
    "status": [["status"]],
    "categoria": [["categoria"]],
    "especificacao": [["especificacao"]],
    "tipo_aplicacao": [["tipo", "aplicacao"]],
    "acao": [["nome", "acao"]],
    "grupo": [["grupo", "despesa", "descricao"]],
    "empenhado": [["valor", "empenhado"]],
    "autoria": [["tipo", "autoria"]],
    "instrumento": [["numero", "instrumento"]],
    "status_instrumento": [["status", "instrumento"]],
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
            if campo in ("status", "uf"):  # "Status" e "Estado" sozinhos, não "Status da Indicação"
                cands = [c for c in cands if len(ws[c]) == 1] or cands
            if cands:
                out[campo] = min(cands, key=lambda c: len(ws[c]))
                break
    return out


VAZIOS = {"", "-", "--", "NAO HA", "NAO SE APLICA", "N A", "NA", "NENHUM", "NENHUMA", "SEM DESCRICAO", "NULL", "NONE", "0"}


def limpo(s: str) -> str:
    """'Não há', '-' e afins viram texto vazio: a fonte usa isso quando o campo não foi preenchido."""
    s = re.sub(r"\s+", " ", (s or "").strip())
    return "" if re.sub(r"[^A-Z0-9]+", " ", norm_name(s).upper()).strip() in VAZIOS else s


def _objeto(*partes: str) -> str:
    """Categoria, especificação e tipo de aplicação juntos, sem repetir: 'Custeio · Aquisição de veículo'."""
    out: list[str] = []
    for p in partes:
        p = fontes.bonito(limpo(p))
        if p and not any(norm_name(p).lower() == norm_name(o).lower() for o in out):
            out.append(p)
    return " · ".join(out)


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
            "municipio": g(r, "municipio"), "uf": limpo(g(r, "uf")), "beneficiario": fontes.sem_cpf(fontes.bonito(limpo(g(r, "beneficiario")))),
            "tipo_beneficiario": fontes.bonito(limpo(g(r, "tipo_beneficiario"))),
            "descricao": fontes.sem_cpf(limpo(g(r, "descricao")))[:220], "area": fontes.bonito(limpo(g(r, "funcao"))),
            "orgao": limpo(g(r, "uo")), "orgao_nome": fontes.bonito(limpo(g(r, "uo_nome"))) or limpo(g(r, "uo")),
            "acao": fontes.sem_cpf(fontes.bonito(limpo(g(r, "acao")))), "grupo": fontes.bonito(limpo(g(r, "grupo"))),
            "tipo_indicacao": fontes.bonito(limpo(g(r, "tipo_indicacao"))),
            "objeto": fontes.sem_cpf(_objeto(g(r, "categoria"), g(r, "especificacao"), g(r, "tipo_aplicacao")))[:160],
            "autoria": fontes.bonito(limpo(g(r, "autoria"))),
            "instrumento": limpo(g(r, "instrumento")), "status_instrumento": fontes.bonito(limpo(g(r, "status_instrumento"))),
            "indicado": round(fontes.valor(g(r, "indicado")), 2), "pago": round(fontes.valor(g(r, "pago")), 2),
            "empenhado": round(fontes.valor(g(r, "empenhado")), 2),
            "situacao": limpo(g(r, "status")) or limpo(g(r, "status_indicacao")),
            "aprovada": not re.search(r"REPROV|CANCEL|EXCLU|INDEFER", norm_name(g(r, "status_indicacao"))),
        })
    log.info("Emendas ALMG: %d indicações (%d linhas no arquivo); colunas %s", len(out), len(rows), col)
    return out


def chave_cidade(nome: str) -> str:
    return re.sub(r"[^A-Z]", "", norm_name(nome))


def _top(d: dict, n: int) -> list:
    return sorted(d.items(), key=lambda kv: -kv[1][0])[:n]


A_DEFINIR = re.compile(r"DEFINI")
UF_MG = {"MG", "MINAS GERAIS"}


def nomear_locais(rows: list[dict], mg: dict[str, str]) -> dict:
    """Põe em cada indicação o nome do lugar como aparece no site ("local").

    mg: chave sem acento -> nome oficial dos 853 municípios de Minas (API do Tesouro). Com ela:
    - município de Minas ganha o nome oficial, com acento e maiúsculas certas ("UBÁ" vira "Ubá");
    - quando a coluna Estado do arquivo diz outro estado, o nome leva a UF: "Brasília (Distrito Federal)";
    - nome que não é município de Minas nem traz outro estado fica como veio, e entra na conferência.
    Devolve a conferência por ano: {ano: [{municipio, uf, n, indicado, beneficiarios}]}, para o site e o log."""
    fora: dict = defaultdict(lambda: defaultdict(lambda: {"n": 0, "indicado": 0.0, "ben": defaultdict(float)}))
    for r in rows:
        bruto = r["municipio"]
        k = chave_cidade(bruto)
        uf = norm_name(r.get("uf") or "").strip()
        nome = fontes.bonito(bruto) or "Sem município"
        if not k or A_DEFINIR.search(norm_name(bruto)):
            r["local"] = "A ser definido pelo órgão" if k else nome
            continue
        if mg and k in mg and (not uf or uf in UF_MG):
            r["local"] = mg[k]
            # "Hospital Sao Vicente de Paulo de UBA": o nome da cidade dentro do nome de quem recebe também
            if " " not in mg[k]:
                r["beneficiario"] = re.sub(rf"\b{re.escape(mg[k].upper())}\b|\b{re.escape(norm_name(mg[k]))}\b", mg[k],
                                           r["beneficiario"])
            continue
        fora_mg = bool(uf) and uf not in UF_MG
        r["local"] = f"{nome} ({fontes.bonito(r['uf'])})" if fora_mg else nome
        if mg or fora_mg:
            f = fora[r["ano"]][(nome, fontes.bonito(r.get("uf") or ""))]
            if r["aprovada"]:
                f["n"] += 1; f["indicado"] += r["indicado"]; f["ben"][r["beneficiario"]] += r["indicado"]
    out = {}
    for ano, d in fora.items():
        lst = [{"municipio": m, "uf": uf, "n": v["n"], "indicado": round(v["indicado"], 2),
                "beneficiarios": [b for b, _ in sorted(v["ben"].items(), key=lambda kv: -kv[1])[:5]]}
               for (m, uf), v in d.items() if v["n"]]
        if lst:
            out[ano] = sorted(lst, key=lambda x: -x["indicado"])
            log.warning("Emendas ALMG %s: lugares que não são municípios de Minas: %s", ano,
                        "; ".join(f"{x['municipio']} [{x['uf'] or 'sem estado'}] {x['n']} indicações, R$ {x['indicado']:,.0f}, "
                                  f"ex.: {', '.join(x['beneficiarios'][:3])}" for x in out[ano][:15]))
    return out


CAMPOS_LISTA = ("numero", "autor", "municipio", "beneficiario", "tipo_beneficiario", "tipo_indicacao", "orgao_nome", "acao",
                "area", "grupo", "objeto", "descricao", "situacao", "autoria", "indicado", "empenhado", "pago")
NUMEROS = ("indicado", "empenhado", "pago")


def _soma() -> list:
    return [0.0, 0.0, 0, 0.0]  # indicado, pago, n, empenhado


def _mais(v: list, r: dict) -> None:
    v[0] += r["indicado"]; v[1] += r["pago"]; v[2] += 1; v[3] += r["empenhado"]


def _ranking(d: dict, n: int | None, extra=None) -> list[dict]:
    itens = sorted(d.items(), key=lambda kv: (-kv[1][0], str(kv[0])))
    out = []
    for k, v in itens[:n] if n else itens:
        x = {"nome": k, "indicado": round(v[0], 2), "pago": round(v[1], 2), "n": v[2], "empenhado": round(v[3], 2)}
        out.append(x | (extra(k, v) if extra else {}))
    return out


def lista_do_ano(rows: list[dict], deputados: dict[str, str]) -> dict:
    """Todas as indicações aprovadas de um ano, para a página procurar por deputado, cidade, quem recebe ou órgão.

    Os textos se repetem muito (o mesmo órgão, a mesma cidade), então cada texto vai uma vez só na lista "textos" e as
    linhas guardam a posição dele. Assim o arquivo do ano fica pequeno."""
    textos: list[str] = []
    pos: dict[str, int] = {}

    def t(s: str) -> int:
        if s not in pos:
            pos[s] = len(textos); textos.append(s)
        return pos[s]
    linhas_out = []
    autores: dict[str, str | None] = {}
    for r in sorted(rows, key=lambda r: (-r["indicado"], r["numero"])):
        x = dict(r, autor=fontes.bonito(r["autor"]), municipio=r.get("local") or fontes.bonito(r["municipio"]) or "Sem município")
        autores[x["autor"]] = deputados.get(fontes.chave_nome(r["autor"]))
        linhas_out.append([round(x[k], 2) if k in NUMEROS else (x[k] if k == "numero" else t(x[k] or "")) for k in CAMPOS_LISTA])
    return {"campos": list(CAMPOS_LISTA), "textos": textos, "linhas": linhas_out,
            "deputados": {k: v for k, v in autores.items() if v},
            "indicado": round(sum(r["indicado"] for r in rows), 2), "pago": round(sum(r["pago"] for r in rows), 2), "n": len(rows)}


def resumir(rows: list[dict], deputados: dict[str, str], cidades: dict[str, str], fora: dict | None = None) -> dict:
    """deputados: nome-chave -> id; cidades: chave do município -> id da cidade acompanhada.

    Devolve {"por_deputado": {id: {ano: {...}}}, "por_cidade": {id: [...]}, "estado": {ano: {...}}, "listas": {ano: {...}}}.
    Só entram indicações aprovadas (as reprovadas não viram dinheiro; só contamos quantas foram)."""
    por_dep: dict = defaultdict(lambda: defaultdict(lambda: {"indicado": 0.0, "pago": 0.0, "n": 0,
                                                            "mun": defaultdict(lambda: [0.0, 0.0, 0]),
                                                            "ben": defaultdict(lambda: [0.0, 0.0, 0, "", "", ""])}))
    estado: dict = defaultdict(lambda: {"indicado": 0.0, "pago": 0.0, "empenhado": 0.0, "n": 0, "reprovadas": 0,
                                        **{k: defaultdict(_soma) for k in ("mun", "autor", "ben", "orgao", "tipo", "area", "grupo")},
                                        "ben_info": {}, "mun_ben": defaultdict(set)})
    por_cidade: dict = defaultdict(list)
    por_ano: dict = defaultdict(list)
    sem_deputado: dict = defaultdict(lambda: defaultdict(float))  # ano -> autor -> indicado (conferência da lista)
    for r in rows:
        if not r["aprovada"]:
            estado[r["ano"]]["reprovadas"] += 1
            continue
        por_ano[r["ano"]].append(r)
        dep = deputados.get(fontes.chave_nome(r["autor"]))
        mun = r.get("local") or fontes.bonito(r["municipio"]) or "Sem município"
        e = estado[r["ano"]]
        e["indicado"] += r["indicado"]; e["pago"] += r["pago"]; e["empenhado"] += r["empenhado"]; e["n"] += 1
        _mais(e["mun"][mun], r)
        _mais(e["autor"][r["autor"]], r)
        _mais(e["orgao"][r["orgao_nome"] or "Órgão não informado"], r)
        _mais(e["tipo"][r["tipo_indicacao"] or "Não informado"], r)
        _mais(e["area"][r["area"] or "Não informada"], r)
        _mais(e["grupo"][r["grupo"] or "Não informado"], r)
        kb = (r["beneficiario"] or "Não informado", mun)
        _mais(e["ben"][kb], r)
        e["ben_info"].setdefault(kb, r["tipo_beneficiario"])
        if not dep:
            sem_deputado[r["ano"]][r["autor"]] += r["indicado"]
        if dep:
            d = por_dep[dep][r["ano"]]
            d["indicado"] += r["indicado"]; d["pago"] += r["pago"]; d["n"] += 1
            m = d["mun"][mun]; m[0] += r["indicado"]; m[1] += r["pago"]; m[2] += 1
            b = d["ben"][(r["beneficiario"], mun)]; b[0] += r["indicado"]; b[1] += r["pago"]; b[2] += 1
            b[3] = b[3] or r["descricao"] or r["objeto"]; b[4] = b[4] or r["area"]; b[5] = b[5] or r["orgao_nome"]
        cid = cidades.get(chave_cidade(r["municipio"]))
        if cid:
            por_cidade[cid].append({k: r[k] for k in ("ano", "autor", "beneficiario", "tipo_beneficiario", "descricao", "area",
                                                     "orgao", "orgao_nome", "acao", "grupo", "tipo_indicacao", "objeto",
                                                     "indicado", "empenhado", "pago", "situacao")} | {"deputado": dep, "municipio": mun})
    out_dep = {}
    for dep, anos in por_dep.items():
        out_dep[dep] = {}
        for ano, d in anos.items():
            out_dep[dep][ano] = {
                "indicado": round(d["indicado"], 2), "pago": round(d["pago"], 2), "n": d["n"],
                "municipios": [{"nome": k, "indicado": round(v[0], 2), "pago": round(v[1], 2), "n": v[2]} for k, v in _top(d["mun"], 12)],
                "n_municipios": len(d["mun"]),
                "beneficiarios": [{"nome": k[0], "municipio": k[1], "indicado": round(v[0], 2), "pago": round(v[1], 2), "n": v[2],
                                   "descricao": v[3], "area": v[4], "orgao": v[5]} for k, v in _top(d["ben"], 20)],
            }
    out_estado = {}
    for ano, e in estado.items():
        if not e["n"]:
            continue
        out_estado[ano] = {
            "indicado": round(e["indicado"], 2), "pago": round(e["pago"], 2), "empenhado": round(e["empenhado"], 2), "n": e["n"],
            "reprovadas": e["reprovadas"],
            # lugares do arquivo que não são municípios de Minas (outro estado, ou nome fora da lista oficial)
            "fora_de_mg": (fora or {}).get(ano, []),
            "municipios": _ranking(e["mun"], 30),
            "n_municipios": len(e["mun"]),
            "autores": _ranking(e["autor"], 150, lambda k, v: {"deputado": deputados.get(fontes.chave_nome(k))}),
            "n_autores": len(e["autor"]),
            "beneficiarios": [{"nome": k[0], "municipio": k[1], "tipo": e["ben_info"].get(k, ""), "indicado": round(v[0], 2),
                               "pago": round(v[1], 2), "n": v[2], "empenhado": round(v[3], 2)}
                              for k, v in sorted(e["ben"].items(), key=lambda kv: (-kv[1][0], kv[0]))[:30]],
            "n_beneficiarios": len(e["ben"]),
            "orgaos": _ranking(e["orgao"], None),
            "tipos": _ranking(e["tipo"], None),
            "areas": _ranking(e["area"], None),
            "grupos": _ranking(e["grupo"], None),
        }
        for a in out_estado[ano]["autores"]:
            a["nome"] = fontes.bonito(a["nome"])
    for cid in por_cidade:
        por_cidade[cid].sort(key=lambda x: (-x["ano"], -x["indicado"]))
    return {"por_deputado": out_dep, "por_cidade": dict(por_cidade), "estado": out_estado,
            "listas": {ano: lista_do_ano(rs, deputados) for ano, rs in por_ano.items()},
            "sem_deputado": {a: dict(x) for a, x in sem_deputado.items()}}


def coletar(cache: Path, deputados: dict[str, str], cidades: dict[str, str], mg: dict[str, str] | None = None) -> dict | None:
    """Baixa (cópia de até 20 horas) e resume. None se não houver arquivo nem cópia: as páginas ficam sem emendas."""
    global ARQUIVO_USADO
    ARQUIVO_USADO = achar_arquivo()
    texto = fontes.baixar(ARQUIVO_USADO, cache / "almg" / "emendas.csv", 20, "Emendas estaduais (ALMG)", minimo=10_000)
    if texto is None:
        return None
    try:
        rows = linhas(texto)
        return resumir(rows, deputados, cidades, nomear_locais(rows, mg or {}))
    except ValueError as e:
        log.warning("Emendas ALMG: %s", e)
        fontes.avisar("Emendas estaduais (ALMG): o arquivo veio num formato diferente; essa parte ficou sem atualização")
        return None
