"""Aba "Brasil: arrecadação e gastos": quanto o governo federal arrecadou, de quem, e para onde foi o dinheiro.

Junta fontes oficiais (veja cada módulo para o motivo de usar API ou arquivo):
- fin_tesouro: API do Tesouro (SICONFI) — receitas por origem, despesas por grupo e por função, pessoal por Poder (LRF).
- fin_receita: arquivos da Receita Federal — arrecadação por imposto, por estado e por setor.
- fin_orcamento: arquivo do Portal da Transparência — gasto do Executivo por órgão, programa, ação e tipo de despesa.
- fin_pessoal: servidores do Executivo (Portal), da Câmara (dados abertos) e do Senado (API): concursados,
  cargos de confiança e comissionados sem concurso.
- IPCA do IBGE (API SIDRA), para comparar anos descontando a inflação.

Grava data/financas/indice.json (anos, série por ano, fontes) e data/financas/{ano}.json (o detalhe de um ano).
Cada ano fica separado; a soma de vários anos só aparece como informação secundária no site.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import time
from pathlib import Path

from . import fin_orcamento, fin_pessoal, fin_receita, fin_tesouro
from .util import get_json, write_json

log = logging.getLogger("sa_etl.financas")
AVISOS: list[str] = []  # problemas desta coleta, mostrados na própria aba (não no aviso geral do site)


def avisar(msg: str) -> None:
    log.warning(msg)
    if msg not in AVISOS:
        AVISOS.append(msg)

ANO_INICIAL = 2019
URL_IPCA = "https://apisidra.ibge.gov.br/values/t/1737/n1/all/v/2266/p/{de}-{ate}"
PAGINA_IPCA = "https://sidra.ibge.gov.br/tabela/1737"
FONTES = {
    "siconfi": "https://apidatalake.tesouro.gov.br/docs/siconfi/",
    "rreo": "https://www.tesourotransparente.gov.br/temas/contabilidade-e-custos/relatorio-resumido-da-execucao-orcamentaria-rreo-uniao",
    "rgf": "https://www.tesourotransparente.gov.br/temas/contabilidade-e-custos/relatorio-de-gestao-fiscal-rgf-uniao",
    "receita": fin_receita.PAGINA, "receita_uf": fin_receita.URL_UF, "receita_cnae": fin_receita.URL_CNAE,
    "orcamento": fin_orcamento.FONTE, "siape": fin_pessoal.FONTE_SIAPE, "camara": fin_pessoal.URL_CAMARA,
    "senado": fin_pessoal.URL_SENADO, "ipca": PAGINA_IPCA,
}

# ---------------------------------------------------------------- inflação

def ipca(ano_atual: int) -> dict[str, float]:
    """Número-índice do IPCA por mês ('AAAAMM' -> índice)."""
    try:
        dados = get_json(URL_IPCA.format(de=f"{ANO_INICIAL - 1}12", ate=f"{ano_atual}12"), timeout=120)
    except Exception as e:  # noqa: BLE001
        log.warning("IPCA: API do IBGE indisponível (%s)", e)
        return {}
    out = {}
    for d in dados[1:] if isinstance(dados, list) else []:
        try:
            out[str(d["D3C"])] = float(d["V"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


def real(valor_antigo: float, ano_antigo: int, ano_novo: int, mes: int, idx: dict[str, float]) -> float | None:
    """Valor do ano antigo corrigido pela inflação até o mesmo mês do ano novo."""
    a, b = idx.get(f"{ano_antigo}{mes:02d}"), idx.get(f"{ano_novo}{mes:02d}")
    if not a or not b:
        return None
    return valor_antigo * b / a


# ---------------------------------------------------------------- KPIs

def _nivel(v: float | None, amarelo: float, vermelho: float, maior_pior: bool = True) -> str:
    if v is None:
        return "sem_dados"
    if maior_pior:
        return "vermelho" if v >= vermelho else "amarelo" if v >= amarelo else "verde"
    return "vermelho" if v <= vermelho else "amarelo" if v <= amarelo else "verde"


def _kpi(id_: str, titulo: str, valor: float | None, formato: str, nivel: str, regra: str, explica: str,
         fonte: str, link: str = "", detalhe: list | None = None, grupo: str = "") -> dict:
    return {"id": id_, "titulo": titulo, "valor": None if valor is None else round(valor, 4), "formato": formato,
            "nivel": nivel, "regra": regra, "explica": explica, "fonte": fonte, "link": link, "detalhe": detalhe or [], "grupo": grupo}


def kpis(d: dict, ant: dict | None, idx: dict[str, float], emendas_total: float | None) -> list[dict]:
    """Sinais verde, amarelo e vermelho. Quando a regra é da lei (limites da LRF), dizemos; as outras são critérios
    do Segredos Abertos, explicados em cada sinal."""
    out: list[dict] = []
    ano = d["ano"]
    r1, r2 = d.get("rreo") or {}, d.get("funcoes") or {}
    per = d.get("periodo") or {}
    # 1. Pessoal por Poder x limites da LRF
    for p in d.get("pessoal_poderes") or []:
        lim = sum(o["limite_max"] for o in p["orgaos"])
        dtp = sum(o["dtp"] for o in p["orgaos"])
        v = dtp / lim if lim else None
        acima = [[o["nome"], round(o["dtp"] / o["limite_max"], 4)] for o in p["orgaos"] if o["limite_max"] and o["dtp"] / o["limite_max"] >= 0.9]
        do = "da" if p["poder"] == "D" else "do"
        out.append(_kpi(f"lrf_{p['poder']}", f"Gasto com pessoal {do} {p['nome']} perto do limite da lei?", v, "pct_limite",
                        _nivel(v, 0.90, 0.95),
                        "Regra da Lei de Responsabilidade Fiscal: acima de 90% do limite é alerta (amarelo); acima de 95% é o limite prudencial (vermelho), que proíbe aumentos e novas contratações.",
                        f"Despesa com pessoal dos últimos 12 meses até {per.get('rgf_mes', '')} de {p.get('ano', ano)}, como parte do limite que a lei permite {'à' if p['poder'] == 'D' else 'ao'} {p['nome']}.",
                        p["url"], "", acima, "pessoal"))
    rec = {x["id"]: x["valor"] for x in r1.get("receitas", [])}
    desp = {x["id"]: x["liquidado"] for x in r1.get("despesas", [])}
    impostos = (rec.get("Impostos", 0) + rec.get("Taxas", 0) + rec.get("ContribuicoesSociais", 0)
                + rec.get("ContribuicaoDeIntervencaoNoDominioEconomico", 0))
    # 2. Juros x impostos
    v = desp.get("JurosEEncargosDaDivida", 0) / impostos if impostos and desp else None
    out.append(_kpi("juros", "Quanto dos impostos vai para juros da dívida", v, "pct", _nivel(v, 0.15, 0.30),
                    "Critério do Segredos Abertos: até 15% verde, de 15% a 30% amarelo, acima de 30% vermelho.",
                    f"Juros pagos de janeiro a {per.get('mes_nome', '')} como parte do que entrou em impostos, taxas e contribuições.",
                    d["fontes_ano"]["rreo1"], "", grupo="divida"))
    # 3. Gasto pago com dívida nova
    gasto = sum(v for k, v in desp.items() if k != "AmortizacaoRefinanciamentoDaDivida")
    v = rec.get("ReceitasDeOperacoesDeCredito", 0) / gasto if gasto and rec else None
    out.append(_kpi("divida_nova", "Quanto do gasto foi pago com empréstimo", v, "pct", _nivel(v, 0.05, 0.20),
                    "Critério do Segredos Abertos: até 5% verde, de 5% a 20% amarelo, acima de 20% vermelho. Não conta a rolagem (dívida nova só para pagar dívida velha).",
                    "Dívida nova (venda de títulos do Tesouro, sem a rolagem) como parte de tudo o que foi gasto no período.",
                    d["fontes_ano"]["rreo1"], "", grupo="divida"))
    # 4 e 5. Crescimento real (mesmo período do ano anterior)
    mes = per.get("mes", 0)
    if ant and ant.get("rreo_mesmo_periodo") and mes:
        a1 = {x["id"]: x["liquidado"] for x in ant["rreo_mesmo_periodo"].get("despesas", [])}
        sem_div = lambda dd: sum(v for k, v in dd.items() if k not in ("JurosEEncargosDaDivida", "AmortizacaoDaDivida", "AmortizacaoRefinanciamentoDaDivida", "InversoesFinanceiras"))  # noqa: E731
        base = real(sem_div(a1), ano - 1, ano, mes, idx)
        v = sem_div(desp) / base - 1 if base else None
        out.append(_kpi("cresc_gasto", "O gasto (sem a dívida) cresceu acima da inflação?", v, "pct_var", _nivel(v, 0.0, 0.025),
                        "Critério do Segredos Abertos: queda real é verde; alta até 2,5% acima da inflação é amarelo; acima de 2,5% é vermelho (2,5% é o teto de crescimento real do arcabouço fiscal, Lei Complementar 200/2023, que vale para um conjunto parecido de despesas).",
                        f"Despesa de janeiro a {per.get('mes_nome', '')} de {ano}, sem juros, dívida e empréstimos concedidos (como o Fies, que voltam ao caixa), comparada com o mesmo período de {ano - 1} corrigido pelo IPCA.",
                        d["fontes_ano"]["rreo1"], "", grupo="gasto"))
        adm_a = ant.get("adm_geral_mesmo_periodo")
        base = real(adm_a, ano - 1, ano, mes, idx) if adm_a else None
        adm = fin_tesouro.adm_geral(r2) if r2 else None
        v = adm / base - 1 if base and adm is not None else None
        out.append(_kpi("cresc_maquina", "O custo de manter a máquina cresceu acima da inflação?", v, "pct_var", _nivel(v, 0.0, 0.05),
                        "Critério do Segredos Abertos: queda real é verde; alta até 5% acima da inflação é amarelo; acima de 5% é vermelho.",
                        f"Subfunção 'Administração geral' de todos os órgãos (aluguéis, limpeza, segurança, pessoal administrativo), de janeiro a {per.get('mes_nome', '')}, comparada com {ano - 1} corrigido pelo IPCA.",
                        d["fontes_ano"]["rreo2"], "", grupo="gasto"))
    # 6. Cobertura do INSS
    arr = d.get("arrecadacao") or {}
    contrib = next((g["valor"] for g in arr.get("grupos", []) if g["id"] == "folha"), None)
    prev = next((s[1] for f in (r2.get("funcoes") or []) if f["nome"] == "Previdência Social" for s in f["sub"] if s[0] == "Previdência Básica"), None)
    if contrib and prev and arr.get("ate_mes") and mes:
        v = (contrib / arr["ate_mes"]) / (prev / mes)
        out.append(_kpi("inss", "As contribuições ao INSS cobrem as aposentadorias do INSS?", v, "pct", _nivel(v, 0.9, 0.7, maior_pior=False),
                        "Critério do Segredos Abertos: a partir de 90% verde, de 70% a 90% amarelo, abaixo de 70% vermelho.",
                        "Média mensal arrecadada com a contribuição ao INSS (Receita Federal) dividida pela média mensal gasta com aposentadorias e pensões do INSS (Tesouro). O que falta sai dos outros impostos.",
                        FONTES["receita"], "", grupo="previdencia"))
    # 7 e 8. Cargos de confiança no Executivo
    ex = d.get("pessoal_executivo")
    if ex:
        g = {x["id"]: x for x in ex["grupos"]}
        total = sum(x["pessoas"] for k, x in g.items() if k != "sigiloso")
        if total:
            v = g["comissionado"]["pessoas"] / total
            out.append(_kpi("comissionados_exec", "Comissionados sem concurso no Executivo", v, "pct", _nivel(v, 0.02, 0.05),
                            "Critério do Segredos Abertos: até 2% verde, de 2% a 5% amarelo, acima de 5% vermelho.",
                            f"Pessoas nomeadas sem concurso como parte de todos os servidores civis do Executivo federal em {ex['mes']:02d}/{ex['ano']}.",
                            ex["url"], "", grupo="cargos"))
            v = (g["comissionado"]["pessoas"] + g["confianca"]["pessoas"]) / total
            out.append(_kpi("confianca_exec", "Cargos e funções de confiança no Executivo", v, "pct", _nivel(v, 0.10, 0.20),
                            "Critério do Segredos Abertos: até 10% verde, de 10% a 20% amarelo, acima de 20% vermelho.",
                            "Comissionados sem concurso mais concursados com cargo ou função de confiança (CCE, FCE, FG, CD e outras), que podem mudar a cada governo.",
                            ex["url"], "", grupo="cargos"))
    # 9 e 10. Comissionados na Câmara e no Senado
    for casa, nome, chaves, link in (("camara", "Câmara", ("secretario", "cne"), "/politicos"), ("senado", "Senado", ("comissionado",), "/politicos")):
        c = d.get(f"pessoal_{casa}")
        if not c:
            continue
        g = {x["id"]: x["pessoas"] for x in c["grupos"]}
        equipe = sum(v for k, v in g.items() if k != "parlamentar")
        if equipe:
            v = sum(g.get(k, 0) for k in chaves) / equipe
            out.append(_kpi(f"comissionados_{casa}", f"Comissionados sem concurso no {nome}" if casa == "senado" else "Comissionados sem concurso na Câmara",
                            v, "pct", _nivel(v, 0.25, 0.50),
                            "Critério do Segredos Abertos: até 25% verde, de 25% a 50% amarelo, acima de 50% vermelho.",
                            "Pessoas sem concurso (gabinetes, lideranças, Mesa) como parte de toda a equipe, sem contar os parlamentares. Situação de hoje.",
                            c["url"], link, grupo="cargos"))
    # 11. Emendas x investimentos
    inv = next((x["empenhado"] for x in r1.get("despesas", []) if x["id"] == "Investimentos"), None)
    if emendas_total and inv:
        v = emendas_total / inv
        out.append(_kpi("emendas", "Emendas parlamentares comparadas ao que o governo investe", v, "pct", _nivel(v, 0.20, 0.40),
                        "Critério do Segredos Abertos: até 20% verde, de 20% a 40% amarelo, acima de 40% vermelho.",
                        f"Valor empenhado em emendas de deputados e senadores em {ano} dividido pelo valor empenhado em investimentos (obras e equipamentos) pelo governo federal. As emendas também pagam custeio, como saúde.",
                        d["fontes_ano"]["rreo1"], "/emendas", grupo="emendas"))
    # 12. Aposentados no gasto com pessoal
    pp = d.get("pessoal_poderes") or []
    bruta = sum(o["bruta"] for p in pp for o in p["orgaos"])
    inat = sum(o["inativos"] for p in pp for o in p["orgaos"])
    if bruta:
        v = inat / bruta
        out.append(_kpi("inativos", "Quanto do gasto com pessoal vai para aposentados e pensionistas", v, "pct", _nivel(v, 0.35, 0.50),
                        "Critério do Segredos Abertos: até 35% verde, de 35% a 50% amarelo, acima de 50% vermelho.",
                        "Aposentadorias e pensões de servidores como parte de todo o gasto com pessoal dos Poderes (últimos 12 meses).",
                        pp[0]["url"] if pp else "", "",
                        [[p["nome"], round(sum(o["inativos"] for o in p["orgaos"]) / max(1, sum(o["bruta"] for o in p["orgaos"])), 4)] for p in pp],
                        grupo="pessoal"))
    return out


# ---------------------------------------------------------------- montar

def _mes_nome(m: int) -> str:
    return ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"][m]


def montar_ano(ano: int, ano_atual: int, cache: Path, arr_uf: dict, arr_cnae: dict) -> dict | None:
    """Tudo de um ano. None se o Tesouro ainda não publicou nada do ano."""
    a1 = fin_tesouro.rreo(ano, "RREO-Anexo 01", cache, ano_atual)
    if not a1:
        return None
    bim, itens1 = a1
    rreo = fin_tesouro.ler_rreo1(itens1)
    for e in fin_tesouro.conferir_rreo1(rreo):
        log.warning("RREO %d: %s", ano, e)
    a2 = fin_tesouro.rreo(ano, "RREO-Anexo 02", cache, ano_atual)
    funcoes = fin_tesouro.ler_rreo2(a2[1]) if a2 and a2[0] == bim else None
    params = lambda anexo: dict(an_exercicio=ano, nr_periodo=bim, co_tipo_demonstrativo="RREO", no_anexo=anexo, co_esfera="U", id_ente=1)  # noqa: E731
    d: dict = {
        "ano": ano,
        "parcial": bim < 6,
        "periodo": {"bimestre": bim, "mes": bim * 2, "mes_nome": fin_tesouro.MESES_BIMESTRE[bim]},
        "rreo": rreo,
        "funcoes": funcoes,
        "fontes_ano": {"rreo1": fin_tesouro.url_api("rreo", **params("RREO-Anexo 01")),
                       "rreo2": fin_tesouro.url_api("rreo", **params("RREO-Anexo 02"))},
    }
    # pessoal por Poder (RGF)
    poderes = []
    for cod, nome in fin_tesouro.PODERES.items():
        g = fin_tesouro.rgf(ano, cod, cache, ano_atual)
        if not g:
            continue
        q, itens = g
        orgs = fin_tesouro.ler_rgf(cod, itens)
        if orgs:
            poderes.append({"poder": cod, "nome": nome, "ano": ano, "quadrimestre": q, "orgaos": orgs,
                            "url": fin_tesouro.url_api("rgf", an_exercicio=ano, in_periodicidade="Q", nr_periodo=q, co_tipo_demonstrativo="RGF",
                                                       no_anexo="RGF-Anexo 01", co_esfera="U", co_poder=cod, id_ente=1)})
            d["periodo"]["rgf_mes"] = fin_tesouro.MESES_QUADRI[q]
    d["pessoal_poderes"] = poderes
    d["arrecadacao"] = arr_uf.get(ano)
    d["setores"] = arr_cnae.get(ano)
    d["executivo"] = fin_orcamento.coletar(ano, cache, ano_atual)
    return d


def mesmo_periodo(ano: int, bim: int, cache: Path, ano_atual: int) -> tuple[dict | None, float | None]:
    """RREO do ano anterior no mesmo bimestre, para comparar períodos iguais."""
    out = []
    for anexo in ("RREO-Anexo 01", "RREO-Anexo 02"):
        params = dict(an_exercicio=ano, nr_periodo=bim, co_tipo_demonstrativo="RREO", no_anexo=anexo, co_esfera="U", id_ente=1)
        try:
            out.append(fin_tesouro.consultar("rreo", cache, completo=ano < ano_atual, **params))
        except Exception as e:  # noqa: BLE001
            log.warning("RREO %d bimestre %d: %s", ano, bim, e)
            out.append([])
    r1 = fin_tesouro.ler_rreo1(out[0]) if out[0] else None
    r2 = fin_tesouro.ler_rreo2(out[1]) if out[1] else None
    return r1, (fin_tesouro.adm_geral(r2) if r2 else None)


def _resumo_serie(d: dict) -> dict:
    """Uma linha da comparação entre anos (cada ano separado)."""
    rec = {x["id"]: x["valor"] for x in d["rreo"]["receitas"]}
    desp = {x["id"]: x["liquidado"] for x in d["rreo"]["despesas"]}
    arr = d.get("arrecadacao") or {}
    ex = d.get("executivo") or {}
    cat = {c["id"]: c["realizado"] for c in ex.get("categorias", [])}
    return {
        "ano": d["ano"], "parcial": d["parcial"], "ate": d["periodo"]["mes_nome"],
        "impostos": round(sum(v for k, v in rec.items() if k in ("Impostos", "Taxas", "ContribuicoesSociais", "ContribuicaoDeIntervencaoNoDominioEconomico")), 2),
        "receita_propria": round(sum(x["valor"] for x in d["rreo"]["receitas"] if x["tipo"] == "propria"), 2),
        "divida_nova": round(rec.get("ReceitasDeOperacoesDeCredito", 0), 2),
        "rolagem": round(rec.get("OperacoesDeCreditoRefinanciamento", 0), 2),
        "despesa": round(sum(v for k, v in desp.items() if k != "AmortizacaoRefinanciamentoDaDivida"), 2),
        "pessoal": desp.get("PessoalEEncargosSociais"), "juros": desp.get("JurosEEncargosDaDivida"),
        "inss": desp.get("BeneficiosPrevidenciarios"), "investimentos": desp.get("Investimentos"),
        "adm_geral": round(fin_tesouro.adm_geral(d["funcoes"]), 2) if d.get("funcoes") else None,
        "maquina_exec": cat.get("maquina"),
        "arrecadacao_rfb": arr.get("total"), "arrecadacao_ate_mes": arr.get("ate_mes"),
    }


def _emendas_totais(saida: Path) -> dict[str, float]:
    try:
        j = json.loads((saida / "emendas" / "anos.json").read_text(encoding="utf-8"))
        return {k: (v or {}).get("empenhado") or 0.0 for k, v in (j.get("totais") or {}).items()}
    except Exception:  # noqa: BLE001
        return {}


def _verba_gabinete(saida: Path, ano: int) -> float | None:
    """Quanto os deputados usaram da verba de gabinete (que paga os secretários parlamentares), dos dados da Câmara
    já coletados para as páginas dos políticos."""
    try:
        pols = json.loads((saida / "politicos.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    vs = [((p.get("por_ano") or {}).get(str(ano)) or {}).get("verba_gabinete") for p in pols if p.get("casa") == "camara"]
    vs = [v for v in vs if v]
    return round(sum(vs), 2) if vs else None


def coletar(saida: Path, cache: Path, ano_atual: int | None = None, minutos: float = 25) -> dict | None:
    ano_atual = ano_atual or dt.date.today().year
    cache = cache / "financas"
    AVISOS.clear()
    inicio = time.time()
    ufp, cnaep = fin_receita.baixar(cache)
    arr_uf = fin_receita.por_uf(ufp) if ufp else {}
    arr_cnae = fin_receita.por_setor(cnaep) if cnaep else {}
    if not arr_uf:
        avisar("Arrecadação e gastos: a Receita Federal não respondeu; a arrecadação por imposto ficou de fora")
    idx = ipca(ano_atual)
    emendas = _emendas_totais(saida)
    anos: dict[int, dict] = {}
    for ano in range(ano_atual, ANO_INICIAL - 1, -1):  # 2026 primeiro, depois os anteriores
        if time.time() - inicio > minutos * 60:
            log.warning("Arrecadação e gastos: tempo esgotado; os anos antes de %d ficam para a próxima coleta", ano + 1)
            break
        try:
            d = montar_ano(ano, ano_atual, cache, arr_uf, arr_cnae)
        except Exception:  # noqa: BLE001
            log.exception("Arrecadação e gastos %d: erro", ano)
            d = None
        if d:
            anos[ano] = d
    if not anos:
        avisar("Arrecadação e gastos: o Tesouro Nacional não respondeu; a aba não foi atualizada")
        return None
    # pessoal: Executivo no mesmo mês de cada ano; Câmara e Senado só a situação de hoje
    ultimo = max(anos)
    mes_hoje = dt.date.today().month if ultimo == dt.date.today().year else 12
    ex_atual = fin_pessoal.coletar_siape(ultimo, mes_hoje, cache)
    mes_ref = ex_atual["mes"] if ex_atual else mes_hoje
    for z in (cache / "siape").glob("*_Servidores_SIAPE.zip"):  # só fica o arquivo do mês mais recente
        if ex_atual and not z.name.startswith(f"{ultimo}{mes_ref:02d}"):
            z.unlink(missing_ok=True)
    for ano, d in anos.items():
        if time.time() - inicio > (minutos + 15) * 60:
            break
        d["pessoal_executivo"] = ex_atual if ano == ultimo else _siape_cacheado(ano, mes_ref, cache)
    anos[ultimo]["pessoal_camara"] = fin_pessoal.coletar_camara()
    if anos[ultimo]["pessoal_camara"]:
        anos[ultimo]["pessoal_camara"]["verba_gabinete"] = _verba_gabinete(saida, ultimo)
    anos[ultimo]["pessoal_senado"] = fin_pessoal.coletar_senado(ultimo, mes_hoje)
    # comparações e sinais
    for ano, d in anos.items():
        bim = d["periodo"]["bimestre"]
        ant = None
        if ano - 1 >= ANO_INICIAL:
            r1, adm = mesmo_periodo(ano - 1, bim, cache, ano_atual)
            ant = {"rreo_mesmo_periodo": r1, "adm_geral_mesmo_periodo": adm}
        d["emendas_empenhado"] = emendas.get(str(ano))
        d["kpis"] = kpis(d, ant, idx, emendas.get(str(ano)))
        if ant and ant["rreo_mesmo_periodo"]:
            d["anterior_mesmo_periodo"] = {"despesas": {x["id"]: x["liquidado"] for x in ant["rreo_mesmo_periodo"]["despesas"]},
                                           "receitas": {x["id"]: x["valor"] for x in ant["rreo_mesmo_periodo"]["receitas"]},
                                           "adm_geral": adm if ant else None,
                                           "ipca_fator": (idx.get(f"{ano}{d['periodo']['mes']:02d}", 0) / idx.get(f"{ano - 1}{d['periodo']['mes']:02d}", 1)) if idx else None}
    gravar(saida, anos)
    log.info("Arrecadação e gastos: anos %s em %.0f s", sorted(anos), time.time() - inicio)
    return {"anos": sorted(anos)}


def _siape_cacheado(ano: int, mes: int, cache: Path) -> dict | None:
    """Resumo do SIAPE de um ano anterior. Guardamos só o resumo (o arquivo do mês tem 80 MB)."""
    arq = cache / "siape" / f"resumo-{ano}{mes:02d}.json"
    if arq.exists():
        return json.loads(arq.read_text(encoding="utf-8"))
    r = fin_pessoal.coletar_siape(ano, mes, cache)
    if r and r["mes"] == mes:
        arq.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        (cache / "siape" / f"{ano}{mes:02d}_Servidores_SIAPE.zip").unlink(missing_ok=True)
    return r


def gravar(saida: Path, anos: dict[int, dict]) -> None:
    pasta = saida / "financas"
    serie = []
    for ano in sorted(anos):
        d = anos[ano]
        write_json(pasta / f"{ano}.json", d)
        serie.append(_resumo_serie(d))
    write_json(pasta / "indice.json", {
        "anos": sorted(anos), "atualizado": dt.date.today().isoformat(),
        "serie": serie, "fontes": FONTES, "avisos": list(AVISOS),
    })
