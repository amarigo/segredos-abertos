"""Comparação justa do gasto com a equipe do gabinete entre os estados.

Comparar só o valor gasto por cada deputado engana por três motivos:
1. Na Câmara, o teto da verba de gabinete é o mesmo para todo deputado, de qualquer estado. O que muda entre eles é
   quanto do teto cada um usa e quantos meses ficou no cargo. Por isso mostramos o percentual do teto usado.
2. O mesmo salário vale mais onde a vida é mais barata. O IBGE não publica um índice oficial de custo de vida por
   estado (o IPCA mede só a variação de preços, e só em 16 capitais e regiões). Usamos o rendimento médio do trabalho
   em cada estado (PNAD Contínua): a verba de um mês dividida por ele diz quantos "salários típicos do estado" ela paga.
3. Os estados têm de 8 a 70 deputados (Constituição, art. 45) e sempre 3 senadores. Por isso somamos a bancada
   inteira de cada estado e dividimos pela população: quanto custa a equipe por habitante e quantos habitantes cada
   assessor atende.

Fontes (API primeiro):
- População e rendimento: API SIDRA do IBGE (apisidra.ibge.gov.br).
- Verba de gabinete e o teto de cada deputado: página oficial do deputado (recursos.py; a API da Câmara não traz a
  verba de gabinete).
- Secretários parlamentares de cada deputado hoje: arquivo de funcionários dos dados abertos da Câmara (a API v2 não
  tem consulta de funcionários; o arquivo é a publicação oficial).
- Regras (teto mensal, faixa de salário, cota por estado): página "Gastos parlamentares" da Câmara. Não há API com
  esses valores; lemos o texto da página e, se ela mudar de formato, o site só deixa de mostrar o quadro das regras.
- Equipe dos senadores: API administrativa do Senado (recursos-utilizados, em recursos.py).

Grava data/gabinetes.json.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import logging
import re
from collections import Counter
from pathlib import Path

from . import fin_pessoal
from .util import avisar, com_copia, get, get_json, to_float, write_json

log = logging.getLogger("sa_etl.gabinetes")

# API SIDRA do IBGE (a mesma da inflação, em financas.py). A outra API do IBGE (servicodados) não aceita conexão a
# partir do GitHub Actions, onde a coleta roda.
SIDRA = "https://apisidra.ibge.gov.br/values"
# Estimativa de população residente, por estado (tabela 6579, variável 9324), último ano publicado
URL_POP = SIDRA + "/t/6579/n3/all/v/9324/p/last"
PAGINA_POP = "https://sidra.ibge.gov.br/tabela/6579"
# PNAD Contínua trimestral: rendimento médio mensal real das pessoas ocupadas, habitualmente recebido em todos os
# trabalhos (tabela 5436, variável 5932), por estado, último trimestre publicado
URL_REND = SIDRA + "/t/5436/n3/all/v/5932/p/last"
PAGINA_REND = "https://sidra.ibge.gov.br/tabela/5436"
# Código de cada estado no IBGE (padrão nacional, não muda): liga a resposta do SIDRA à sigla usada no site
COD_UF = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA", "22": "PI",
          "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
          "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}
URL_REGRAS = "https://www.camara.leg.br/transparencia/gastos-parlamentares"
URL_FUNC = fin_pessoal.URL_CAMARA
URL_SENADO = "https://www12.senado.leg.br/transparencia/sen/"
CONSTITUICAO = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm#art45"
NUM = r"([\d.]+,\d{2})"


# ---------------------------------------------------------------- leitura das fontes

def serie_sidra(d: list) -> tuple[str, dict[str, float], dict[str, str]]:
    """Resposta da API SIDRA (primeira linha = nomes das colunas) -> (período, {sigla: valor}, {nome do estado: sigla}).
    Valores com sinal no lugar do número ('-', '...', 'X') ficam de fora."""
    if not isinstance(d, list) or len(d) < 2:
        raise ValueError("SIDRA: resposta sem linhas")
    cab = d[0]
    col_uf = next(k for k, v in cab.items() if k.endswith("C") and str(v).startswith("Unidade da Federação"))
    col_per = next(k for k, v in cab.items() if k.endswith("C") and re.match(r"(Ano|Trimestre|Mês)", str(v)))
    out: dict[str, float] = {}
    nomes: dict[str, str] = {}
    periodo = ""
    for x in d[1:]:
        sigla = COD_UF.get(str(x.get(col_uf)))
        try:
            valor = float(x.get("V"))
        except (TypeError, ValueError):
            continue
        if sigla and valor > 0:
            out[sigla] = valor
            nomes[str(x.get(col_uf[:-1] + "N") or "")] = sigla
            periodo = max(periodo, str(x.get(col_per)))
    return periodo, out, nomes


def _texto(h: str) -> str:
    h = re.sub(r"(?s)<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def regras_camara(h: str, nomes_uf: dict[str, str]) -> dict | None:
    """Teto mensal da verba de gabinete, número máximo de secretários, faixa de salário e cota mensal de cada estado,
    como a Câmara escreve na página "Gastos parlamentares". nomes_uf: nome do estado -> sigla."""
    t = _texto(h)
    m = re.search(r"limite mensal de R\$ ?" + NUM + r" para pagar salários de até (\d+) secretários parlamentares", t)
    s = re.search(r"salários de R\$ ?" + NUM + r" a R\$ ?" + NUM, t)
    if not m:
        return None
    cota = {}
    # o mapa da página: <a ... title="Tocantins" ... data-content="51.525,80">
    for nome, valor in re.findall(r'title="([^"]+)"[^>]*?class="mapa-estado"[^>]*?data-content="([\d.,]+)"', h):
        sigla = nomes_uf.get(html.unescape(nome).strip())
        if sigla:
            cota[sigla] = round(to_float(valor), 2)
    return {"teto_mensal": round(to_float(m.group(1)), 2), "max_secretarios": int(m.group(2)),
            "salario_min": round(to_float(s.group(1)), 2) if s else None,
            "salario_max": round(to_float(s.group(2)), 2) if s else None,
            "cota_por_uf": dict(sorted(cota.items())), "fonte": URL_REGRAS}


def secretarios_por_deputado(dados: list) -> Counter:
    """Quantos secretários parlamentares cada deputado tem hoje (id do deputado na API da Câmara -> quantidade)."""
    c: Counter = Counter()
    for f in dados or []:
        if str(f.get("grupo") or "").strip() != "Secretário Parlamentar":
            continue
        m = re.search(r"/deputados/(\d+)$", str(f.get("uriLotacao") or ""))
        if m:
            c[m.group(1)] += 1
    return c


# ---------------------------------------------------------------- conta

def resumir(politicos: list[dict], anos: list[int], pop: dict[str, float], rend: dict[str, float],
            secretarios: Counter | None) -> dict:
    """Por ano e estado: cadeiras hoje, verba somada da bancada (inclui quem passou pela vaga no ano), teto somado,
    secretários hoje e equipe dos senadores. As divisões (por cadeira, por habitante...) ficam para o site."""
    hoje = [p for p in politicos if p.get("em_exercicio") is not False]
    cad = Counter(p["uf"] for p in hoje if p["casa"] == "camara")
    sen = Counter(p["uf"] for p in hoje if p["casa"] == "senado")
    secs: Counter = Counter()
    for p in hoje:
        if p["casa"] == "camara" and secretarios is not None:
            secs[p["uf"]] += secretarios.get(p["id"].split("-", 1)[1], 0)
    out = {}
    for ano in anos:
        a = str(ano)
        verba: Counter = Counter()
        teto: Counter = Counter()
        n_dep: Counter = Counter()
        equipe_sen: Counter = Counter()
        n_sen_equipe: Counter = Counter()
        meses = 0
        for p in politicos:
            x = (p.get("por_ano") or {}).get(a) or {}
            if p["casa"] == "camara" and x.get("verba_gabinete"):
                verba[p["uf"]] += x["verba_gabinete"]
                teto[p["uf"]] += x.get("verba_disponivel") or 0
                n_dep[p["uf"]] += 1
                meses = max(meses, x.get("verba_ate_mes") or 0)
            if p["casa"] == "senado" and p.get("em_exercicio") is not False and x.get("n_pessoal"):
                equipe_sen[p["uf"]] += x["n_pessoal"]
                n_sen_equipe[p["uf"]] += 1
        if not verba:
            continue
        ufs = []
        for uf in sorted(set(cad) | set(sen)):
            ufs.append({"uf": uf, "populacao": int(pop[uf]) if uf in pop else None, "rendimento": rend.get(uf),
                        "cadeiras": cad.get(uf, 0), "verba": round(verba.get(uf, 0), 2), "teto": round(teto.get(uf, 0), 2),
                        "deputados_no_ano": n_dep.get(uf, 0),
                        "secretarios_hoje": secs.get(uf, 0) if secretarios is not None else None,
                        "senadores": sen.get(uf, 0), "equipe_senado": equipe_sen.get(uf, 0) or None,
                        "senadores_com_equipe": n_sen_equipe.get(uf, 0)})
        out[a] = {"meses": meses or None, "ufs": ufs}
    return out


# ---------------------------------------------------------------- coleta

def coletar(saida: Path, cache: Path, anos: list[int]) -> dict | None:
    """Lê politicos.json (já gravado por montar()), busca IBGE e Câmara e grava gabinetes.json."""
    pasta = cache / "gabinetes"
    politicos = json.loads((saida / "politicos.json").read_text(encoding="utf-8"))
    try:
        ano_pop, pop, nomes = serie_sidra(com_copia(pasta / "populacao.json", lambda: get_json(URL_POP, timeout=120),
                                                    "População dos estados (IBGE)", max_horas=24 * 7))
    except Exception as e:  # noqa: BLE001
        log.warning("Gabinetes: IBGE fora do ar e sem cópia (%s)", e)
        avisar("Comparação dos gabinetes: o IBGE não respondeu; a página ficou de fora desta atualização")
        return None
    try:
        tri_rend, rend, _ = serie_sidra(com_copia(pasta / "rendimento.json", lambda: get_json(URL_REND, timeout=120),
                                                  "Rendimento médio por estado (IBGE)", max_horas=24 * 7))
    except Exception as e:  # noqa: BLE001
        log.warning("Gabinetes: rendimento do IBGE indisponível (%s)", e)
        tri_rend, rend = "", {}
    try:
        func = com_copia(pasta / "funcionarios.json",
                         lambda: {"dados": [{"grupo": f.get("grupo"), "uriLotacao": f.get("uriLotacao")}
                                            for f in get_json(URL_FUNC, timeout=300).get("dados") or []
                                            if f.get("grupo") == "Secretário Parlamentar"]},
                         "Secretários parlamentares (Câmara)", max_horas=20)
        secretarios = secretarios_por_deputado(func.get("dados"))
    except Exception as e:  # noqa: BLE001
        log.warning("Gabinetes: arquivo de funcionários da Câmara indisponível (%s)", e)
        secretarios = None
    try:
        regras = regras_camara(get(URL_REGRAS, timeout=60, headers={"Accept": "text/html"}).text, nomes)
    except Exception as e:  # noqa: BLE001
        log.warning("Gabinetes: página de gastos parlamentares da Câmara indisponível (%s)", e)
        regras = None
    if regras is None:
        log.warning("Gabinetes: não achamos o teto da verba na página da Câmara; o quadro das regras fica de fora")
    por_ano = resumir(politicos, anos, pop, rend, secretarios)
    if not por_ano:
        log.warning("Gabinetes: nenhum deputado com verba de gabinete; nada a gravar")
        return None
    d = {
        "atualizado": dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).isoformat(timespec="minutes"),
        "ano_populacao": ano_pop, "trimestre_rendimento": tri_rend, "regras": regras, "anos": por_ano,
        "fontes": {"populacao": PAGINA_POP, "rendimento": PAGINA_REND, "api_ibge": "https://apisidra.ibge.gov.br/",
                   "regras": URL_REGRAS, "secretarios": URL_FUNC, "constituicao": CONSTITUICAO, "senado": URL_SENADO},
    }
    write_json(saida / "gabinetes.json", d)
    log.info("Gabinetes: %d estados, anos %s", len(next(iter(por_ano.values()))["ufs"]), ", ".join(por_ano))
    return d
