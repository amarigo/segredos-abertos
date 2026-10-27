"""Verificação independente: confere os números do site com uma segunda fonte oficial, todo dia.

A conferência de `validar.py` vê se os arquivos do site batem entre si (somas, votos repetidos, CPFs). Esta
verificação vai além: pega, ao acaso, uma amostra dos números já prontos para o site e pergunta de novo a uma fonte
oficial diferente daquela de onde o número veio. Cada número que bate conta como conferido; cada um que não bate
vira uma divergência, com o link para a fonte, e aparece no site e no resumo do GitHub Actions.

O que é conferido e com quê (a fonte da coleta e a fonte da verificação são sempre diferentes):

| Seção | Dado no site (fonte da coleta) | Conferido com |
| --- | --- | --- |
| Cota | total do mês de cada deputado (arquivo anual da cota) | API da Câmara, /deputados/{id}/despesas |
| Cota | quanto cada empresa recebeu de cada deputado no mês (arquivo anual) | API da Câmara, /deputados/{id}/despesas |
| Cota | total do ano de cada senador (API CEAPS, nota por nota) | API do Senado, recursos-utilizados (total oficial) |
| Votações | voto de cada deputado (arquivos CSV de votações) | API da Câmara, /votacoes/{id}/votos |
| Votações | placar oficial da Câmara (arquivo CSV) | API da Câmara, contagem dos votos |
| Votações | placar oficial do Senado (painel de votação) | ata da sessão (Secretaria de Atas, no informe legislativo) |
| Empresas | razão social e sócios (base da Receita, via Minha Receita) | outra cópia da base da Receita (BrasilAPI) |
| Emendas | empenhado e pago de cada autor (arquivo do Portal da Transparência) | API de dados do Portal, consulta de emendas |
| Arrecadação e gastos | juros da dívida (arquivo do orçamento do Portal) | Tesouro Nacional, RREO (API do SICONFI) |

Por que as amostras: conferir tudo, todo dia, levaria horas e sobrecarregaria as APIs do governo. Uma amostra ao
acaso, nova a cada dia, mede a taxa de erro com uma conta conhecida (intervalo de Clopper-Pearson): com n números
conferidos e nenhuma divergência, temos 95% de confiança de que a taxa de erro é menor que 1 - 0,05^(1/n). Para
afirmar "pelo menos 99,99% certos" é preciso conferir cerca de 30 mil números sem nenhum erro. Por isso as amostras
de cada dia se somam às dos dias anteriores (últimos 90 dias), e o site mostra o total acumulado.

Regras de honestidade:
- uma seção só aparece como "conferida" se todas as suas checagens rodaram e nenhuma achou divergência;
- se uma fonte não respondeu, a checagem fica "não conferida" (nunca "conferida");
- dados do mês corrente e do anterior mudam (notas lançadas com atraso): a cota só é conferida em meses fechados
  há mais de 60 dias, e isso aparece escrito no site;
- seções sem uma segunda fonte (ainda) aparecem como "sem segunda fonte".

Uso:
    python -m sa_etl.verificar ../site/public/data [--anterior https://.../data/verificacao.json] [--minutos 20]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import math
import random
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

from .camara import API as API_CAMARA, normaliza_voto
from .emendas import _chave
from .senado import LEGIS, _as_list, normaliza_voto_senado
from .util import chave_portal, digits, get_json, norm_name, to_float, write_json

log = logging.getLogger("sa_etl.verificar")

SENADO_RECURSOS = "https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/{cod}/recursos-utilizados?ano={ano}"
BRASILAPI = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
PORTAL_EMENDAS = "https://api.portaldatransparencia.gov.br/api-de-dados/emendas"
PAGINA_CAMARA_MES = "https://www.camara.leg.br/deputados/{id}?ano={ano}"
PAGINA_EMENDAS_AUTOR = "https://portaldatransparencia.gov.br/emendas/consulta?ano={ano}&autor={autor}"

DIAS_MES_FECHADO = 60  # a cota só é conferida em meses que acabaram há mais que isso
DIAS_HISTORICO = 90
CONFIANCA = 0.95
AMOSTRAS = {  # quantos itens por checagem, por dia
    "cota_camara_mes": 40, "cota_camara_empresa": 40, "cota_senado_ano": 30,
    "votos_camara": 12, "votos_senado": 8, "empresas_receita": 25, "emendas_autor": 15,
}

SECOES = {
    "cota": "Gastos da cota parlamentar",
    "votacoes": "Votações",
    "empresas": "Empresas e donos",
    "emendas": "Emendas parlamentares",
    "financas": "Arrecadação e gastos do governo",
    "incentivos": "Dinheiro público para empresas",
}
# Seções que ainda não têm uma segunda fonte oficial para conferir, e por quê
SEM_SEGUNDA_FONTE = {
    "incentivos": "Os pagamentos e a renúncia fiscal vêm direto do Portal da Transparência e da Receita Federal. Ainda não "
                  "há uma segunda fonte oficial com o mesmo dado para conferir; os totais passam só pela conferência de somas.",
}


# ---------------------------------------------------------------- estatística

def _binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) para X ~ Binomial(n, p), em logaritmos para não estourar com n grande."""
    if p <= 0:
        return 1.0
    if p >= 1:
        return 0.0 if k < n else 1.0
    lp, lq = math.log(p), math.log1p(-p)
    tot = 0.0
    for i in range(k + 1):
        tot += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq)
    return min(tot, 1.0)


def erro_maximo(n: int, k: int, confianca: float = CONFIANCA) -> float | None:
    """Limite superior (Clopper-Pearson, unilateral) da taxa de erro com k divergências em n conferidos."""
    if n <= 0:
        return None
    alfa = 1 - confianca
    if k == 0:
        return 1 - alfa ** (1 / n)
    if k >= n:
        return 1.0
    lo, hi = k / n, 1.0
    for _ in range(60):  # bisseção: o maior p com P(X <= k) >= alfa
        mid = (lo + hi) / 2
        if _binom_cdf(k, n, mid) > alfa:
            lo = mid
        else:
            hi = mid
    return hi


def conferidos_para(certeza: float, confianca: float = CONFIANCA) -> int:
    """Quantos números conferidos, sem nenhum erro, para afirmar 'pelo menos `certeza` certos'."""
    return math.ceil(math.log(1 - confianca) / math.log(certeza))


# ---------------------------------------------------------------- registro das checagens

class Checagem:
    def __init__(self, cid: str, secao: str, titulo: str, como: str, fonte: str) -> None:
        self.id, self.secao, self.titulo, self.como, self.fonte = cid, secao, titulo, como, fonte
        self.n = 0
        self.k = 0
        self.divergencias: list[dict] = []
        self.exemplos: list[dict] = []  # alguns que bateram, para quem quiser conferir com os próprios olhos
        self.falhas: list[str] = []  # itens que não deu para conferir (fonte fora do ar)
        self.motivo = ""  # por que a checagem inteira não rodou
        self.completados = 0  # só na comparação com a página oficial: meses que o site completou com ela

    def bateu(self, ok: bool, item: dict) -> None:
        self.n += 1
        if ok:
            if len(self.exemplos) < 3:
                self.exemplos.append(item)
        else:
            self.k += 1
            if len(self.divergencias) < 20:
                self.divergencias.append(item)

    def falhou(self, msg: str) -> None:
        if len(self.falhas) < 50:
            self.falhas.append(msg)

    @property
    def status(self) -> str:
        if self.k:
            return "divergente"
        if self.n == 0:
            return "nao_conferido"
        return "conferido"

    def json(self) -> dict:
        return {"id": self.id, "secao": self.secao, "titulo": self.titulo, "como": self.como, "fonte": self.fonte,
                "status": self.status, "conferidos": self.n, "divergentes": self.k,
                "nao_conferidos": len(self.falhas), **({"completados": self.completados} if self.completados else {}),
                "motivo": self.motivo or (self.falhas[0] if self.n == 0 and self.falhas else ""),
                "divergencias": self.divergencias, "exemplos": self.exemplos}


class Prazo:
    """Tempo máximo da verificação inteira; o que não couber fica para o dia seguinte (com outra amostra)."""

    def __init__(self, minutos: float) -> None:
        self.fim = time.monotonic() + minutos * 60

    def acabou(self) -> bool:
        return time.monotonic() > self.fim


def _ler(f: Path) -> Any:
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None


def _perto(a: float, b: float, n: int = 1) -> bool:
    return abs((a or 0) - (b or 0)) <= 0.011 * max(n, 1) + 0.01


def _mes_fechado(ano: int, mes: int, hoje: dt.date) -> bool:
    fim = dt.date(ano + (mes == 12), mes % 12 + 1, 1) - dt.timedelta(days=1)
    return (hoje - fim).days > DIAS_MES_FECHADO


def _num(pid: str) -> str:
    return pid.split("-", 1)[1]


# ---------------------------------------------------------------- cota da Câmara

class DespesasCamara:
    """Despesas de um deputado num mês, pela API da Câmara (com cache, para as duas checagens da cota)."""

    def __init__(self, buscar: Callable = get_json) -> None:
        self.buscar = buscar
        self.cache: dict[tuple[str, int, int], list[dict] | None] = {}
        self.com_dados = 0  # quantas respostas vieram com alguma despesa

    def url(self, num: str, ano: int, mes: int) -> str:
        return f"{API_CAMARA}/deputados/{num}/despesas?ano={ano}&mes={mes}&itens=100&ordem=ASC&ordenarPor=dataDocumento"

    def mes(self, num: str, ano: int, mes: int) -> list[dict]:
        k = (num, ano, mes)
        if k not in self.cache:
            linhas: list[dict] = []
            url: str | None = self.url(num, ano, mes)
            paginas = 0
            while url:
                d = self.buscar(url, timeout=60)
                if not isinstance(d, dict) or not isinstance(d.get("dados"), list):
                    raise ValueError("resposta inesperada da API da Câmara")
                linhas += d["dados"]
                self.com_dados += bool(d["dados"])
                url = next((l["href"] for l in d.get("links") or [] if l.get("rel") == "next"), None)
                paginas += 1
                if paginas > 30:
                    raise ValueError("paginação da API da Câmara não terminou")
            self.cache[k] = linhas
        return self.cache[k]


def cota_camara(saida: Path, pols: list[dict], rng: random.Random, prazo: Prazo, hoje: dt.date,
                api: DespesasCamara) -> tuple[Checagem, Checagem]:
    c_mes = Checagem(
        "cota_camara_mes", "cota", "Total do mês de cada deputado",
        f"Sorteamos deputados e meses e somamos, na API oficial da Câmara, todas as despesas daquele mês. A soma tem de "
        f"ser igual à do site. Só meses que terminaram há mais de {DIAS_MES_FECHADO} dias (antes disso a Câmara ainda "
        f"lança notas atrasadas). A parte que o site completa com a página oficial do deputado (passagens compradas pela "
        f"própria Câmara) não está na API e fica de fora da comparação.",
        "https://dadosabertos.camara.leg.br/swagger/api.html#/Deputados/despesasDeputado")
    c_emp = Checagem(
        "cota_camara_empresa", "cota", "Quanto cada empresa recebeu de cada deputado no mês",
        "Sorteamos pagamentos da página de cada empresa (empresa, deputado e mês) e somamos, na API oficial da Câmara, "
        "as notas daquele deputado para aquele CNPJ no mês. Tem de dar o mesmo valor.",
        "https://dadosabertos.camara.leg.br/swagger/api.html#/Deputados/despesasDeputado")
    deps = [p for p in pols if p["casa"] == "camara"]
    meses = [(a, m) for a in sorted({int(x) for p in deps for x in p.get("por_ano") or {}}) for m in range(1, 13)
             if _mes_fechado(a, m, hoje)]
    if not deps or not meses:
        c_mes.motivo = c_emp.motivo = f"Nenhum mês da cota fechado há mais de {DIAS_MES_FECHADO} dias"
        return c_mes, c_emp

    # 1) total do mês: sorteio entre todos os deputados e meses (inclusive meses em que o site não tem gasto)
    vazios_mes: list[dict] = []
    vazios_emp: list[dict] = []
    sorteio = rng.sample([(p["id"], a, m) for p in deps for a, m in meses], min(AMOSTRAS["cota_camara_mes"], len(deps) * len(meses)))
    detalhes: dict[str, dict] = {}
    for pid, ano, mes in sorteio:
        if prazo.acabou():
            c_mes.falhou("tempo da verificação acabou")
            break
        if pid not in detalhes:
            detalhes[pid] = _ler(saida / "p" / f"{pid}.json") or {}
        a = (detalhes[pid].get("anos") or {}).get(str(ano)) or {}
        m = next((x for x in a.get("meses") or [] if x["mes"] == mes), {"valor": 0.0})
        nosso = round(m["valor"] - (m.get("fora_dados_abertos") or 0), 2)
        try:
            linhas = api.mes(_num(pid), ano, mes)
        except Exception as e:  # noqa: BLE001
            c_mes.falhou(f"{pid} {mes:02d}/{ano}: API da Câmara não respondeu ({str(e)[:100]})")
            continue
        oficial = round(sum(to_float(x.get("valorLiquido")) for x in linhas), 2)
        item = {"o_que": f"{detalhes[pid].get('nome', pid)}, {mes:02d}/{ano}", "politico": pid,
                "site": nosso, "oficial": oficial, "fonte": api.url(_num(pid), ano, mes)}
        if not linhas and abs(nosso) > 0.01:
            vazios_mes.append(item)  # pode ser a API sem dados; decidimos no fim
        else:
            c_mes.bateu(_perto(nosso, oficial, len(linhas)), item)

    # 2) empresa × deputado × mês: sorteio entre os pagamentos das páginas de empresa
    candidatos = []
    for f in sorted((saida / "e").glob("*.json")) if (saida / "e").exists() else []:
        e = _ler(f) or {}
        for x in e.get("por_mes") or []:
            if str(x.get("politico", "")).startswith("dep-") and _mes_fechado(x["ano"], x["mes"], hoje):
                candidatos.append((e.get("cnpj", f.stem), e.get("nome", ""), x))
    for cnpj, nome, x in rng.sample(candidatos, min(AMOSTRAS["cota_camara_empresa"], len(candidatos))):
        if prazo.acabou():
            c_emp.falhou("tempo da verificação acabou")
            break
        nosso = round(x["valor"] - (x.get("fora_dados_abertos") or 0), 2)
        try:
            linhas = api.mes(_num(x["politico"]), x["ano"], x["mes"])
        except Exception as e:  # noqa: BLE001
            c_emp.falhou(f"{x['politico']} {x['mes']:02d}/{x['ano']}: API da Câmara não respondeu ({str(e)[:100]})")
            continue
        dela = [y for y in linhas if digits(y.get("cnpjCpfFornecedor")) == cnpj]
        oficial = round(sum(to_float(y.get("valorLiquido")) for y in dela), 2)
        item = {"o_que": f"{nome or cnpj} recebeu de {x.get('nome', x['politico'])} em {x['mes']:02d}/{x['ano']}",
                "cnpj": cnpj, "politico": x["politico"], "site": nosso, "oficial": oficial,
                "fonte": api.url(_num(x["politico"]), x["ano"], x["mes"])}
        if not linhas and abs(nosso) > 0.01:
            vazios_emp.append(item)
        else:
            c_emp.bateu(_perto(nosso, oficial, len(dela)), item)
    if not candidatos:
        c_emp.motivo = "Nenhum pagamento a empresa em mês fechado para sortear"
    # A API às vezes responde sem nenhuma despesa para todos os deputados (já aconteceu). Se nenhum mês sorteado veio
    # com dados, a falha é da API e nada foi conferido; se outros meses vieram, o mês vazio é uma divergência de verdade.
    for c, vazios in ((c_mes, vazios_mes), (c_emp, vazios_emp)):
        if api.com_dados:
            for item in vazios:
                c.bateu(False, {**item, "oficial": "nenhuma despesa na API"})
        elif vazios or c.n:
            # meses sem gasto no site e sem dados na API "bateriam" com zero; sem a API, isso não prova nada
            c.n = c.k = 0
            c.exemplos, c.divergencias = [], []
            c.motivo = (f"A API de despesas da Câmara respondeu sem nenhuma despesa em todos os {len(api.cache)} meses "
                        f"pedidos; parece fora do ar para esse dado. Nada foi conferido.")
            for item in vazios:
                c.falhou(f"{item['o_que']}: a API não trouxe nenhuma despesa")
    return c_mes, c_emp


def cota_camara_pagina(saida: Path, pols: list[dict], hoje: dt.date) -> Checagem:
    """Todos os deputados e meses fechados: soma das notas dos dados abertos comparada com a página oficial do deputado."""
    c = Checagem(
        "cota_camara_pagina", "cota", "Total do mês comparado com a página oficial do deputado",
        "Para cada deputado e cada mês fechado, comparamos a soma das notas dos dados abertos com o gasto do mês que a "
        "página oficial do deputado no site da Câmara mostra. Quando a página mostra mais que as notas, o site completa a "
        "diferença com a página (e avisa como 'sem nota'); esses meses não contam como conferidos, porque a igualdade "
        "seria por construção. Conta como divergência quando as notas passam do que a página mostra.",
        "https://www.camara.leg.br/transparencia/gastos-parlamentares")
    completados = 0
    for p in pols:
        if p["casa"] != "camara":
            continue
        d = None
        for ano in p.get("por_ano") or {}:
            if d is None:
                d = _ler(saida / "p" / f"{p['id']}.json") or {}
            a = (d.get("anos") or {}).get(ano) or {}
            pagina = ((a.get("recursos") or {}).get("cota_meses")) or []
            nossos = {m["mes"]: m for m in a.get("meses") or []}
            for pm in pagina:
                if not _mes_fechado(int(ano), pm["mes"], hoje):
                    continue
                m = nossos.get(pm["mes"], {"valor": 0.0})
                if abs(m.get("fora_dados_abertos") or 0) > 0.005:
                    completados += 1
                    continue
                c.bateu(abs(m["valor"] - pm["valor"]) <= 1.0, {
                    "o_que": f"{p['nome']}, {pm['mes']:02d}/{ano}", "politico": p["id"], "site": round(m["valor"], 2),
                    "oficial": pm["valor"], "fonte": PAGINA_CAMARA_MES.format(id=_num(p["id"]), ano=ano)})
    if c.n == 0:
        c.motivo = "Sem os gastos mensais das páginas oficiais dos deputados nesta coleta"
    c.completados = completados
    return c


# ---------------------------------------------------------------- cota do Senado

SEM_TIPO_SENADO = "Não informado"  # categoria das notas do Senado sem tipo de despesa (senado.parse_ceaps)


def cota_senado(pols: list[dict], rng: random.Random, prazo: Prazo, hoje: dt.date, buscar: Callable = get_json,
                saida: Path | None = None) -> Checagem:
    c = Checagem(
        "cota_senado_ano", "cota", "Total do ano de cada senador",
        "O site soma, nota por nota, as despesas da cota (CEAPS) da API do Senado. Conferimos essa soma com o total "
        "oficial que o próprio Senado publica para cada senador (consulta de recursos utilizados). Só anos fechados.",
        "https://adm.senado.gov.br/adm-dadosabertos/swagger-ui/index.html")
    sens = [p for p in pols if p["casa"] == "senado"]
    pares = [(p, a) for p in sens for a in (p.get("por_ano") or {}) if int(a) < hoje.year]
    if not pares:
        c.motivo = "Nenhum ano fechado da cota do Senado no site"
        return c
    for p, ano in rng.sample(pares, min(AMOSTRAS["cota_senado_ano"], len(pares))):
        if prazo.acabou():
            c.falhou("tempo da verificação acabou")
            break
        url = SENADO_RECURSOS.format(cod=_num(p["id"]), ano=ano)
        try:
            d = buscar(url, timeout=60)
            dados = _as_list((d or {}).get("data"))
            cotas = (dados[0] or {}).get("cotas") if dados else None
            if not isinstance(cotas, dict) or "totalValor" not in cotas:
                raise ValueError("resposta sem o total da cota")
            oficial = round(to_float(cotas["totalValor"]), 2)
        except Exception as e:  # noqa: BLE001
            c.falhou(f"{p['id']} {ano}: API do Senado não respondeu ({str(e)[:100]})")
            continue
        nosso = round(p["por_ano"][ano]["total"], 2)
        item = {"o_que": f"{p['nome']}, {ano}", "politico": p["id"], "site": nosso, "oficial": oficial, "fonte": url}
        if abs(nosso - oficial) > 1.0:
            # Já vimos o Senado listar notas sem tipo de despesa que o total oficial dele não soma: dizemos quanto é
            det = ((saida / "p" / f"{p['id']}.json") if saida else None)
            cats = (((_ler(det) or {}).get("anos") or {}).get(ano) or {}).get("categorias") or [] if det else []
            sem_tipo = round(sum(x["valor"] for x in cats if x["categoria"] == SEM_TIPO_SENADO), 2)
            if sem_tipo and abs(nosso - sem_tipo - oficial) <= 1.0:
                item["o_que"] += (f" (a diferença é igual às notas que o Senado lista sem tipo de despesa, {_fmt(sem_tipo)}: "
                                  f"estão na lista oficial de reembolsos, mas o total oficial não as soma)")
        c.bateu(abs(nosso - oficial) <= 1.0, item)
    return c


# ---------------------------------------------------------------- votações

def votos_camara(saida: Path, vots: list[dict], rng: random.Random, prazo: Prazo,
                 buscar: Callable = get_json) -> tuple[Checagem, Checagem]:
    c_votos = Checagem(
        "votos_camara", "votacoes", "Voto de cada deputado",
        "Sorteamos votações e, para cada deputado listado no site, comparamos o voto com o da API oficial da Câmara "
        "(o site lê os arquivos de votações; a API é outra publicação da Câmara).",
        "https://dadosabertos.camara.leg.br/swagger/api.html#/Vota%C3%A7%C3%B5es/votos")
    c_placar = Checagem(
        "placar_camara", "votacoes", "Placar oficial da Câmara",
        "O placar do site (Sim e Não da Câmara inteira) tem de ser igual à contagem dos votos na API oficial.",
        "https://dadosabertos.camara.leg.br/swagger/api.html#/Vota%C3%A7%C3%B5es/votos")
    cam = [v for v in vots if v["casa"] == "camara"]
    for v in rng.sample(cam, min(AMOSTRAS["votos_camara"], len(cam))):
        if prazo.acabou():
            c_votos.falhou("tempo da verificação acabou")
            break
        d = _ler(saida / "v" / f"{v['id']}.json") or {}
        vid = v["id"].removeprefix("cd-")
        url = f"{API_CAMARA}/votacoes/{vid}/votos"
        try:
            r = buscar(url, timeout=60)
            if not isinstance(r, dict) or not isinstance(r.get("dados"), list):
                raise ValueError("resposta inesperada")
        except Exception as e:  # noqa: BLE001
            c_votos.falhou(f"{v['id']}: API da Câmara não respondeu ({str(e)[:100]})")
            continue
        oficial = {f"dep-{(x.get('deputado_') or {}).get('id')}": normaliza_voto(x.get("tipoVoto") or "") for x in r["dados"]}
        if not oficial:
            c_votos.falhou(f"{v['id']}: a API ainda não tem os votos desta votação")
            continue
        titulo = (v.get("proposicao") or {}).get("titulo") or v.get("descricao", "")[:60]
        for x in d.get("votos") or []:
            ok = oficial.get(x["politico"]) == x["voto"]
            c_votos.bateu(ok, {"o_que": f"{x['nome']} em {titulo} ({v['data']})", "votacao": v["id"],
                               "politico": x["politico"], "site": x["voto"], "oficial": oficial.get(x["politico"], "não está na API"),
                               "fonte": url})
        pc = v.get("placar_casa")
        if pc:
            cont = Counter(oficial.values())
            c_placar.bateu(pc["sim"] == cont.get("Sim", 0) and pc["nao"] == cont.get("Não", 0), {
                "o_que": f"{titulo} ({v['data']})", "votacao": v["id"],
                "site": f"Sim {pc['sim']} · Não {pc['nao']}", "oficial": f"Sim {cont.get('Sim', 0)} · Não {cont.get('Não', 0)}",
                "fonte": url})
    return c_votos, c_placar


SIM_ATA = re.compile(r"\bSim\s*[-–:]?\s*(\d+)", re.I)
NAO_ATA = re.compile(r"\bN[ãa]o\s*[-–:]?\s*(\d+)", re.I)


def placar_da_ata(texto: str) -> tuple[int, int] | None:
    """(sim, não) escritos na ata. A ata usa vários formatos ("Sim - 65; Não - 1", "Sim: 72, Pres.: 1, Total: 73").
    Se o texto traz mais de um resultado (várias votações da mesma matéria), não dá para saber qual é: None."""
    sims, naos = SIM_ATA.findall(texto or ""), NAO_ATA.findall(texto or "")
    if len(sims) != 1 or len(naos) > 1 or (not naos and not re.search(r"\btotal\b", texto, re.I)):
        return None
    return int(sims[0]), int(naos[0]) if naos else 0


def votos_senado(saida: Path, vots: list[dict], rng: random.Random, prazo: Prazo,
                 buscar: Callable = get_json) -> tuple[Checagem, Checagem]:
    c_votos = Checagem(
        "votos_senado", "votacoes", "Voto de cada senador",
        "Sorteamos votações e pedimos de novo à API do Senado só aquela sessão de votação. O voto de cada senador listado "
        "no site tem de ser o mesmo. Isso confere a nossa leitura dos dados, não uma segunda publicação.",
        "https://legis.senado.leg.br/dadosabertos/docs/")
    c_ata = Checagem(
        "placar_senado_ata", "votacoes", "Placar do Senado comparado com a ata",
        "O placar do site vem do painel de votação. Comparamos com o resultado escrito na ata da sessão (Secretaria de "
        "Atas e Diários do Senado), que é registrada à parte.",
        "https://legis.senado.leg.br/dadosabertos/docs/")
    sen = [v for v in vots if v["casa"] == "senado"]
    for v in rng.sample(sen, min(AMOSTRAS["votos_senado"], len(sen))):
        if prazo.acabou():
            c_votos.falhou("tempo da verificação acabou")
            break
        d = _ler(saida / "v" / f"{v['id']}.json") or {}
        cod = v["id"].removeprefix("sf-")
        url = f"{LEGIS}/votacao?dataInicio={v['data']}&dataFim={v['data']}"
        try:
            # Pedimos o dia da votação (a consulta por código da sessão às vezes responde 503)
            r = [x for x in _as_list(buscar(f"{LEGIS}/votacao", params={"dataInicio": v["data"], "dataFim": v["data"]}, timeout=60))
                 if str((x or {}).get("codigoSessaoVotacao")) == cod]
            if not r:
                raise ValueError("a sessão de votação não veio na resposta")
        except Exception as e:  # noqa: BLE001
            c_votos.falhou(f"{v['id']}: API do Senado não respondeu ({str(e)[:100]})")
            continue
        sessao = r[0]
        oficial = {f"sen-{x.get('codigoParlamentar')}": normaliza_voto_senado(x.get("siglaVotoParlamentar") or "")
                   for x in _as_list(sessao.get("votos"))}
        titulo = (v.get("proposicao") or {}).get("titulo") or v.get("descricao", "")[:60]
        for x in d.get("votos") or []:
            c_votos.bateu(oficial.get(x["politico"]) == x["voto"], {
                "o_que": f"{x['nome']} em {titulo} ({v['data']})", "votacao": v["id"], "politico": x["politico"],
                "site": x["voto"], "oficial": oficial.get(x["politico"], "não está na API"), "fonte": url})
        m = placar_da_ata((sessao.get("informeLegislativo") or {}).get("texto") or "")
        pc = v.get("placar_casa")
        if m and pc:
            c_ata.bateu((pc["sim"], pc["nao"]) == m, {
                "o_que": f"{titulo} ({v['data']})", "votacao": v["id"], "site": f"Sim {pc['sim']} · Não {pc['nao']}",
                "oficial": f"Sim {m[0]} · Não {m[1]} (ata)", "fonte": url})
    if c_ata.n == 0 and not c_ata.falhas:
        c_ata.motivo = "Nenhuma votação sorteada tinha o placar escrito na ata"
    return c_votos, c_ata


# ---------------------------------------------------------------- empresas

def _nome(s: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", norm_name(s or "").upper()).strip()


def empresas_receita(saida: Path, rng: random.Random, prazo: Prazo, buscar: Callable = get_json) -> Checagem:
    c = Checagem(
        "empresas_receita", "empresas", "Nome e sócios de cada empresa",
        "O site lê a base de CNPJ da Receita Federal pelo Minha Receita. Sorteamos empresas e comparamos a razão social "
        "e a lista de sócios com outra cópia da mesma base oficial, mantida por outro grupo (BrasilAPI). A Receita não "
        "tem uma API pública gratuita de CNPJ. Quando a Receita atualiza a base, uma cópia pode ficar alguns dias à "
        "frente da outra.",
        "https://brasilapi.com.br/docs#tag/CNPJ")
    # sorteio entre as empresas da lista do site (as que mais receberam da cota) que têm dados da Receita
    lista = _ler(saida / "empresas.json") or []
    com_dados = [saida / "e" / f"{e['cnpj']}.json" for e in lista if re.fullmatch(r"\d{14}", str(e.get("cnpj", "")))]
    for f in rng.sample(com_dados, len(com_dados)):
        if c.n >= AMOSTRAS["empresas_receita"]:
            break
        if prazo.acabou():
            c.falhou("tempo da verificação acabou")
            break
        e = _ler(f) or {}
        if not e.get("empresa"):
            continue
        url = BRASILAPI.format(cnpj=f.stem)
        try:
            r = buscar(url, timeout=40)
            if not isinstance(r, dict) or not r.get("razao_social"):
                raise ValueError("resposta sem razão social")
        except Exception as ex:  # noqa: BLE001
            c.falhou(f"{f.stem}: BrasilAPI não respondeu ({str(ex)[:100]})")
            continue
        nossos = sorted(_nome(s.get("nome")) for s in e.get("socios") or [])
        deles = sorted(_nome(s.get("nome_socio")) for s in r.get("qsa") or [])
        ok_nome = _nome(e["empresa"].get("razao_social")) == _nome(r["razao_social"])
        c.bateu(ok_nome and nossos == deles, {
            "o_que": e.get("nome") or f.stem, "cnpj": f.stem,
            "site": f"{e['empresa'].get('razao_social')} · sócios: {', '.join(nossos) or 'nenhum'}",
            "oficial": f"{r['razao_social']} · sócios: {', '.join(deles) or 'nenhum'}", "fonte": url})
    if not com_dados:
        c.motivo = "Nenhuma página de empresa para sortear"
    return c


# ---------------------------------------------------------------- emendas

def emendas_autor(saida: Path, rng: random.Random, prazo: Prazo, chave: str, buscar: Callable = get_json) -> Checagem:
    c = Checagem(
        "emendas_autor", "emendas", "Empenhado e pago por autor de emenda",
        "O site lê o arquivo completo de emendas do Portal da Transparência. Sorteamos autores e somamos, na API de dados "
        "do Portal, todas as emendas daquele autor no ano. O empenhado e o pago (com restos a pagar) têm de ser iguais.",
        "https://api.portaldatransparencia.gov.br/swagger-ui/index.html#/Emendas%20parlamentares")
    if not chave:
        c.motivo = "Sem a chave da API do Portal da Transparência (secret PORTAL_TRANSPARENCIA_CHAVE)"
        return c
    idx = _ler(saida / "emendas" / "anos.json") or {}
    pares = []
    for ano in idx.get("anos") or []:
        for a in (_ler(saida / "emendas" / f"{ano}.json") or {}).get("autores") or []:
            if a.get("chave"):
                pares.append((ano, a))
    if not pares:
        c.motivo = "Sem emendas no site para sortear"
        return c
    for ano, a in rng.sample(pares, min(AMOSTRAS["emendas_autor"], len(pares))):
        if prazo.acabou():
            c.falhou("tempo da verificação acabou")
            break
        emp = pago = 0.0
        achou = 0
        nome_api = ""
        try:
            for pagina in range(1, 60):
                lote = buscar(PORTAL_EMENDAS, params={"ano": ano, "nomeAutor": a["nome"].split(" (no lugar de")[0], "pagina": pagina},
                              headers={"chave-api-dados": chave}, timeout=60)
                if not isinstance(lote, list):
                    raise ValueError("resposta inesperada da API do Portal")
                for x in lote:
                    if _chave(x.get("nomeAutor") or x.get("autor") or "") == a["chave"]:
                        achou += 1
                        nome_api = nome_api or x.get("nomeAutor") or ""
                        emp += to_float(x.get("valorEmpenhado"))
                        pago += to_float(x.get("valorPago")) + to_float(x.get("valorRestoPago"))
                if len(lote) < 15:
                    break
                time.sleep(0.7)  # a API do Portal limita os pedidos por minuto
        except Exception as e:  # noqa: BLE001
            c.falhou(f"{a['nome']} {ano}: API do Portal não respondeu ({str(e)[:100]})")
            continue
        if not achou:
            c.falhou(f"{a['nome']} {ano}: a busca por nome na API não achou o autor")
            continue
        ok = _perto(emp, a["empenhado"], achou) and _perto(pago, a["pago"], achou)
        c.bateu(ok, {"o_que": f"{a['nome']}, {ano}", "politico": a.get("politico"),
                     "site": f"empenhado R$ {a['empenhado']:,.2f} · pago R$ {a['pago']:,.2f}",
                     "oficial": f"empenhado R$ {emp:,.2f} · pago R$ {pago:,.2f}",
                     "fonte": PAGINA_EMENDAS_AUTOR.format(ano=ano, autor=nome_api or a["nome"])})
    return c


# ---------------------------------------------------------------- arrecadação e gastos

def financas_juros(saida: Path) -> Checagem:
    c = Checagem(
        "financas_juros", "financas", "Juros da dívida: Portal da Transparência e Tesouro",
        "O gasto do Executivo vem do arquivo de orçamento do Portal da Transparência (CGU); as despesas por grupo vêm do "
        "relatório do Tesouro (RREO). São publicações de órgãos diferentes. Em cada ano fechado, os juros e encargos da "
        "dívida têm de bater nas duas (tolerância de 0,1%).",
        "https://apidatalake.tesouro.gov.br/docs/siconfi/")
    idx = _ler(saida / "financas" / "indice.json") or {}
    for ano in idx.get("anos") or []:
        d = _ler(saida / "financas" / f"{ano}.json") or {}
        if d.get("parcial") or not d.get("executivo"):
            continue
        portal = next((x.get("realizado") for x in d["executivo"].get("categorias") or [] if x.get("id") == "juros"), None)
        tesouro = next((x.get("liquidado") for x in (d.get("rreo") or {}).get("despesas") or []
                        if isinstance(x, dict) and x.get("id") == "JurosEEncargosDaDivida"), None)
        if not isinstance(portal, (int, float)) or not isinstance(tesouro, (int, float)) or not tesouro:
            continue
        c.bateu(abs(portal - tesouro) <= 0.001 * abs(tesouro), {
            "o_que": f"Juros e encargos da dívida, {ano}", "site": round(portal, 2), "oficial": round(tesouro, 2),
            "fonte": (d.get("fontes_ano") or {}).get("rreo1") or c.fonte})
    if c.n == 0:
        c.motivo = "Nenhum ano fechado com os dois números (Portal e Tesouro) no site"
    return c


# ---------------------------------------------------------------- juntar tudo

def resumo_secoes(checagens: list[Checagem], historico: dict[str, list[dict]], hoje: str) -> dict:
    secoes = {}
    for sid, titulo in SECOES.items():
        cs = [c for c in checagens if c.secao == sid]
        st = [c.status for c in cs]
        if sid in SEM_SEGUNDA_FONTE and not cs:
            status = "sem_segunda_fonte"
        elif "divergente" in st:
            status = "divergente"
        elif st and all(s == "conferido" for s in st):
            status = "conferido"
        elif "conferido" in st:
            status = "parcial"
        else:
            status = "nao_conferido"
        hist = [h for h in historico.get(sid) or [] if h["data"] != hoje]
        n, k = sum(c.n for c in cs), sum(c.k for c in cs)
        if n:
            hist.append({"data": hoje, "n": n, "k": k})
        limite = (dt.date.fromisoformat(hoje) - dt.timedelta(days=DIAS_HISTORICO)).isoformat()
        hist = sorted((h for h in hist if h["data"] >= limite), key=lambda h: h["data"])
        n_ac, k_ac = sum(h["n"] for h in hist), sum(h["k"] for h in hist)
        em = erro_maximo(n_ac, k_ac)
        secoes[sid] = {
            "titulo": titulo, "status": status, "checagens": [c.id for c in cs],
            "hoje": {"conferidos": n, "divergentes": k},
            "acumulado": {"conferidos": n_ac, "divergentes": k_ac, "desde": hist[0]["data"] if hist else None,
                          "dias": len(hist),
                          # com 95% de confiança, pelo menos esta fração dos números está certa
                          "certos_min": None if em is None else round(1 - em, 6)},
            "historico": hist,
            **({"motivo": SEM_SEGUNDA_FONTE[sid]} if status == "sem_segunda_fonte" else {}),
        }
    return secoes


def verificar(saida: Path, anterior: dict | None = None, minutos: float = 20, semente: str | None = None,
              hoje: dt.date | None = None, chave: str | None = None, buscar: Callable = get_json) -> dict:
    hoje = hoje or dt.date.today()
    semente = semente or hoje.isoformat()  # amostra nova a cada dia, e repetível (mesma data, mesma amostra)
    rng = random.Random(f"segredos-abertos-{semente}")
    prazo = Prazo(minutos)
    pols = _ler(saida / "politicos.json") or []
    vots = _ler(saida / "votacoes.json") or []
    api = DespesasCamara(buscar)
    cs: list[Checagem] = []

    def rodar(nome: str, f: Callable):
        try:
            r = f()
            cs.extend(r if isinstance(r, tuple) else (r,))
        except Exception as e:  # noqa: BLE001 - uma checagem com defeito não derruba as outras
            log.exception("Verificação %s: erro", nome)
            c = Checagem(nome, SECAO_DE.get(nome, "cota"), nome, "", "")
            c.motivo = f"erro na verificação: {str(e)[:200]}"
            cs.append(c)

    rodar("cota_camara", lambda: cota_camara(saida, pols, random.Random(rng.random()), prazo, hoje, api))
    rodar("cota_camara_pagina", lambda: cota_camara_pagina(saida, pols, hoje))
    rodar("cota_senado_ano", lambda: cota_senado(pols, random.Random(rng.random()), prazo, hoje, buscar, saida))
    rodar("votos_camara", lambda: votos_camara(saida, vots, random.Random(rng.random()), prazo, buscar))
    rodar("votos_senado", lambda: votos_senado(saida, vots, random.Random(rng.random()), prazo, buscar))
    rodar("empresas_receita", lambda: empresas_receita(saida, random.Random(rng.random()), prazo, buscar))
    rodar("emendas_autor", lambda: emendas_autor(saida, random.Random(rng.random()), prazo,
                                                 chave_portal() if chave is None else chave, buscar))
    rodar("financas_juros", lambda: financas_juros(saida))

    hist = {sid: (s.get("historico") or []) for sid, s in ((anterior or {}).get("secoes") or {}).items()}
    out = {
        "gerado_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "data": hoje.isoformat(), "semente": semente, "confianca": CONFIANCA,
        "dias_mes_fechado": DIAS_MES_FECHADO, "dias_historico": DIAS_HISTORICO,
        "para_99_99": conferidos_para(0.9999),
        "secoes": resumo_secoes(cs, hist, hoje.isoformat()),
        "checagens": [c.json() for c in cs],
    }
    return out


SECAO_DE = {"cota_camara": "cota", "cota_camara_pagina": "cota", "cota_senado_ano": "cota", "votos_camara": "votacoes", "votos_senado": "votacoes",
            "empresas_receita": "empresas", "emendas_autor": "emendas", "financas_juros": "financas"}


def _baixar_anterior(url: str) -> dict | None:
    if not url:
        return None
    try:
        if re.match(r"^https?://", url):
            import requests
            r = requests.get(url, timeout=30)
            return r.json() if r.ok else None
        return json.loads(Path(url).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - sem o histórico, começa a contar de novo
        return None


def _fmt(x: Any) -> str:
    return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if isinstance(x, (int, float)) else str(x)


def relatorio(v: dict) -> str:
    rot = {"conferido": "conferido", "divergente": "DIVERGENTE", "parcial": "parcial", "nao_conferido": "não conferido",
           "sem_segunda_fonte": "sem segunda fonte"}
    linhas = ["## Verificação independente (segunda fonte oficial)\n",
              "| Seção | Situação | Conferidos hoje | Divergentes hoje | Acumulado | Pelo menos certos (95%) |",
              "| --- | --- | --- | --- | --- | --- |"]
    for s in v["secoes"].values():
        a = s["acumulado"]
        cm = f"{a['certos_min'] * 100:.2f}%" if a["certos_min"] is not None else "-"
        linhas.append(f"| {s['titulo']} | {rot[s['status']]} | {s['hoje']['conferidos']} | {s['hoje']['divergentes']} | "
                      f"{a['conferidos']} ({a['dias']} dias) | {cm} |")
    linhas.append("")
    for c in v["checagens"]:
        extra = f" ({c['nao_conferidos']} não conferidos)" if c["nao_conferidos"] else ""
        motivo = f" — {c['motivo']}" if c["status"] == "nao_conferido" and c["motivo"] else ""
        linhas.append(f"- **{c['titulo']}**: {rot[c['status']]}, {c['conferidos']} conferidos, {c['divergentes']} divergentes{extra}{motivo}")
        for d in c["divergencias"][:5]:
            linhas.append(f"  - {d['o_que']}: site {_fmt(d['site'])}, fonte {_fmt(d['oficial'])} ({d['fonte']})")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("saida", type=Path)
    ap.add_argument("--anterior", default="", help="verificacao.json publicado antes (URL ou arquivo), para somar o histórico")
    ap.add_argument("--minutos", type=float, default=20)
    ap.add_argument("--semente", default=None)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("sa_etl").setLevel(logging.ERROR)  # novas tentativas de download não poluem o resumo
    v = verificar(a.saida, _baixar_anterior(a.anterior), a.minutos, a.semente)
    write_json(a.saida / "verificacao.json", v)
    print(relatorio(v))
    # Não bloqueia a publicação: o site mostra a situação de cada seção, inclusive as divergências.
    return 0


if __name__ == "__main__":
    sys.exit(main())
