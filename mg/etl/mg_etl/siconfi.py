"""Onde a prefeitura gasta: despesas de cada cidade por área (saúde, educação, Câmara...), ano a ano.

Fonte: SICONFI, o sistema do Tesouro Nacional onde cada prefeitura entrega as contas do ano (Declaração de
Contas Anuais, DCA). API aberta: https://apidatalake.tesouro.gov.br/ords/siconfi/tt/
- /entes: lista de prefeituras com o código do IBGE;
- /dca?an_exercicio=&no_anexo=DCA-Anexo I-E&id_ente=: despesas por função (área) e subfunção, com os valores
  empenhados (reservados), liquidados (serviço entregue) e pagos.

As contas de um ano são entregues até abril do ano seguinte. Anos já entregues não mudam: ficam no cache.

O ano em curso vem do RREO (Relatório Resumido da Execução Orçamentária), que estado e prefeituras entregam a cada
dois meses: /rreo?no_anexo=RREO-Anexo 02 traz a despesa por função e subfunção, empenhada e liquidada até o
bimestre. O RREO não traz o valor pago por função; por isso o ano em curso aparece como parcial e sem o "pago".
Para comparar sem enganar, o mesmo bimestre do ano anterior também é lido (até agosto de 2026 contra até agosto
de 2025, e não contra o ano inteiro).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
from collections import defaultdict
from pathlib import Path

import time

from sa_etl.fin_tesouro import FUNCOES as NOMES_FUNCOES, _subfuncao_nome
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


def municipios(uf: str, cache: Path) -> dict[str, str]:
    """Nome oficial de cada município de uma UF, pela API do Tesouro (lista de entes): chave sem acento -> nome.
    Vazio se a API e a cópia guardada faltarem."""
    entes = _entes(cache)
    return {re.sub(r"[^A-Z]", "", norm_name(e.get("ente") or "")): e["ente"] for e in entes
            if e.get("uf") == uf and str(e.get("esfera") or "M").upper().startswith("M") and e.get("ente")}


def _entes(cache: Path) -> list[dict]:
    alvo = cache / "siconfi" / "entes.json"
    entes = _ENTES.get(str(alvo))
    if entes is not None:
        return entes
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
    return entes or []


def codigo_ibge(nome: str, uf: str, cache: Path) -> int | None:
    return _achar(_entes(cache), nome, uf)


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


# Código do estado de Minas Gerais no IBGE (e no SICONFI, que usa o mesmo código para o governo estadual)
COD_MG = 31


def contas_estado(cache: Path, hoje: dt.date | None = None) -> dict | None:
    """Despesas do governo de Minas por área, ano a ano: o mesmo anexo da DCA que as prefeituras entregam."""
    return contas_do_ente(COD_MG, "o estado de Minas Gerais", cache, hoje)


def contas(nome: str, uf: str, cache: Path, hoje: dt.date | None = None) -> dict | None:
    cod = codigo_ibge(nome, uf, cache)
    if not cod:
        avisar(f"SICONFI: não achamos {nome} na lista do Tesouro; as contas da prefeitura ficaram de fora")
        return None
    return contas_do_ente(cod, nome, cache, hoje)


# ---------------------------------------------------------------- ano em curso (RREO, a cada bimestre)

ANEXO_RREO = "RREO-Anexo 02"
MES_DO_BIMESTRE = {1: "fevereiro", 2: "abril", 3: "junho", 4: "agosto", 5: "outubro", 6: "dezembro"}
# Código de cada função (Portaria 42/1999): a lista do coletor nacional está na ordem dos códigos, 01 a 28
CODIGO_FUNCAO = {norm_name(n): f"{i:02d}" for i, n in enumerate(NOMES_FUNCOES, start=1)}
CODIGO_FUNCAO[norm_name("Reserva de Contingência")] = "99"
RELER_HORAS = 20


def rreo2(ano: int, bimestre: int, cod: int, cache: Path, hoje: dt.date) -> list[dict] | None:
    """Linhas do Anexo 02 do RREO de um bimestre. None: o Tesouro não respondeu e não há cópia guardada.
    O ano em curso é relido a cada 20 horas (o ente pode entregar ou corrigir o relatório); anos passados ficam."""
    alvo = cache / "siconfi" / f"rreo2_{cod}_{ano}_{bimestre}.json"
    if alvo.exists() and (ano < hoje.year or time.time() - alvo.stat().st_mtime < RELER_HORAS * 3600):
        try:
            return json.loads(alvo.read_text(encoding="utf-8"))
        except ValueError:
            pass
    esfera = "E" if cod < 100 else "M"
    try:
        r = get(f"{API}/rreo", params={"an_exercicio": ano, "nr_periodo": bimestre, "co_tipo_demonstrativo": "RREO",
                                       "no_anexo": ANEXO_RREO, "co_esfera": esfera, "id_ente": cod}, timeout=90)
        dados = r.json().get("items") or []
    except Exception as e:  # noqa: BLE001
        log.warning("SICONFI RREO %s %s/%s: %s", cod, ano, bimestre, e)
        if alvo.exists():
            try:
                return json.loads(alvo.read_text(encoding="utf-8"))
            except ValueError:
                return None
        return None
    if dados:  # vazio não vai para o cache: o relatório do bimestre pode sair amanhã
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return dados


def resumir_rreo2(dados: list[dict]) -> dict | None:
    """Por função: empenhado e liquidado até o bimestre (sem as intraorçamentárias), e as 3 maiores subfunções.
    Só vale se as funções somarem o total do próprio relatório; senão, nada (melhor faltar que mostrar errado)."""
    def coluna(prefixo: str) -> list[tuple[str, float]]:
        out = []
        for i in dados:
            if i.get("cod_conta") == "RREO2TotalDespesas" and norm_name(str(i.get("coluna") or "")).startswith(prefixo):
                try:
                    out.append((str(i.get("conta") or "").strip(), float(i.get("valor") or 0)))
                except (TypeError, ValueError):
                    continue
        return out

    def por_funcao(linhas: list[tuple[str, float]]) -> tuple[dict, dict, dict, float | None]:
        fun: dict[str, float] = {}
        nomes: dict[str, str] = {}
        sub: dict[str, dict[str, float]] = defaultdict(dict)
        total, atual = None, None
        for nome, v in linhas:
            n = norm_name(nome)
            if n.startswith("DESPESAS (EXCETO") or n.startswith("DESPESAS EXCETO"):
                total = v
                continue
            if n.startswith(("DESPESAS (INTRA", "DESPESAS INTRA", "TOTAL")):
                break  # daqui para baixo é intraorçamentária ou total geral
            c = CODIGO_FUNCAO.get(n)
            if c:
                atual = c
                fun[c] = fun.get(c, 0.0) + v
                nomes[c] = nome
            elif atual:
                s = _subfuncao_nome(nome)
                sub[atual][s] = sub[atual].get(s, 0.0) + v
        return fun, nomes, sub, total

    liq, nomes, sub, total = por_funcao(coluna("DESPESAS LIQUIDADAS ATE"))
    emp, _, _, _ = por_funcao(coluna("DESPESAS EMPENHADAS ATE"))
    if not liq or total is None:
        return None
    soma = sum(liq.values())
    if abs(soma - total) > max(1.0, abs(total) * 0.005):
        log.warning("SICONFI RREO: as funções somam %.2f, mas o total do relatório é %.2f; ano em curso fica de fora", soma, total)
        return None
    funcoes = [{"codigo": c, "funcao": nomes[c], "empenhado": round(emp.get(c, 0.0), 2), "liquidado": round(v, 2), "pago": None,
                "principais": [{"nome": k, "valor": round(x, 2)} for k, x in sorted(sub[c].items(), key=lambda kv: -kv[1])[:3] if x > 0]}
               for c, v in liq.items() if v or emp.get(c)]
    funcoes.sort(key=lambda f: -f["liquidado"])
    instituicao = next((str(i.get("instituicao") or "") for i in dados if i.get("instituicao")), "")
    return {"funcoes": funcoes, "total_empenhado": round(sum(f["empenhado"] for f in funcoes), 2),
            "total_liquidado": round(sum(f["liquidado"] for f in funcoes), 2), "total_pago": None, "instituicao": instituicao}


def ano_em_curso(cod: int, cache: Path, hoje: dt.date) -> dict | None:
    """O ano atual até o último bimestre entregue, com o mesmo bimestre do ano anterior para comparar."""
    ano = hoje.year
    for bim in range(6, 0, -1):
        if dt.date(ano, bim * 2, 1) > hoje:  # o bimestre ainda não acabou
            continue
        dados = rreo2(ano, bim, cod, cache, hoje)
        r = resumir_rreo2(dados) if dados else None
        if not r:
            continue
        ant = rreo2(ano - 1, bim, cod, cache, hoje)
        ra = resumir_rreo2(ant) if ant else None
        return {"ano": ano, "parcial": True, "bimestre": bim, "ate_mes": MES_DO_BIMESTRE[bim], **r,
                "mesmo_periodo_anterior": {"ano": ano - 1, "total_liquidado": ra["total_liquidado"],
                                           "liquidado": {f["codigo"]: f["liquidado"] for f in ra["funcoes"]}} if ra else None,
                "api": f"{API}/rreo?an_exercicio={ano}&nr_periodo={bim}&co_tipo_demonstrativo=RREO"
                       f"&no_anexo={ANEXO_RREO.replace(' ', '%20')}&co_esfera={'E' if cod < 100 else 'M'}&id_ente={cod}"}
    return None


def contas_do_ente(cod: int, nome: str, cache: Path, hoje: dt.date | None = None) -> dict | None:
    hoje = hoje or dt.date.today()
    anos, falhas = [], 0
    try:
        atual = ano_em_curso(cod, cache, hoje)
    except Exception as e:  # noqa: BLE001
        log.warning("SICONFI RREO %s: %s", nome, e)
        atual = None
    if atual:
        anos.append(atual)
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
