"""Partidos que mudaram de nome ou se juntaram a outro desde 1996.

Para cobrar um partido pelo que fez na cidade, é preciso saber como ele se chama hoje: o PMDB de 2000 é o MDB,
o PFL virou DEM e depois União Brasil. A sigla do dia da eleição continua aparecendo; o nome de hoje vai ao lado.

Fontes: registros de partidos do TSE (tse.jus.br/partidos/partidos-registrados-no-tse) e as resoluções que
aprovaram cada mudança de nome, fusão ou incorporação.
"""
from __future__ import annotations

import re

# sigla antiga -> (sigla de hoje, o que aconteceu)
SUCESSOR: dict[str, tuple[str, str]] = {
    "PMDB": ("MDB", "mudou o nome para MDB em 2017"),
    "PFL": ("UNIÃO", "virou DEM em 2007, que se juntou ao PSL em 2022 para formar o União Brasil"),
    "DEM": ("UNIÃO", "se juntou ao PSL em 2022 para formar o União Brasil"),
    "PSL": ("UNIÃO", "se juntou ao DEM em 2022 para formar o União Brasil"),
    "PPB": ("PP", "mudou o nome para PP (Progressistas) em 2003"),
    "PRONA": ("PL", "se juntou ao antigo PL em 2006 para formar o PR, que voltou a se chamar PL em 2019"),
    "PR": ("PL", "voltou a se chamar PL em 2019"),
    "PST": ("PL", "foi incorporado pelo PL em 2003"),
    "PGT": ("PL", "foi incorporado pelo PL em 2003"),
    "PRB": ("REPUBLICANOS", "mudou o nome para Republicanos em 2019"),
    "PPS": ("CIDADANIA", "mudou o nome para Cidadania em 2019"),
    "PTN": ("PODE", "mudou o nome para Podemos em 2017"),
    "PHS": ("PODE", "foi incorporado pelo Podemos em 2019"),
    "PSC": ("PODE", "foi incorporado pelo Podemos em 2023"),
    "PSDC": ("DC", "mudou o nome para Democracia Cristã em 2017"),
    "PTDOB": ("AVANTE", "mudou o nome para Avante em 2017"),
    "PEN": ("PRD", "virou Patriota em 2018, que se juntou ao PTB em 2023 para formar o PRD"),
    "PATRI": ("PRD", "se juntou ao PTB em 2023 para formar o PRD"),
    "PATRIOTA": ("PRD", "se juntou ao PTB em 2023 para formar o PRD"),
    "PRP": ("PRD", "foi incorporado pelo Patriota em 2019, que se juntou ao PTB em 2023 para formar o PRD"),
    "PTB": ("PRD", "se juntou ao Patriota em 2023 para formar o PRD"),
    "PAN": ("PRD", "foi incorporado pelo PTB em 2006, que se juntou ao Patriota em 2023 para formar o PRD"),
    "PROS": ("SOLIDARIEDADE", "foi incorporado pelo Solidariedade em 2023"),
    "SD": ("SOLIDARIEDADE", "é a sigla antiga do Solidariedade"),
    "PPL": ("PCDOB", "foi incorporado pelo PCdoB em 2019"),
    "PRN": ("AGIR", "virou PTC em 2000, que mudou o nome para Agir em 2022"),
    "PTC": ("AGIR", "mudou o nome para Agir em 2022"),
    "PMN": ("MOBILIZA", "mudou o nome para Mobiliza em 2023"),
}
# Como escrever a sigla de hoje (as chaves acima são só letras, em maiúsculas)
GRAFIA = {"UNIÃO": "UNIÃO", "PCDOB": "PCdoB", "PODE": "PODE", "SOLIDARIEDADE": "SOLIDARIEDADE", "MOBILIZA": "MOBILIZA"}


def chave(sigla: str) -> str:
    """'PC do B' -> 'PCDOB', 'PT do B' -> 'PTDOB', 'União' -> 'UNIÃO'."""
    return re.sub(r"[^A-ZÃ]", "", (sigla or "").upper())


def sigla_limpa(sigla: str) -> str:
    """Grafia única para a mesma sigla, que o TSE escreve de jeitos diferentes em anos diferentes."""
    k = chave(sigla)
    return {"PCDOB": "PCdoB", "PTDOB": "PTdoB", "SOLIDARIEDADE": "SOLIDARIEDADE", "SD": "SD"}.get(k, (sigla or "").strip().upper())


def hoje(sigla: str, ano: int) -> dict:
    """Como o partido se chama hoje. {"sigla": ..., "mudou": texto ou None}.

    O PSD de antes de 2011 é outro partido (incorporado pelo PTB em 2003), sem relação com o PSD de hoje.
    """
    k = chave(sigla)
    if k == "PSD" and ano < 2011:
        return {"sigla": "PRD", "mudou": "o PSD antigo foi incorporado pelo PTB em 2003 (não é o PSD de hoje, criado em 2011); o PTB se juntou ao Patriota em 2023 para formar o PRD"}
    if k == "PL" and ano < 2006:
        return {"sigla": "PL", "mudou": "se juntou ao Prona em 2006 para formar o PR, que voltou a se chamar PL em 2019"}
    if k in SUCESSOR:
        novo, como = SUCESSOR[k]
        return {"sigla": GRAFIA.get(novo, novo), "mudou": como}
    return {"sigla": sigla_limpa(sigla), "mudou": None}
