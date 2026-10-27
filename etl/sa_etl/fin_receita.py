"""Arrecadação federal por imposto, por estado e por setor da economia (Receita Federal).

Fonte: dados abertos da Receita Federal ("Receita Data"),
    https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos/receitadata/arrecadacao
- arrecadacao-estado.csv: valor arrecadado por mês, estado (UF) e imposto, desde 2000;
- arrecadacao-cnae.csv: valor arrecadado por mês, setor da economia (seção da CNAE) e imposto, desde 2016.
  Traz também uma linha para pessoas físicas (PF).

Por que arquivo e não API: a Receita Federal não tem API para a arrecadação; os dados abertos oficiais são só esses
arquivos CSV (o API do Tesouro, o SICONFI, traz o total por natureza da receita, mas não por imposto, estado ou setor).

Os arquivos usam ; e vírgula decimal, com e sem ponto de milhar (depende do ano). Os valores estão em reais.
"""
from __future__ import annotations

import csv
import io
import logging
import re
from collections import defaultdict
from pathlib import Path

from .util import download, eh_csv

log = logging.getLogger("sa_etl.financas")

URL_UF = "https://www.gov.br/receitafederal/dados/arrecadacao-estado.csv"
URL_CNAE = "https://www.gov.br/receitafederal/dados/arrecadacao-cnae.csv"
PAGINA = "https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/dados-abertos/receitadata/arrecadacao"

MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}

# Sobre o que o imposto é cobrado. Quem paga de fato é discutido por economistas: o imposto sobre consumo é recolhido
# pela empresa, mas entra no preço que todo mundo paga. O site explica isso.
GRUPOS = [
    ("renda_pessoas", "Salários e renda das pessoas", "Imposto de Renda da pessoa física e o descontado dos salários (na fonte)."),
    ("lucro_empresas", "Lucro das empresas", "Imposto de Renda das empresas (IRPJ) e Contribuição Social sobre o Lucro (CSLL)."),
    ("consumo", "Consumo e produção", "Cofins, PIS, IPI e Cide. As empresas recolhem, mas o valor entra no preço do que todos compram."),
    ("folha", "Folha de salários (INSS)", "Contribuição ao INSS paga por trabalhadores e empresas sobre os salários."),
    ("servidores", "Previdência dos servidores", "Contribuição dos servidores públicos federais para a própria aposentadoria."),
    ("capital", "Aplicações financeiras e operações de crédito", "Imposto de Renda sobre juros e aplicações, remessas ao exterior e IOF."),
    ("comercio_exterior", "Importação e exportação", "Imposto de importação, IPI de produtos importados e imposto de exportação."),
    ("simples", "Simples Nacional (pequenas empresas)", "Guia única das micro e pequenas empresas (parte federal e as partes de estados e municípios juntas)."),
    ("outros", "Outros", "Imposto territorial rural, parcelamentos (Refis), receitas de outros órgãos e demais."),
]
# coluna do arquivo -> (grupo, família). Numa família, se as colunas detalhadas (FINANCEIRAS/DEMAIS) têm valor, a coluna
# geral não entra, para não contar duas vezes.
COLUNAS = {
    "IRPF": ("renda_pessoas", None), "IRRF - RENDIMENTOS DO TRABALHO": ("renda_pessoas", None),
    "IRPJ - ENTIDADES FINANCEIRAS": ("lucro_empresas", None), "IRPJ - DEMAIS EMPRESAS": ("lucro_empresas", None),
    "CSLL": ("lucro_empresas", "CSLL"), "CSLL - FINANCEIRAS": ("lucro_empresas", "CSLL*"), "CSLL - DEMAIS": ("lucro_empresas", "CSLL*"),
    "COFINS": ("consumo", "COFINS"), "COFINS - FINANCEIRAS": ("consumo", "COFINS*"), "COFINS - DEMAIS": ("consumo", "COFINS*"),
    "CONTRIBUIÇÃO PARA O PIS/PASEP": ("consumo", "PIS"), "CONTRIBUIÇÃO PARA O PIS/PASEP - FINANCEIRAS": ("consumo", "PIS*"),
    "CONTRIBUIÇÃO PARA O PIS/PASEP - DEMAIS": ("consumo", "PIS*"),
    "IPI - FUMO": ("consumo", None), "IPI - BEBIDAS": ("consumo", None), "IPI - AUTOMÓVEIS": ("consumo", None), "IPI - OUTROS": ("consumo", None),
    "CIDE-COMBUSTÍVEIS": ("consumo", "CIDE"), "CIDE-COMBUSTÍVEIS (parc. não dedutível)": ("consumo", "CIDE*"),
    "RECEITA PREVIDENCIÁRIA": ("folha", "PREV"), "RECEITA PREVIDENCIÁRIA - PRÓPRIA": ("folha", "PREV*"), "RECEITA PREVIDENCIÁRIA - DEMAIS": ("folha", "PREV*"),
    "CONTRIBUIÇÃO PLANO SEG. SOC. SERVIDORES": ("servidores", "PSS"), "CPSSS - Contrib. p/ o Plano de Segurid. Social Serv. Público": ("servidores", "PSS*"),
    "IRRF - RENDIMENTOS DO CAPITAL": ("capital", None), "IRRF - REMESSAS P/ EXTERIOR": ("capital", None), "IRRF - OUTROS RENDIMENTOS": ("capital", None),
    "IMPOSTO S/ OPERAÇÕES FINANCEIRAS": ("capital", None), "CPMF": ("capital", None), "IMPOSTO PROVIS.S/ MOVIMENT. FINANC. - IPMF": ("capital", None),
    "IMPOSTO SOBRE IMPORTAÇÃO": ("comercio_exterior", None), "IMPOSTO SOBRE EXPORTAÇÃO": ("comercio_exterior", None),
    "IPI - VINCULADO À IMPORTACAO": ("comercio_exterior", None),
    "PAGAMENTO UNIFICADO": ("simples", None),
}
NOME_TRIBUTO = {
    "IRPF": "IR pessoa física (declaração)", "IRRF - RENDIMENTOS DO TRABALHO": "IR descontado dos salários",
    "IRPJ - ENTIDADES FINANCEIRAS": "IR de bancos e financeiras", "IRPJ - DEMAIS EMPRESAS": "IR das demais empresas",
    "CSLL - FINANCEIRAS": "CSLL de bancos e financeiras", "CSLL - DEMAIS": "CSLL das demais empresas",
    "COFINS - FINANCEIRAS": "Cofins de bancos e financeiras", "COFINS - DEMAIS": "Cofins das demais empresas",
    "CONTRIBUIÇÃO PARA O PIS/PASEP - FINANCEIRAS": "PIS de bancos e financeiras", "CONTRIBUIÇÃO PARA O PIS/PASEP - DEMAIS": "PIS das demais empresas",
    "RECEITA PREVIDENCIÁRIA": "INSS (contribuição previdenciária)", "IMPOSTO S/ OPERAÇÕES FINANCEIRAS": "IOF",
    "IMPOSTO SOBRE IMPORTAÇÃO": "Imposto de importação", "IMPOSTO SOBRE EXPORTAÇÃO": "Imposto de exportação",
    "IPI - VINCULADO À IMPORTACAO": "IPI na importação", "PAGAMENTO UNIFICADO": "Simples Nacional",
    "IMPOSTO TERRITORIAL RURAL": "Imposto territorial rural (ITR)",
    "CPSSS - Contrib. p/ o Plano de Segurid. Social Serv. Público": "Previdência dos servidores (PSS)",
    "IRRF - RENDIMENTOS DO CAPITAL": "IR sobre aplicações e juros", "IRRF - REMESSAS P/ EXTERIOR": "IR sobre remessas ao exterior",
    "IRRF - OUTROS RENDIMENTOS": "IR sobre outros rendimentos", "ADMINISTRADAS POR OUTROS ÓRGÃOS": "Receitas de outros órgãos",
    "OUTRAS RECEITAS ADMINISTRADAS": "Outras receitas da Receita Federal",
}


def numero(v: str) -> float:
    """'1.234.567,89', '1234567,89', '1234567' e '-0,01' -> float."""
    s = (v or "").strip()
    if not s:
        return 0.0
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1 or re.fullmatch(r"-?\d{1,3}\.\d{3}", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _mes(v: str) -> int:
    t = (v or "").strip().lower()[:3]
    return MESES.get(t, 0)


def baixar(cache: Path) -> tuple[Path | None, Path | None]:
    pasta = cache / "receita"
    out = []
    for url in (URL_UF, URL_CNAE):
        try:
            out.append(download(url, pasta / url.rsplit("/", 1)[1], max_horas=20, validar=eh_csv))
        except Exception as e:  # noqa: BLE001
            log.warning("Arrecadação: %s indisponível (%s)", url, e)
            out.append(None)
    return out[0], out[1]


def _linhas(arq: Path) -> list[list[str]]:
    texto = arq.read_bytes().decode("latin-1")
    return [r for r in csv.reader(io.StringIO(texto), delimiter=";") if r]


def valores_linha(cab: list[str], linha: list[str], inicio: int) -> dict[str, float]:
    """{coluna: valor} sem contar duas vezes as famílias que têm coluna geral e colunas detalhadas."""
    v = {c: numero(x) for c, x in zip(cab[inicio:], linha[inicio:]) if x.strip()}
    familias_detalhadas = {COLUNAS[c][1][:-1] for c, x in v.items() if c in COLUNAS and (COLUNAS[c][1] or "").endswith("*") and x}
    return {c: x for c, x in v.items() if not (c in COLUNAS and COLUNAS[c][1] in familias_detalhadas)}


def por_uf(arq: Path) -> dict[int, dict]:
    """Por ano: total, por mês, por grupo (com os impostos), por UF."""
    linhas = _linhas(arq)
    cab = [c.strip() for c in linhas[0]]
    anos: dict[int, dict] = {}
    for r in linhas[1:]:
        try:
            ano = int(r[0])
        except ValueError:
            continue
        mes, uf = _mes(r[1]), r[2].strip().upper()
        if not mes:
            continue
        a = anos.setdefault(ano, {"meses": defaultdict(float), "grupos": defaultdict(float), "tributos": defaultdict(float),
                                  "uf": defaultdict(float), "uf_grupo": defaultdict(lambda: defaultdict(float))})
        for col, x in valores_linha(cab, r, 3).items():
            g = COLUNAS.get(col, ("outros", None))[0]
            a["meses"][mes] += x
            a["grupos"][g] += x
            a["tributos"][col] += x
            a["uf"][uf] += x
            a["uf_grupo"][uf][g] += x
    out = {}
    for ano, a in anos.items():
        total = sum(a["meses"].values())
        nomes_g = {g: (n, e) for g, n, e in GRUPOS}
        grupos = []
        for g, _, _ in GRUPOS:
            if not a["grupos"].get(g):
                continue
            trib = sorted(((NOME_TRIBUTO.get(c, c[:1] + c[1:].lower()), round(v, 2)) for c, v in a["tributos"].items()
                           if COLUNAS.get(c, ("outros", None))[0] == g and v), key=lambda t: -t[1])
            grupos.append({"id": g, "nome": nomes_g[g][0], "explica": nomes_g[g][1], "valor": round(a["grupos"][g], 2), "tributos": [list(t) for t in trib]})
        out[ano] = {
            "total": round(total, 2),
            "meses": [[m, round(a["meses"][m], 2)] for m in sorted(a["meses"])],
            "ate_mes": max(a["meses"]),
            "grupos": grupos,
            "por_uf": sorted(([uf, round(v, 2)] for uf, v in a["uf"].items()), key=lambda t: -t[1]),
        }
    return out


SECAO_NOME = {
    "A": "Agropecuária", "B": "Mineração e petróleo", "C": "Indústria", "D": "Eletricidade e gás", "E": "Água, esgoto e lixo",
    "F": "Construção", "G": "Comércio", "H": "Transporte e correio", "I": "Hotéis e restaurantes", "J": "Informação e comunicação",
    "K": "Bancos, seguros e finanças", "L": "Imóveis", "M": "Serviços profissionais e técnicos", "N": "Serviços administrativos",
    "O": "Administração pública", "P": "Educação", "Q": "Saúde e assistência social", "R": "Cultura, esporte e lazer",
    "S": "Outros serviços", "T": "Serviços domésticos", "U": "Organismos internacionais",
    "PF": "Pessoas físicas", "NI": "Não identificado", "IN": "Inválido ou sem setor",
}


def por_setor(arq: Path) -> dict[int, dict]:
    """Por ano: valor por setor da economia (seção da CNAE) e por imposto."""
    linhas = _linhas(arq)
    cab = [c.strip() for c in linhas[0]]
    anos: dict[int, dict] = {}
    for r in linhas[1:]:
        try:
            ano = int(r[0])
        except ValueError:
            continue
        mes, sec = _mes(r[1]), r[2].strip().upper()
        if not mes:
            continue
        a = anos.setdefault(ano, {"setor": defaultdict(float), "meses": set(), "imposto": defaultdict(lambda: defaultdict(float))})
        a["meses"].add(mes)
        for col, x in zip(cab[4:], r[4:]):
            v = numero(x)
            if v:
                a["setor"][sec] += v
                a["imposto"][sec][col] += v
    out = {}
    for ano, a in anos.items():
        itens = []
        for sec, v in sorted(a["setor"].items(), key=lambda t: -t[1]):
            imp = sorted(a["imposto"][sec].items(), key=lambda t: -t[1])[:4]
            itens.append({"secao": sec, "nome": SECAO_NOME.get(sec, sec), "valor": round(v, 2), "impostos": [[k, round(x, 2)] for k, x in imp]})
        out[ano] = {"ate_mes": max(a["meses"]), "setores": itens, "total": round(sum(a["setor"].values()), 2)}
    return out
