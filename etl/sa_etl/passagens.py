"""Passagens aéreas compradas pelo sistema da Câmara (SIGEPA) que faltam nos dados abertos.

Desde agosto de 2025 o arquivo de dados abertos da Câmara não traz essas passagens, mas a página oficial
de cada deputado soma o valor delas. A lista oficial de despesas da Câmara ("analitico", tipo 998) mostra
cada bilhete: companhia, CNPJ, data, número do bilhete, valor (devoluções aparecem negativas) e um link
para o detalhe. Buscamos essa lista só nos meses em que falta dinheiro em relação ao total oficial.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import logging
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .camara import LISTA_MES
from .categorias import categoria_curta, grupo_de
from .recursos import _get_text
from .util import digits, to_float

log = logging.getLogger("sa_etl.passagens")

SIGEPA = "998"
CATEGORIA = categoria_curta("PASSAGEM AÉREA - SIGEPA")
VERSAO = 1


def _celulas(tr: str) -> list[str]:
    return [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
            for c in re.findall(r"(?s)<td[^>]*>(.*?)</td>", tr)]


def _valor(t: str) -> float | None:
    m = re.search(r"(\()?\s*R\$\s*([\d.]+,\d{2})", t)
    if not m:
        return None
    v = to_float(m.group(2))
    return -v if m.group(1) else v


def parse_lista(h: str) -> list[dict]:
    """Lê a tabela da lista oficial. Cada linha: fornecedor, CNPJ, data, número do documento, valores e link de detalhe."""
    out = []
    corpo = h[h.find("<tbody"):] if "<tbody" in h else h
    for tr in re.findall(r"(?s)<tr[^>]*>(.*?)</tr>", corpo):
        href = re.search(r'href="([^"]*cota-parlamentar/documento\?[^"]*)"', tr)
        cel = _celulas(tr)
        if not href or len(cel) < 4:
            continue
        data = next((c for c in cel if re.fullmatch(r"\d{2}/\d{2}/\d{4}", c)), "")
        valores = [v for v in (_valor(c) for c in cel) if v is not None]
        if not valores:
            continue
        cnpj = next((c for c in cel if re.fullmatch(r"[\d./-]{14,18}", c)), "")
        i = cel.index(data) if data else -1
        numero = cel[i + 1] if 0 <= i < len(cel) - 1 else ""
        link = re.sub(r"\s+", "", html.unescape(href.group(1)))
        out.append({
            "fornecedor": cel[0], "doc": digits(cnpj), "numero": numero,
            "data": f"{data[6:]}-{data[3:5]}-{data[:2]}" if data else "",
            "valor": round(valores[-1], 2),  # última coluna: valor reembolsado
            "url": link if link.startswith("http") else "https://www.camara.leg.br" + link,
        })
    return out


def _num(n: str) -> str:
    """Número do bilhete sem pontuação nem zeros à esquerda, para comparar com os dados abertos."""
    return re.sub(r"[^0-9A-Z]", "", (n or "").upper()).lstrip("0")


def coletar(meses: list[tuple[str, str, int, int]], existentes: list[dict], falta: dict, cache: Path,
            workers: int = 6, minutos: float = 15) -> list[dict]:
    """meses: (politico, nuDeputadoId, ano, mes) em que falta valor; falta: quanto falta em cada um.

    Devolve só os bilhetes que ainda não estão nos dados abertos. Um bilhete é considerado repetido se o
    mesmo número e valor já aparecem em qualquer mês do deputado. Se mesmo assim a soma do mês passar do
    que falta, tiramos os que coincidem só pelo número ou por companhia e valor; se ainda passar, não usamos
    a lista nesse mês (a diferença fica como "sem nota"), para nunca somar acima do total oficial.

    A lista da Câmara às vezes demora ou não responde. Para a coleta não passar do limite de tempo, as consultas
    param depois de `minutos` (os meses que faltam usam o que já está no cache), e um mês antigo que não
    respondeu só é tentado de novo depois de uma semana.
    """
    cache.mkdir(parents=True, exist_ok=True)
    hoje = dt.date.today()
    prazo = time.monotonic() + minutos * 60
    sem_tempo = 0
    ja_exato = Counter((d["politico"], _num(d.get("num", "")), round(d["valor"], 2)) for d in existentes if _num(d.get("num", "")))
    ja_num = Counter((d["politico"], _num(d.get("num", ""))) for d in existentes if _num(d.get("num", "")))
    ja_valor = Counter((d["politico"], d.get("doc", ""), round(d["valor"], 2)) for d in existentes if d.get("doc"))

    def do_cache(f: Path):
        try:
            return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
        except ValueError:
            return None

    def um(item):
        nonlocal sem_tempo
        pid, nu, ano, mes = item
        f = cache / f"{pid}-{ano}-{mes:02d}-v{VERSAO}.json"
        falhou = f.with_suffix(".falhou")
        antigo = (hoje.year - ano) * 12 + hoje.month - mes > 2  # meses recentes ainda podem mudar
        if antigo and (linhas := do_cache(f)) is not None:
            return item, linhas
        if antigo and falhou.exists() and time.time() - falhou.stat().st_mtime < 7 * 86400:
            return item, None
        if time.monotonic() >= prazo:
            sem_tempo += 1
            return item, do_cache(f)
        h = _get_text(LISTA_MES.format(nu=nu, mes=mes, ano=ano, sub=SIGEPA), timeout=30, tentativas=2)
        if h is None:
            if antigo:
                falhou.touch()
            return item, do_cache(f)
        linhas = parse_lista(h)
        f.write_text(json.dumps(linhas, ensure_ascii=False), encoding="utf-8")
        return item, linhas

    def tira(cand, cont, chave):
        out = []
        for x in cand:
            k = chave(x)
            if k[1] and cont[k] > 0:
                cont[k] -= 1
                continue
            out.append(x)
        return out

    novas, falhas, repetidas, cortados, exemplos = [], 0, 0, 0, []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for (pid, nu, ano, mes), linhas in ex.map(um, meses):
            if linhas is None:
                falhas += 1
                continue
            cand = tira(linhas, ja_exato, lambda x: (pid, _num(x["numero"]), round(x["valor"], 2)))
            repetidas += len(linhas) - len(cand)
            limite = falta.get((pid, ano, mes), 0) + 1
            if sum(x["valor"] for x in cand) > limite:
                cand = tira(cand, ja_num, lambda x: (pid, _num(x["numero"])))
            if sum(x["valor"] for x in cand) > limite:
                cand = tira(cand, ja_valor, lambda x: (pid, x["doc"], round(x["valor"], 2)))
            if sum(x["valor"] for x in cand) > limite:
                cortados += 1
                if len(exemplos) < 5:
                    exemplos.append(f"{pid} {mes:02d}/{ano}: lista R$ {sum(x['valor'] for x in cand):.2f}, falta R$ {limite - 1:.2f}")
                continue
            for x in cand:
                novas.append({
                    "politico": pid, "ano": ano, "mes": mes, "data": x["data"] or f"{ano}-{mes:02d}-01",
                    "categoria": CATEGORIA, "grupo": grupo_de("PASSAGEM AÉREA - SIGEPA"),
                    "fornecedor": x["fornecedor"], "doc": x["doc"], "valor": x["valor"], "url": x["url"],
                    "link": "detalhe", "detalhe": f"Bilhete nº {x['numero']}" if x["numero"] else "",
                    "nu": nu, "num": x["numero"], "fonte_lista": True,
                })
    log.info("Câmara: %d passagens buscadas na lista oficial em %d meses (%d meses sem resposta, %d deixados para a próxima "
             "coleta por falta de tempo, %d bilhetes já nos dados abertos, %d meses em que a lista passaria do total oficial e "
             "não foi usada), R$ %.2f",
             len(novas), len(meses), falhas, sem_tempo, repetidas, cortados, sum(n["valor"] for n in novas))
    for e in exemplos:
        log.info("  lista acima do que falta: %s", e)
    return novas
