"""Gasto do Poder Executivo federal por órgão, programa, ação e tipo de despesa (Portal da Transparência).

Fonte: "Orçamento da despesa pública" do Portal da Transparência (CGU), um arquivo por ano:
    https://portaldatransparencia.gov.br/download-de-dados/orcamento-despesa
Cada linha: órgão × função × subfunção × programa × ação × grupo × elemento de despesa, com orçamento inicial,
atualizado, empenhado e realizado. "Realizado" é a despesa liquidada: em 2025 o total dos juros (R$ 363,47 bilhões)
e da dívida bate centavo por centavo com o RREO do Tesouro.

Por que arquivo e não API: a API de dados do Portal tem consultas por órgão (despesas/por-orgao) e por programa e
ação (despesas/por-funcional-programatica), mas nenhuma cruza órgão com o tipo de despesa (pessoal, diárias,
terceirizados, material...), que é o que separa o custo de funcionar a máquina do resto. O arquivo traz esse
cruzamento inteiro num download pequeno (menos de 1 MB por ano).

O arquivo só tem o Poder Executivo (ministérios, autarquias e encargos da União). Legislativo, Judiciário,
Ministério Público e Defensoria vêm do Tesouro (RGF e RREO, ver fin_tesouro.py).
"""
from __future__ import annotations

import csv
import io
import logging
import zipfile
from collections import defaultdict
from pathlib import Path

from .fin_receita import numero
from .util import download, eh_zip

log = logging.getLogger("sa_etl.financas")

URL = "https://portaldatransparencia.gov.br/download-de-dados/orcamento-despesa/{ano}"
FONTE = "https://portaldatransparencia.gov.br/download-de-dados/orcamento-despesa"
LINK_ORGAO = "https://portaldatransparencia.gov.br/orgaos-superiores/{cod}?ano={ano}"
LINK_ACAO = "https://portaldatransparencia.gov.br/programas-e-acoes/acao/{cod}?ano={ano}"
LINK_PROGRAMA = "https://portaldatransparencia.gov.br/programas-e-acoes/programa-orcamentario/{cod}?ano={ano}"

# Subfunções de gestão do próprio governo (administração geral, TI, comunicação, controle...): o custeio nelas é o
# custo de manter a máquina funcionando, em qualquer ministério.
SUBFUNCOES_MAQUINA = {"121", "122", "123", "124", "125", "126", "128", "129", "130", "131"}
# Elementos de despesa de custeio administrativo e de apoio ao servidor
ELEMENTOS_CUSTEIO = {"14", "15", "30", "33", "35", "36", "37", "39", "40", "46", "47", "49", "08", "92", "93"}
# Benefícios em dinheiro a pessoas (BPC, seguro-desemprego, abono, Bolsa Família, bolsas de estudo e pesquisa)
ELEMENTOS_BENEFICIO = {"05", "06", "10", "18", "20", "48", "59"}
ELEMENTOS_APOSENTADORIA = {"01", "03"}  # aposentadorias e pensões (no grupo pessoal: de servidores)

CATEGORIAS = [
    ("pessoal_ativo", "Salários de servidores e militares da ativa", "Salários, gratificações, encargos e contratações temporárias."),
    ("aposentados", "Aposentadorias e pensões de servidores e militares", "Pagas pelo governo como patrão aos seus ex-servidores e dependentes."),
    ("inss", "Aposentadorias e pensões do INSS", "Benefícios do regime geral, pagos a quem trabalhou no setor privado."),
    ("beneficios", "Benefícios e programas sociais em dinheiro", "BPC, Bolsa Família, seguro-desemprego, abono salarial, bolsas de estudo e pesquisa."),
    ("transferencias", "Repasses a estados, municípios e entidades", "Fundos de participação, SUS, Fundeb, convênios, auxílios e subvenções."),
    ("maquina", "Funcionamento da máquina", "Custeio das áreas de gestão dos órgãos: aluguéis, terceirizados, diárias, passagens, TI, consultorias, material."),
    ("servicos", "Custeio dos serviços públicos", "Custeio de hospitais, universidades, fiscalização, Forças Armadas e outros serviços que chegam à população."),
    ("investimentos", "Investimentos (obras e equipamentos)", "Obras, equipamentos e outros bens que ficam para o país."),
    ("inversoes", "Empréstimos e participações", "Dinheiro que o governo empresta (como o Fies) ou põe em empresas e fundos."),
    ("juros", "Juros da dívida", "Juros pagos a quem emprestou dinheiro ao governo."),
    ("amortizacao", "Pagamento e rolagem da dívida", "Principal da dívida que venceu, pago com dinheiro do orçamento ou com dívida nova (refinanciamento)."),
    ("reserva", "Reserva de contingência", "Dinheiro guardado no orçamento para imprevistos."),
]
NOMES_CAT = {c: n for c, n, _ in CATEGORIAS}


def categoria(r: dict) -> str:
    gnd, el, sub = r["gnd"], r["elemento"], r["subfuncao"]
    if gnd == "1":
        return "aposentados" if el in ELEMENTOS_APOSENTADORIA else "pessoal_ativo"
    if gnd == "2":
        return "juros"
    if gnd == "4":
        return "investimentos"
    if gnd == "5":
        return "inversoes"
    if gnd == "6":
        return "amortizacao"
    if gnd == "9":
        return "reserva"
    # outras despesas correntes
    if "REGIME GERAL DE PREVID" in r["orgao_sub"].upper() or (sub == "271" and el in ("01", "03", "05", "09")):
        return "inss"
    if el in ELEMENTOS_BENEFICIO:
        return "beneficios"
    if el in ("41", "42", "43", "45", "81", "70", "71", "72", "73", "74", "75", "76", "80", "87"):
        return "transferencias"
    if sub in SUBFUNCOES_MAQUINA and el in ELEMENTOS_CUSTEIO:
        return "maquina"
    return "servicos"


COLS = {
    "orgao_cod": "CÓDIGO ÓRGÃO SUPERIOR", "orgao": "NOME ÓRGÃO SUPERIOR", "orgao_sub": "NOME ÓRGÃO SUBORDINADO",
    "funcao_cod": "CÓDIGO FUNÇÃO", "funcao": "NOME FUNÇÃO", "subfuncao": "CÓDIGO SUBFUNÇÃO",
    "programa_cod": "CÓDIGO PROGRAMA ORÇAMENTÁRIO", "programa": "NOME PROGRAMA ORÇAMENTÁRIO",
    "acao_cod": "CÓDIGO AÇÃO", "acao": "NOME AÇÃO", "gnd": "CÓDIGO GRUPO DE DESPESA", "elemento": "CÓDIGO ELEMENTO DE DESPESA",
    "elemento_nome": "NOME ELEMENTO DE DESPESA",
    "inicial": "ORÇAMENTO INICIAL (R$)", "atualizado": "ORÇAMENTO ATUALIZADO (R$)", "empenhado": "ORÇAMENTO EMPENHADO (R$)",
    "realizado": "ORÇAMENTO REALIZADO (R$)",
}


def baixar(ano: int, cache: Path, ano_atual: int) -> Path | None:
    dest = cache / "orcamento" / f"{ano}_OrcamentoDespesa.zip"
    try:
        # ano corrente: o Portal atualiza o arquivo todo mês; anos fechados: uma vez por mês basta
        return download(URL.format(ano=ano), dest, max_horas=20 if ano >= ano_atual else 24 * 30, validar=eh_zip)
    except Exception as e:  # noqa: BLE001
        log.warning("Orçamento %d: arquivo do Portal indisponível (%s)", ano, e)
        return None


def linhas(arq: Path):
    with zipfile.ZipFile(arq) as z:
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(nome) as f:
            for r in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";"):
                yield {k: (r.get(c) or "").strip() for k, c in COLS.items()}


def _cod(v: str, n: int) -> str:
    v = v.strip()
    return v.zfill(n) if v.isdigit() else v


def resumir(ano: int, itens) -> dict:
    """Totais por categoria, por órgão (com as categorias) e por programa e ação."""
    cat: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])  # [realizado, atualizado]
    orgaos: dict[str, dict] = {}
    programas: dict[str, dict] = {}
    elementos_maquina: dict[str, float] = defaultdict(float)
    for r in itens:
        r["gnd"] = r["gnd"].lstrip("0") or "0"
        r["elemento"] = _cod(r["elemento"], 2)
        r["subfuncao"] = _cod(r["subfuncao"], 3)
        real, atual = numero(r["realizado"]), numero(r["atualizado"])
        if not real and not atual:
            continue
        c = categoria(r)
        cat[c][0] += real
        cat[c][1] += atual
        if c == "maquina":
            elementos_maquina[r["elemento_nome"] or r["elemento"]] += real
        o = orgaos.setdefault(r["orgao_cod"], {"cod": r["orgao_cod"], "nome": r["orgao"], "realizado": 0.0, "atualizado": 0.0,
                                               "cat": defaultdict(float)})
        o["realizado"] += real
        o["atualizado"] += atual
        o["cat"][c] += real
        if c in ("juros", "amortizacao", "reserva"):
            continue  # dívida e reserva não são programas
        p = programas.setdefault(r["programa_cod"], {"cod": r["programa_cod"], "nome": r["programa"], "funcao": r["funcao"],
                                                     "realizado": 0.0, "atualizado": 0.0, "acoes": {}})
        p["realizado"] += real
        p["atualizado"] += atual
        a = p["acoes"].setdefault(r["acao_cod"], {"cod": r["acao_cod"], "nome": r["acao"], "orgao": r["orgao"], "realizado": 0.0,
                                                  "atualizado": 0.0, "cat": defaultdict(float)})
        a["realizado"] += real
        a["atualizado"] += atual
        a["cat"][c] += real
    r2 = lambda x: round(x, 2)  # noqa: E731
    lista_org = []
    for o in sorted(orgaos.values(), key=lambda o: -o["realizado"]):
        lista_org.append({"cod": o["cod"], "nome": o["nome"], "realizado": r2(o["realizado"]), "atualizado": r2(o["atualizado"]),
                          "cat": {k: r2(v) for k, v in sorted(o["cat"].items(), key=lambda kv: -kv[1]) if v},
                          "url": LINK_ORGAO.format(cod=o["cod"], ano=ano)})
    lista_prog = []
    for p in sorted(programas.values(), key=lambda p: -p["realizado"]):
        if not p["realizado"] and not p["atualizado"]:
            continue
        acoes = sorted(p["acoes"].values(), key=lambda a: -a["realizado"])
        lista_prog.append({
            "cod": p["cod"], "nome": p["nome"], "funcao": p["funcao"], "realizado": r2(p["realizado"]), "atualizado": r2(p["atualizado"]),
            "url": LINK_PROGRAMA.format(cod=p["cod"], ano=ano),
            "acoes": [{"cod": a["cod"], "nome": a["nome"], "orgao": a["orgao"], "realizado": r2(a["realizado"]), "atualizado": r2(a["atualizado"]),
                       "tipo": max(a["cat"], key=a["cat"].get) if a["cat"] else "", "url": LINK_ACAO.format(cod=a["cod"], ano=ano)}
                      for a in acoes if a["realizado"] or a["atualizado"]],
        })
    total = sum(v[0] for v in cat.values())
    log.info("Orçamento %d: R$ %.0f realizado no Executivo, %d órgãos, %d programas", ano, total, len(lista_org), len(lista_prog))
    return {
        "total": r2(total),
        "total_atualizado": r2(sum(v[1] for v in cat.values())),
        "categorias": [{"id": c, "nome": n, "explica": e, "realizado": r2(cat[c][0]), "atualizado": r2(cat[c][1])}
                       for c, n, e in CATEGORIAS if cat[c][0] or cat[c][1]],
        "orgaos": lista_org,
        "programas": lista_prog,
        "maquina_por_tipo": sorted(([k, r2(v)] for k, v in elementos_maquina.items() if v), key=lambda t: -t[1])[:15],
    }


def coletar(ano: int, cache: Path, ano_atual: int) -> dict | None:
    arq = baixar(ano, cache, ano_atual)
    if not arq:
        return None
    try:
        return resumir(ano, linhas(arq))
    except Exception:  # noqa: BLE001
        log.exception("Orçamento %d: erro ao ler o arquivo do Portal", ano)
        return None
