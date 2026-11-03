"""Agrupa as dezenas de tipos de despesa da cota em três grupos fáceis de entender."""
from __future__ import annotations

import re

from .util import norm_name

GRUPOS = {
    "pessoal": "Com o próprio parlamentar (viagens, comida, transporte)",
    "escritorio": "Com o gabinete (escritório, telefone, material)",
    "servicos": "Com serviços contratados (divulgação, consultorias)",
}

_PESSOAL = (
    "PASSAGE", "AEREA", "AEREO", "HOSPEDAGEM", "ALIMENTACAO", "COMBUSTIV", "LOCACAO OU FRETAMENTO",
    "VEICULO", "TAXI", "PEDAGIO", "ESTACIONAMENTO", "LOCOMOCAO", "FRETAMENTO", "EMBARCAC",
    "TRANSPORTE", "AERONAVE",
)
_SERVICOS = (
    "DIVULGACAO", "CONSULTORIA", "PESQUISA", "TRABALHOS TECNICOS", "SEGURANCA", "CONTRATACAO",
    "ASSESSORIA", "SERVICOS DE APOIO",
)


def grupo_de(categoria: str) -> str:
    c = norm_name(categoria)
    if any(k in c for k in _PESSOAL):
        return "pessoal"
    if any(k in c for k in _SERVICOS):
        return "servicos"
    return "escritorio"


def categoria_curta(categoria: str) -> str:
    """Nome mais curto e legível para o tipo de despesa."""
    c = (categoria or "Não informado").strip()
    if len(c) > 70:
        c = c.split(",")[0].strip()
    c = c[:1].upper() + c[1:].lower() if c.isupper() else c
    # Siglas da Câmara: SIGEPA é a passagem comprada pela própria Câmara; RPA é a passagem paga pelo deputado e reembolsada
    return re.sub(r"\s*-\s*sigepa$", " (comprada pela Câmara)", re.sub(r"\s*-\s*rpa$", " (reembolsada ao deputado)", c, flags=re.I), flags=re.I)


# Temas para o resumo "Para onde vai o dinheiro": junta os nomes da Câmara e do Senado num nome curto.
# A ordem conta: a primeira regra que bate decide (o Senado junta locomoção, hospedagem, comida e combustível numa
# categoria só, por isso ela vem antes de combustível e hospedagem).
_TEMAS = (
    (("LOCOMOCAO, HOSPEDAGEM",), "Locomoção, hospedagem, comida e combustível (Senado)"),
    (("PASSAGE", "AERONAVE", "EMBARCAC"), "Viagens: passagens e fretamento de avião e barco"),
    (("COMBUSTIV",), "Combustível"),
    (("HOSPEDAGEM",), "Hospedagem"),
    (("ALIMENTACAO",), "Alimentação"),
    (("VEICULO", "TAXI", "PEDAGIO", "ESTACIONAMENTO", "LOCOMOCAO", "TRANSPORTE"), "Carro alugado, táxi, pedágio e estacionamento"),
    (("DIVULGACAO",), "Divulgação do mandato"),
    (("CONSULTORIA", "PESQUISA", "TRABALHOS TECNICOS", "ASSESSORIA", "SERVICOS DE APOIO"), "Consultorias, pesquisas e assessorias"),
    (("SEGURANCA",), "Segurança"),
    (("ESCRITORIO", "IMOVE", "ALUGUEL", "MATERIAL"), "Escritório: aluguel, contas e material"),
    (("TELEFON",), "Telefone"),
    (("POSTA",), "Correio"),
    (("ASSINATURA", "PUBLICAC"), "Assinaturas de jornais e revistas"),
    (("CURSO", "PALESTRA", "EVENTO"), "Cursos e eventos"),
)


def tema_de(categoria: str) -> str:
    """Nome curto do tipo de gasto para o resumo (viagens, combustível, divulgação...)."""
    c = norm_name(categoria)
    for chaves, tema in _TEMAS:
        if any(k in c for k in chaves):
            return tema
    return categoria_curta(categoria)
