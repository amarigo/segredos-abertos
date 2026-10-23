"""Onde a prefeitura gasta: despesas de cada cidade por área (saúde, educação, Câmara...), ano a ano.

Fonte: SICONFI, o sistema do Tesouro Nacional onde cada prefeitura entrega as contas do ano (Declaração de
Contas Anuais, DCA). API aberta: https://apidatalake.tesouro.gov.br/ords/siconfi/tt/
- /entes: lista de prefeituras com o código do IBGE;
- /dca?an_exercicio=&no_anexo=DCA-Anexo I-E&id_ente=: despesas por função (área) e subfunção, com os valores
  empenhados (reservados), liquidados (serviço entregue) e pagos.

As contas de um ano são entregues até abril do ano seguinte. Anos já entregues não mudam: ficam no cache.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
from collections import defaultdict
from pathlib import Path

from sa_etl.util import avisar, get, norm_name

log = logging.getLogger("mg_etl.siconfi")

API = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
PAGINA = "https://siconfi.tesouro.gov.br/siconfi/pages/public/consulta_finbra/finbra_list.jsf"
ANEXO = "DCA-Anexo I-E"
PRIMEIRO_ANO = 2018

COLUNAS = {"empenhado": re.compile(r"empenhad", re.I), "liquidado": re.compile(r"liquidad", re.I),
           "pago": re.compile(r"pag[ao]s?\b|pagas", re.I)}
# "10 - Saúde", "01 - Legislativa"; as subfunções têm ponto: "10.301 - Atenção Básica"
FUNCAO = re.compile(r"^\s*(\d{2})\s*-\s*(.+)$")
SUBFUNCAO = re.compile(r"^\s*(\d{2})\.(\d{3})\s*-\s*(.+)$")


_ENTES: dict[str, list] = {}


def codigo_ibge(nome: str, uf: str, cache: Path) -> int | None:
    alvo = cache / "siconfi" / "entes.json"
    entes = _ENTES.get(str(alvo))
    if entes is not None:
        return _achar(entes, nome, uf)
    try:
        entes = get(f"{API}/entes", timeout=60).json()["items"]
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(json.dumps(entes, ensure_ascii=False), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        log.warning("SICONFI entes: %s", e)
        if alvo.exists():
            entes = json.loads(alvo.read_text(encoding="utf-8"))
    if entes:
        _ENTES[str(alvo)] = entes
    return _achar(entes or [], nome, uf)


def _achar(entes: list[dict], nome: str, uf: str) -> int | None:
    for e in entes:
        if (e.get("uf") == uf and norm_name(e.get("ente") or "") == norm_name(nome)
                and str(e.get("esfera") or "M").upper().startswith("M")):
            return int(e["cod_ibge"])
    return None


def itens(ano: int, cod: int, cache: Path, hoje: dt.date) -> list[dict] | None:
    """Linhas do anexo de despesas por função de um ano. Anos fechados ficam no cache para sempre."""
    alvo = cache / "siconfi" / f"dca_{cod}_{ano}.json"
    if alvo.exists():
        try:
            dados = json.loads(alvo.read_text(encoding="utf-8"))
            if dados:
                return dados
        except ValueError:
            pass
    try:
        r = get(f"{API}/dca", params={"an_exercicio": ano, "no_anexo": ANEXO, "id_ente": cod}, timeout=90)
        dados = r.json().get("items") or []
    except Exception as e:  # noqa: BLE001
        log.warning("SICONFI %s %s: %s", cod, ano, e)
        return None
    fechado = ano < hoje.year - 1 or (ano == hoje.year - 1 and hoje.month >= 7)  # prazo de entrega: 30 de abril
    if dados and fechado:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return dados


def resumir_ano(dados: list[dict]) -> dict | None:
    """Por função: empenhado, liquidado e pago, e as 3 maiores subfunções de cada uma."""
    fun: dict = defaultdict(lambda: {"empenhado": 0.0, "liquidado": 0.0, "pago": 0.0, "sub": defaultdict(float)})
    nomes: dict[str, str] = {}
    instituicoes = set()
    for it in dados:
        col = str(it.get("coluna") or "")
        tipo = next((k for k, rx in COLUNAS.items() if rx.search(col)), None)
        if not tipo or re.search(r"restos|intra", col, re.I) or re.search(r"intra", str(it.get("rotulo") or ""), re.I):
            continue  # restos a pagar e despesas intraorçamentárias (entre órgãos da própria prefeitura) contariam duas vezes
        conta = str(it.get("conta") or "")
        try:
            v = float(it.get("valor") or 0)
        except (TypeError, ValueError):
            continue
        instituicoes.add(str(it.get("instituicao") or ""))
        m = SUBFUNCAO.match(conta)
        if m:
            if tipo == "liquidado":
                fun[m.group(1)]["sub"][m.group(3).strip()] += v
            continue
        m = FUNCAO.match(conta)
        if m:
            fun[m.group(1)][tipo] += v
            nomes[m.group(1)] = m.group(2).strip()
    if not fun:
        return None
    funcoes = [{"codigo": c, "funcao": nomes.get(c, c), "empenhado": round(f["empenhado"], 2),
                "liquidado": round(f["liquidado"], 2), "pago": round(f["pago"], 2),
                "principais": [{"nome": k, "valor": round(x, 2)} for k, x in sorted(f["sub"].items(), key=lambda kv: -kv[1])[:3] if x > 0]}
               for c, f in fun.items() if c in nomes and (f["empenhado"] or f["liquidado"] or f["pago"])]
    funcoes.sort(key=lambda f: -f["liquidado"])
    return {"funcoes": funcoes, "total_empenhado": round(sum(f["empenhado"] for f in funcoes), 2),
            "total_liquidado": round(sum(f["liquidado"] for f in funcoes), 2),
            "total_pago": round(sum(f["pago"] for f in funcoes), 2),
            "instituicao": sorted(i for i in instituicoes if i)[:1][0] if instituicoes - {""} else ""}


def contas(nome: str, uf: str, cache: Path, hoje: dt.date | None = None) -> dict | None:
    hoje = hoje or dt.date.today()
    cod = codigo_ibge(nome, uf, cache)
    if not cod:
        avisar(f"SICONFI: não achamos {nome} na lista do Tesouro; as contas da prefeitura ficaram de fora")
        return None
    anos, falhas = [], 0
    for ano in range(hoje.year - 1, PRIMEIRO_ANO - 1, -1):
        dados = itens(ano, cod, cache, hoje)
        if dados is None:  # o Tesouro não respondeu: depois de 2 anos seguidos sem resposta, desiste (sem esperar à toa)
            falhas += 1
            if falhas >= 2:
                break
            continue
        falhas = 0
        r = resumir_ano(dados) if dados else None
        if r:
            anos.append({"ano": ano, **r})
    if not anos:
        avisar(f"SICONFI: as contas de {nome} não puderam ser baixadas")
        return None
    return {"cod_ibge": cod, "fonte": PAGINA, "api": f"{API}/dca?no_anexo={ANEXO.replace(' ', '%20')}&id_ente={cod}",
            "anos": anos}
