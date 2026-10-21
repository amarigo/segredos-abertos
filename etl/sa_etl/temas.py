"""Temas das votações, a partir de palavras da ementa da proposta e da descrição da votação.

Regras simples e públicas: cada tema tem uma lista de expressões. Uma votação pode ter vários temas.
As expressões são comparadas sem acento e em minúsculas, como palavra inteira ou começo de palavra.
"""
from __future__ import annotations

import re
import unicodedata

TEMAS: dict[str, list[str]] = {
    "Mulheres": ["mulher", "mulheres", "feminic", "violencia domestica", "maria da penha", "gestante", "maternidade",
                 "igualdade de genero", "igualdade salarial", "misoginia", "lactante", "dignidade menstrual"],
    "Micro e pequenas empresas": ["microempres", "pequena empresa", "pequenas empresas", "microempreendedor", "mei",
                                  "simples nacional", "empreendedor", "pronampe", "empresas de pequeno porte",
                                  "empresa de pequeno porte"],
    "Saúde": ["saude", "sus", "hospital", "medicament", "vacina", "doenca", "medic", "enfermag", "sanitari", "cancer"],
    "Educação": ["educacao", "escola", "ensino", "professor", "universidade", "estudante", "fundeb", "alfabetiz", "creche"],
    "Segurança pública": ["seguranca publica", "policia", "policial", "crime", "penal", "pena de", "presidio", "prisao",
                          "organizacao criminosa", "faccao", "trafico", "homicid"],
    "Armas": ["arma de fogo", "armas", "estatuto do desarmamento", "cac", "municao"],
    "Meio ambiente": ["meio ambiente", "ambiental", "desmatamento", "florest", "clima", "climatic", "licenciamento",
                      "agrotox", "agrotóx", "residuos", "carbono", "amazonia", "biodivers"],
    "Impostos e contas públicas": ["tribut", "imposto", "reforma tributaria", "orcament", "arcabouco fiscal", "fiscal",
                                   "icms", "ipi", "irpf", "imposto de renda", "contribuicao social", "divida publica",
                                   "credito extraordinario", "ldo", "loa"],
    "Trabalho e aposentadoria": ["trabalh", "emprego", "salario minimo", "previdencia", "aposentad", "clt", "sindic",
                                 "fgts", "seguro-desemprego", "inss"],
    "Agropecuária": ["agropecu", "agricult", "rural", "agronegocio", "pecuar", "safra", "fundiari", "terra indigena",
                     "marco temporal", "produtor rural"],
    "Crianças e adolescentes": ["crianca", "adolescente", "infancia", "infantil", "eca", "menor de idade", "juventude"],
    "Indígenas e minorias": ["indigena", "quilombol", "racial", "racismo", "pessoa com deficiencia", "lgbt",
                             "povos tradicionais", "idoso"],
    "Energia e combustíveis": ["energia", "eletric", "combustiv", "petroleo", "gas natural", "petrobras", "mineracao"],
    "Eleições e política": ["eleitor", "eleicao", "eleicoes", "partido politico", "partidos politicos", "fundo partidario",
                            "fundo eleitoral", "mandato", "anistia", "inelegib", "emenda parlamentar", "emendas parlamentares"],
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s)


def _padrao(t: str) -> str:
    t = re.escape(_norm(t))
    return t + r"\b" if len(t) <= 4 else t  # siglas curtas (MEI, SUS, ECA...) só como palavra inteira


_REGEX = {tema: re.compile(r"\b(?:" + "|".join(_padrao(t) for t in termos) + r")", re.I)
          for tema, termos in TEMAS.items()}


def temas_de(texto: str) -> list[str]:
    t = _norm(texto)
    return [tema for tema, rx in _REGEX.items() if rx.search(t)]


def temas_da_votacao(v: dict) -> list[str]:
    p = v.get("proposicao") or {}
    return temas_de(" ".join([p.get("ementa") or "", p.get("titulo") or "", v.get("descricao") or ""]))
