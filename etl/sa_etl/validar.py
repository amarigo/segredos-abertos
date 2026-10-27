"""Confere os arquivos gerados antes de publicar o site.

Erros bloqueiam a publicação (o site continua com a versão anterior, que estava certa). Alertas aparecem no
resumo do GitHub Actions, mas não bloqueiam.

O que é conferido:
- Somas: cada total bate com a soma das suas partes (grupos, categorias, meses, anos, parlamentares, empresas).
- Votações: cada votação aparece uma vez, cada parlamentar vota uma vez em cada votação, e o placar bate com os votos.
- Empresas e donos: cada empresa recebeu a soma do que cada parlamentar pagou; a cadeia de holdings não repete empresa.
- Privacidade e segurança: nenhum CPF sem máscara; todo link é http(s); nomes de arquivo seguros.
- Tamanho: número mínimo de deputados e senadores, e queda brusca em relação à versão publicada antes.
- Páginas oficiais: quantos deputados têm o total da cota igual ao da página oficial (alerta).

Uso:
    python -m sa_etl.validar ../site/public/data [--anterior https://.../data/meta.json] [--ignorar-queda]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .cnpj import MAX_NIVEL
from .util import id_seguro

FINS = {"pessoa", "estrangeiro", "sem_socios", "sem_dados", "limite", "ciclo"}
CHAVES_LINK = {"url", "foto", "fonte"}
CPF_ABERTO = re.compile(r"^\d{11}$|^\d{3}\.\d{3}\.\d{3}-\d{2}$")
CPF_NO_LINK = re.compile(r"(?:cnpjFornecedor|cpf)=\d{11}(?:&|$)", re.I)
NOME_ARQ = re.compile(r"^[A-Za-z0-9_-]+\.json$")

# Valores de produção. Os testes usam números menores.
MINIMOS = {"camara": 400, "senado": 70, "votacoes": 50}
QUEDA_MAXIMA = 0.2  # 20%


class Resultado:
    def __init__(self) -> None:
        self.erros: list[str] = []
        self.alertas: list[str] = []

    def erro(self, msg: str) -> None:
        if len(self.erros) < 500:
            self.erros.append(msg)

    def alerta(self, msg: str) -> None:
        if len(self.alertas) < 500:
            self.alertas.append(msg)

    @property
    def ok(self) -> bool:
        return not self.erros


def _ler(f: Path, r: Resultado) -> Any:
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except FileNotFoundError:
        r.erro(f"Arquivo faltando: {f.name}")
    except ValueError as e:
        r.erro(f"JSON inválido em {f}: {e}")
    return None


def _perto(a: float, b: float, n: int = 1) -> bool:
    """Igual, com tolerância para o arredondamento de centavos em n parcelas."""
    return abs((a or 0) - (b or 0)) <= 0.011 * max(n, 1) + 0.01


def _varrer(x: Any, caminho: str, r: Resultado) -> None:
    """Procura links perigosos e CPFs sem máscara em qualquer lugar do JSON."""
    if isinstance(x, dict):
        for k, v in x.items():
            if k in CHAVES_LINK and isinstance(v, str) and v and not re.match(r"^https?://", v, re.I):
                r.erro(f"Link que não é http(s) em {caminho}.{k}: {v[:80]!r}")
            elif k in CHAVES_LINK and isinstance(v, str) and CPF_NO_LINK.search(v):
                r.erro(f"CPF dentro de um link em {caminho}.{k}")
            elif k in ("doc", "cpf") and isinstance(v, str) and CPF_ABERTO.match(v.strip()):
                r.erro(f"CPF sem máscara em {caminho}.{k}")
            else:
                _varrer(v, f"{caminho}.{k}", r)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            _varrer(v, f"{caminho}[{i}]", r)


def validar(saida: Path, minimos: dict | None = None, anterior: dict | None = None,
            ignorar_queda: bool = False) -> Resultado:
    minimos = {**MINIMOS, **(minimos or {})}
    r = Resultado()
    meta = _ler(saida / "meta.json", r)
    pols = _ler(saida / "politicos.json", r)
    vots = _ler(saida / "votacoes.json", r)
    emps = _ler(saida / "empresas.json", r)
    parts = _ler(saida / "partidos.json", r)
    if not r.ok:
        return r
    anos = [str(a) for a in meta.get("anos", [])]

    # ---------------- nomes de arquivo
    for pasta in ("p", "v", "e", "e/notas"):
        for f in (saida / pasta).glob("*.json") if (saida / pasta).exists() else []:
            if not NOME_ARQ.match(f.name):
                r.erro(f"Nome de arquivo inseguro: {pasta}/{f.name}")

    # ---------------- parlamentares
    ids = Counter(p["id"] for p in pols)
    for i, n in ids.items():
        if n > 1:
            r.erro(f"Parlamentar repetido em politicos.json: {i} ({n} vezes)")
    por_casa = Counter(p["casa"] for p in pols)
    for casa in ("camara", "senado"):
        if por_casa[casa] < minimos[casa]:
            r.erro(f"Poucos parlamentares da casa {casa}: {por_casa[casa]} (mínimo {minimos[casa]})")
    por_id = {p["id"]: p for p in pols}

    soma_ano = Counter()
    for p in pols:
        pa = p.get("por_ano") or {}
        if not _perto(p["total"], sum(a["total"] for a in pa.values()), len(pa)):
            r.erro(f"{p['id']}: total {p['total']} diferente da soma dos anos")
        for ano, a in pa.items():
            soma_ano[ano] += a["total"]
            if not _perto(a["total"], sum((a.get("grupos") or {}).values()), 3):
                r.erro(f"{p['id']} {ano}: total {a['total']} diferente da soma dos grupos {a.get('grupos')}")
            custo = a["total"] + (a.get("salario") or 0) + (a.get("verba_gabinete") or 0) + (a.get("outros_gastos") or 0)
            if not _perto(a.get("custo_total", 0), custo, 4):
                r.erro(f"{p['id']} {ano}: custo_total {a.get('custo_total')} diferente de cota + salário + verba + outros ({custo:.2f})")
            if a["total"] < -0.01:
                r.alerta(f"{p['id']} {ano}: total negativo ({a['total']}): só devoluções no ano?")
        _conferir_politico(saida, p, r)

    if not _perto(meta.get("total_gasto", 0), sum(p["total"] for p in pols), len(pols)):
        r.erro(f"meta.total_gasto {meta.get('total_gasto')} diferente da soma dos parlamentares {sum(p['total'] for p in pols):.2f}")
    for ano in anos:
        if not _perto(meta.get("total_por_ano", {}).get(ano, 0), soma_ano[ano], len(pols)):
            r.erro(f"meta.total_por_ano[{ano}] diferente da soma dos parlamentares")
    if meta.get("contagens", {}).get("politicos") != len(pols):
        r.erro("meta.contagens.politicos diferente do número de parlamentares")

    # ---------------- partidos
    for pt in parts:
        membros = [p for p in pols if p["casa"] == pt["casa"] and p["partido"] == pt["sigla"]]
        if pt["n"] != len(membros) or not _perto(pt["total"], sum(p["total"] for p in membros), len(membros)):
            r.erro(f"Partido {pt['casa']}/{pt['sigla']}: número de membros ou total não bate com os parlamentares")

    # ---------------- votações
    vids = Counter(v["id"] for v in vots)
    for i, n in vids.items():
        if n > 1:
            r.erro(f"Votação repetida em votacoes.json: {i} ({n} vezes)")
    if len(vots) < minimos["votacoes"]:
        r.erro(f"Poucas votações: {len(vots)} (mínimo {minimos['votacoes']})")
    for v in vots:
        d = _ler(saida / "v" / f"{v['id']}.json", r)
        if d is None:
            continue
        quem = Counter(x["politico"] for x in d.get("votos", []))
        rep = [k for k, n in quem.items() if n > 1]
        if rep:
            r.erro(f"Votação {v['id']}: parlamentares votando mais de uma vez: {rep[:5]}")
        cont = Counter(x["voto"] for x in d.get("votos", []))
        if v["sim"] != cont.get("Sim", 0) or v["nao"] != cont.get("Não", 0) or dict(cont) != d.get("contagem"):
            r.erro(f"Votação {v['id']}: placar (sim {v['sim']}, não {v['nao']}) não bate com os votos")
        fora = [k for k in quem if k not in por_id]
        if fora:
            r.erro(f"Votação {v['id']}: votos de parlamentares desconhecidos: {fora[:5]}")
    # mesma casa, mesmo dia, mesma proposta, mesma descrição e mesmo placar: provavelmente a mesma votação duas vezes
    assin = Counter((v["casa"], v["data"], json.dumps(v.get("proposicao"), sort_keys=True), v.get("descricao"), v["sim"], v["nao"])
                    for v in vots)
    dup = sum(n - 1 for n in assin.values() if n > 1)
    if dup:
        r.alerta(f"{dup} votações com mesma casa, dia, proposta, descrição e placar (podem ser repetidas)")

    # ---------------- empresas
    vistos = Counter(e["cnpj"] for e in emps)
    for c, n in vistos.items():
        if n > 1:
            r.erro(f"Empresa repetida em empresas.json: {c}")
    if [e["total"] for e in emps] != sorted((e["total"] for e in emps), reverse=True):
        r.erro("empresas.json fora de ordem (deveria estar do maior para o menor total)")
    for e in emps:  # a soma dos anos tem que bater com o total (as listas do site mostram o ano escolhido)
        if "por_ano" in e and abs(sum(x["valor"] for x in e["por_ano"].values()) - e["total"]) > 0.05:
            r.erro(f"Empresa {e['cnpj']}: soma dos anos diferente do total em empresas.json")
    for f in sorted((saida / "e").glob("*.json")) if (saida / "e").exists() else []:
        _conferir_empresa(saida, f, por_id, r)

    # ---------------- emendas
    _conferir_emendas(saida, r)

    # ---------------- incentivos (pagamentos a empresas e renúncia fiscal)
    _conferir_incentivos(saida, r)

    # ---------------- arrecadação e gastos (primeira aba)
    _conferir_financas(saida, r)

    # ---------------- projetos em andamento (aba de votações)
    _conferir_tramitacao(saida, r)

    # ---------------- privacidade e links (em todos os arquivos)
    for f in sorted(saida.rglob("*.json")):
        x = _ler(f, r)
        if x is not None:
            _varrer(x, str(f.relative_to(saida)), r)

    # ---------------- páginas oficiais (alerta)
    for ano in anos:
        com = [p for p in pols if p["casa"] == "camara" and (p["por_ano"].get(ano) or {}).get("cota_oficial") is not None]
        if not com:
            continue
        def compara(a):
            return a["total"] - (a.get("fora_do_periodo") or 0)
        dif = [p for p in com if abs(p["por_ano"][ano]["cota_oficial"] - compara(p["por_ano"][ano]))
               > max(50, 0.005 * abs(compara(p["por_ano"][ano])))]
        if len(dif) > 0.1 * len(com):
            r.alerta(f"{ano}: {len(dif)} de {len(com)} deputados com total da cota diferente da página oficial")

    # ---------------- queda em relação à versão publicada
    if anterior:
        _comparar_anterior(meta, anterior, r, ignorar_queda)
    for a in meta.get("avisos") or []:
        r.alerta(f"Aviso da coleta: {a}")
    return r


def _conferir_politico(saida: Path, p: dict, r: Resultado) -> None:
    d = _ler(saida / "p" / f"{p['id']}.json", r)
    if d is None:
        return
    for ano, a in (d.get("anos") or {}).items():
        resumo = (p.get("por_ano") or {}).get(ano) or {}
        if not _perto(a["total"], resumo.get("total", 0)):
            r.erro(f"{p['id']} {ano}: total do detalhe ({a['total']}) diferente do resumo ({resumo.get('total')})")
        cats = a.get("categorias") or []
        if not _perto(a["total"], sum(c["valor"] for c in cats), len(cats)):
            r.erro(f"{p['id']} {ano}: soma das categorias diferente do total")
        meses = a.get("meses") or []
        if not _perto(a["total"], sum(m["valor"] for m in meses), len(meses)):
            r.erro(f"{p['id']} {ano}: soma dos meses diferente do total")
        if any(not 1 <= m["mes"] <= 12 for m in meses):
            r.alerta(f"{p['id']} {ano}: despesa com mês fora de 1 a 12")
    vs = Counter(v["votacao"] for v in d.get("votos") or [])
    if any(n > 1 for n in vs.values()):
        r.erro(f"{p['id']}: a mesma votação aparece mais de uma vez nos votos")
    if d.get("n_votos") != len(d.get("votos") or []):
        r.erro(f"{p['id']}: n_votos diferente da lista de votos")


def _conferir_empresa(saida: Path, f: Path, por_id: dict, r: Resultado) -> None:
    e = _ler(f, r)
    if e is None:
        return
    c = e.get("cnpj", "")
    if f.stem != c or not re.fullmatch(r"\d{14}", c):
        r.erro(f"Arquivo de empresa com CNPJ inválido: {f.name}")
        return
    pag = e.get("pagadores") or []
    if not _perto(e["total"], sum(x["valor"] for x in pag), len(pag)):
        r.erro(f"Empresa {c}: total {e['total']} diferente da soma dos pagadores")
    if any(x["politico"] not in por_id for x in pag):
        r.erro(f"Empresa {c}: pagador que não está na lista de parlamentares")
    pm = e.get("por_mes") or []
    if pm and not _perto(e["total"], sum(x["valor"] for x in pm), len(pm)):
        r.erro(f"Empresa {c}: total diferente da soma mensal")
    soma_notas, n_notas = 0.0, 0
    for ano, n in (e.get("notas_por_ano") or {}).items():
        notas = _ler(saida / "e" / "notas" / f"{c}-{ano}.json", r) or []
        if len(notas) != n:
            r.erro(f"Empresa {c} {ano}: {len(notas)} notas no arquivo, {n} no resumo")
        soma_notas += sum(x[3] for x in notas)
        n_notas += len(notas)
        # cada nota: [data, parlamentar, categoria, valor, link, tipo de link, detalhe]
        for x in notas:
            if x[4] and (not re.match(r"^https?://", x[4], re.I) or CPF_NO_LINK.search(x[4])):
                r.erro(f"Empresa {c} {ano}: link de nota inseguro (não é http(s) ou leva CPF): {x[4][:80]!r}")
            if x[1] not in por_id:
                r.erro(f"Empresa {c} {ano}: nota de parlamentar desconhecido {x[1]}")
                break
    if e.get("n_notas") is not None and (n_notas != e["n_notas"] or not _perto(soma_notas, e["total"], n_notas)):
        r.erro(f"Empresa {c}: as notas (R$ {soma_notas:.2f}, {n_notas}) não batem com o total (R$ {e['total']})")
    for k in ("governo", "renuncia"):
        x = e.get(k)
        if x and not _perto(x["total"], sum((x.get("por_ano") or {}).values()), len(x.get("por_ano") or {})):
            r.erro(f"Empresa {c}: total de {k} ({x['total']}) diferente da soma dos anos")
    for d in e.get("donos_finais") or []:
        cadeia = [x["cnpj"][:8] for x in d.get("cadeia") or []]
        if d.get("fim") not in FINS:
            r.erro(f"Empresa {c}: dono final com fim desconhecido {d.get('fim')!r}")
        if len(cadeia) > MAX_NIVEL + 1:
            r.erro(f"Empresa {c}: cadeia de holdings maior que o limite ({len(cadeia)})")
        if d.get("fim") != "ciclo" and (len(set(cadeia)) != len(cadeia) or c[:8] in cadeia):
            r.erro(f"Empresa {c}: cadeia de holdings repete empresa sem marcar ciclo")


def _conferir_emendas(saida: Path, r: Resultado) -> None:
    pasta = saida / "emendas"
    if not (pasta / "anos.json").exists():
        r.alerta("Sem dados de emendas (emendas/anos.json)")
        return
    idx = _ler(pasta / "anos.json", r) or {}
    for ano in idx.get("anos", []):
        d = _ler(pasta / f"{ano}.json", r)
        if d is None:
            continue
        t = d["total"]
        for nome, lista in (("tipo", d.get("por_tipo") or []), ("área", d.get("por_area") or [])):
            if not _perto(t["empenhado"], sum(x["empenhado"] for x in lista), len(lista)) or \
                    not _perto(t["pago"], sum(x["pago"] for x in lista), len(lista)):
                r.erro(f"Emendas {ano}: soma por {nome} diferente do total")
        if t["pago"] - t["empenhado"] > 0.01 * max(t["empenhado"], 1):
            r.alerta(f"Emendas {ano}: pago (inclui restos a pagar de anos anteriores) maior que o empenhado")
        fav = d.get("favorecidos")
        if fav:
            cats = fav.get("por_categoria") or []
            if not _perto(fav["total"], sum(x["valor"] for x in cats), len(cats)):
                r.erro(f"Emendas {ano}: total dos favorecidos diferente da soma por categoria")


def _conferir_incentivos(saida: Path, r: Resultado) -> None:
    pasta = saida / "incentivos"
    if not (pasta / "indice.json").exists():
        r.alerta("Sem dados da página de incentivos (incentivos/indice.json)")
        return
    idx = _ler(pasta / "indice.json", r) or {}
    for ano in idx.get("anos", []):
        d = _ler(pasta / f"{ano}.json", r) or {}
        p = d.get("pagamentos")
        if p:
            cats = p.get("por_categoria") or []
            if not _perto(p["total"], sum(x["valor"] for x in cats), len(cats)):
                r.erro(f"Incentivos {ano}: total dos pagamentos diferente da soma por categoria")
            top = [x["valor"] for x in p.get("top") or []]
            if top != sorted(top, reverse=True) or (top and top[0] > p["total"] + 0.01):
                r.erro(f"Incentivos {ano}: lista dos que mais receberam fora de ordem ou maior que o total")
            dest = p.get("destino")
            if dest:
                if not _perto(dest["privado"]["total"], p["total"], 1):
                    r.erro(f"Incentivos {ano}: total privado do destino diferente do total dos pagamentos")
                esf = dest["publico"].get("por_esfera") or []
                if not _perto(dest["publico"]["total"], sum(x["valor"] for x in esf), len(esf)):
                    r.erro(f"Incentivos {ano}: total público diferente da soma por esfera")
        em = d.get("emendas")
        if em:
            soma = sum(x["valor"] for x in em.get("politicos") or []) + sum(x["valor"] for x in em.get("coletivos") or [])
            if em.get("n_politicos", 0) <= len(em.get("politicos") or []) and len(em.get("coletivos") or []) < 40 \
                    and not _perto(em["total"], soma, len(em.get("politicos") or []) + 1):
                r.erro(f"Incentivos {ano}: total das emendas a empresas diferente da soma por parlamentar")
            ps = em.get("partidos") or []
            if sum(x["valor"] for x in ps) > em["total"] + 0.01 * max(len(ps), 1):
                r.erro(f"Incentivos {ano}: soma dos partidos maior que o total das emendas a empresas")
    for x in idx.get("anos_renuncia", []):
        d = _ler(pasta / f"renuncia-{x['ano']}.json", r) or {}
        if not d:
            continue
        for nome, lista in (("estado", [[u, v] for u, v, *_ in d.get("por_uf") or []]),
                            ("setor", [[s["setor"], s["valor"]] for s in d.get("por_setor") or []])):
            if not _perto(d["total"], sum(v for _, v in lista), len(lista)):
                r.erro(f"Renúncia {x['ano']}: soma por {nome} diferente do total")
        top = [e["valor"] for e in d.get("top") or []]
        if top != sorted(top, reverse=True):
            r.erro(f"Renúncia {x['ano']}: lista das empresas fora de ordem")


def _conferir_tramitacao(saida: Path, r: Resultado) -> None:
    """Cada proposta tem link oficial e id seguro, sem repetição; a agenda só aponta para propostas da lista."""
    f = saida / "tramitacao.json"
    if not f.exists():
        r.alerta("Sem a lista de projetos em andamento (tramitacao.json)")
        return
    d = _ler(f, r) or {}
    ids = Counter(i.get("id") for i in d.get("itens", []))
    for i, n in ids.items():
        if n > 1:
            r.erro(f"Projeto em andamento repetido: {i} ({n} vezes)")
    for i in d.get("itens", []):
        if not id_seguro(i.get("id")):
            r.erro(f"Projeto em andamento com id inválido: {i.get('id')!r}")
        if not str(i.get("url") or "").startswith(("https://www.camara.leg.br/", "https://www25.senado.leg.br/")):
            r.erro(f"Projeto em andamento sem link oficial: {i.get('id')}")
        if not i.get("grupos"):
            r.erro(f"Projeto em andamento sem motivo para estar na lista: {i.get('id')}")
    for ev in d.get("agenda", []):
        fora = [x for x in ev.get("itens", []) if x not in ids]
        if fora:
            r.erro(f"Agenda {ev.get('id')} aponta para propostas que não estão na lista: {fora[:3]}")


def _conferir_financas(saida: Path, r: Resultado) -> None:
    """Partes somam o total (com folga de 0,01% para arredondamentos) e todo sinal tem um nível conhecido."""
    pasta = saida / "financas"
    if not (pasta / "indice.json").exists():
        r.alerta("Sem dados da aba de arrecadação e gastos (financas/indice.json)")
        return
    idx = _ler(pasta / "indice.json", r) or {}

    def igual(a: float, b: float) -> bool:
        return abs((a or 0) - (b or 0)) <= max(1.0, 1e-4 * abs(a or 0))

    for ano in idx.get("anos", []):
        d = _ler(pasta / f"{ano}.json", r) or {}
        if not d:
            continue
        if not (d.get("rreo") or {}).get("receitas"):
            r.erro(f"Finanças {ano}: sem receitas do Tesouro (RREO)")
        ex = d.get("executivo")
        if ex and not igual(ex["total"], sum(c["realizado"] for c in ex.get("categorias") or [])):
            r.erro(f"Finanças {ano}: gasto do Executivo diferente da soma das categorias")
        fu = d.get("funcoes")
        if fu and not fu.get("confere"):
            r.alerta(f"Finanças {ano}: a soma das funções de governo não bate com o total do Tesouro")
        a = d.get("arrecadacao")
        if a:
            if not igual(a["total"], sum(g["valor"] for g in a.get("grupos") or [])):
                r.erro(f"Finanças {ano}: arrecadação diferente da soma por grupo de imposto")
            if a.get("por_uf") and not igual(a["total"], sum(u[1] if isinstance(u, list) else u["valor"] for u in a["por_uf"])):
                r.erro(f"Finanças {ano}: arrecadação diferente da soma por estado")
        pe = d.get("pessoal_executivo")
        if pe and pe["pessoas"] != sum(g["pessoas"] for g in pe.get("grupos") or []):
            r.erro(f"Finanças {ano}: servidores do Executivo diferente da soma dos grupos")
        for k in d.get("kpis") or []:
            if k.get("nivel") not in ("verde", "amarelo", "vermelho", "sem_dados"):
                r.erro(f"Finanças {ano}: sinal {k.get('id')} com nível desconhecido")
            if k.get("nivel") != "sem_dados" and not isinstance(k.get("valor"), (int, float)):
                r.erro(f"Finanças {ano}: sinal {k.get('id')} sem valor")


def _comparar_anterior(meta: dict, ant: dict, r: Resultado, ignorar: bool) -> None:
    """Uma queda grande de um dia para o outro quase sempre é falha de coleta, não mudança real."""
    msgs = []
    for ano, v in (ant.get("total_por_ano") or {}).items():
        novo = (meta.get("total_por_ano") or {}).get(ano)
        if novo is not None and v > 0 and novo < v * (1 - QUEDA_MAXIMA):
            msgs.append(f"total da cota de {ano} caiu de R$ {v:,.2f} para R$ {novo:,.2f}")
    for k in ("politicos", "votacoes", "despesas"):
        v, novo = (ant.get("contagens") or {}).get(k), (meta.get("contagens") or {}).get(k)
        if v and novo is not None and novo < v * (1 - QUEDA_MAXIMA):
            msgs.append(f"número de {k} caiu de {v} para {novo}")
    for m in msgs:
        (r.alerta if ignorar else r.erro)(f"Queda em relação à versão publicada: {m}")


def _baixar_anterior(url: str) -> dict | None:
    if not url:
        return None
    try:
        if re.match(r"^https?://", url):
            import requests
            resp = requests.get(url, timeout=30)
            return resp.json() if resp.ok else None
        return json.loads(Path(url).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - sem a versão anterior, só não comparamos
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("saida", type=Path)
    ap.add_argument("--anterior", default="", help="meta.json publicado antes (URL ou arquivo)")
    ap.add_argument("--ignorar-queda", action="store_true", help="queda grande vira alerta, não erro")
    a = ap.parse_args(argv)
    ant = _baixar_anterior(a.anterior)
    r = validar(a.saida, anterior=ant, ignorar_queda=a.ignorar_queda)
    print("## Conferência dos dados\n")
    if a.anterior and ant is None:
        r.alerta("Não foi possível ler a versão publicada antes; a comparação de quedas ficou de fora")
    print(f"- {len(r.erros)} erros, {len(r.alertas)} alertas\n")
    for e in r.erros[:60]:
        print(f"- ERRO: {e}")
    for x in r.alertas[:60]:
        print(f"- alerta: {x}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
