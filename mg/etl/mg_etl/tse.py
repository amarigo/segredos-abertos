"""Eleições de cada cidade, de 1996 até hoje, com os arquivos de dados abertos do TSE.

Fontes (CDN do TSE, um .zip por eleição, com um CSV por estado dentro):
- votacao_candidato_munzona_{ano}.zip: votos de cada candidato por município e zona, com partido, coligação e
  resultado (eleito, suplente, não eleito, 2º turno);
- consulta_cand_{ano}.zip: lista de candidatos. Usada só nas eleições municipais, para achar o vice-prefeito
  (o vice não recebe votos próprios, então não aparece no arquivo de votação).

Os arquivos do TSE são grandes (50 a 100 MB cada) e não mudam depois de fechados. Por isso guardamos no cache
só as linhas das cidades acompanhadas (cache/tse/{tipo}_{ano}.json) e apagamos o .zip. Nas próximas coletas
não baixamos de novo. A eleição do ano corrente é baixada de novo a cada 20 horas até o resultado fechar.

Os CSVs do TSE trazem CPF, e-mail e outros dados pessoais dos candidatos. Lemos só as colunas listadas em
COLUNAS: nada de CPF entra no cache nem no site.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import logging
import re
import time
import zipfile
from pathlib import Path
from typing import IO, Iterator

from sa_etl.util import avisar, download, eh_zip, norm_name

log = logging.getLogger("mg_etl.tse")

CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele"
URL = {
    "votacao": CDN + "/votacao_candidato_munzona/votacao_candidato_munzona_{ano}.zip",
    "cand": CDN + "/consulta_cand/consulta_cand_{ano}.zip",
}
MUNICIPAIS = list(range(1996, 2100, 4))  # 1996, 2000, ..., 2024
GERAIS = list(range(1998, 2100, 4))  # 1998, 2002, ..., 2022

# Só estas colunas são lidas. Nada de CPF, e-mail, data de nascimento ou título de eleitor.
COLUNAS = ["ANO_ELEICAO", "CD_TIPO_ELEICAO", "NM_TIPO_ELEICAO", "NR_TURNO", "SG_UF", "NM_UE", "NM_MUNICIPIO",
           "DS_CARGO", "SQ_CANDIDATO", "NR_CANDIDATO", "NM_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO",
           "NM_COLIGACAO", "DS_COMPOSICAO_COLIGACAO", "NM_FEDERACAO", "SG_FEDERACAO", "QT_VOTOS_NOMINAIS",
           "QT_VOTOS_NOMINAIS_VALIDOS", "DS_SIT_TOT_TURNO", "DS_SITUACAO_CANDIDATURA", "DS_DETALHE_SITUACAO_CAND"]
OBRIGATORIAS = {"votacao": {"ANO_ELEICAO", "NR_TURNO", "DS_CARGO", "SG_PARTIDO", "QT_VOTOS_NOMINAIS", "DS_SIT_TOT_TURNO"},
                "cand": {"ANO_ELEICAO", "DS_CARGO", "NR_CANDIDATO", "SG_PARTIDO"}}


def anos_ate(hoje: dt.date | None = None) -> tuple[list[int], list[int]]:
    """Eleições municipais e gerais já realizadas (a de outubro conta a partir de novembro)."""
    hoje = hoje or dt.date.today()
    feito = lambda a: a < hoje.year or (a == hoje.year and hoje.month >= 11)  # noqa: E731
    return [a for a in MUNICIPAIS if feito(a)], [a for a in GERAIS if feito(a)]


def chave_cidade(nome: str) -> str:
    return norm_name(nome).replace(" ", "")


def ler_csv(fonte: bytes | IO[bytes], obrigatorias: set[str] = frozenset()) -> Iterator[dict[str, str]]:
    """Lê um CSV do TSE (latin-1, ';', aspas), linha a linha (o de MG tem centenas de MB).

    Se não tiver cabeçalho, ou faltar alguma coluna obrigatória, falha: as colunas mudam de ano para ano e
    adivinhar a posição daria dados errados.
    """
    texto = io.StringIO(fonte.decode("latin-1")) if isinstance(fonte, bytes) else io.TextIOWrapper(fonte, encoding="latin-1", newline="")
    leitor = csv.reader(texto, delimiter=";", quotechar='"')
    cab = [c.strip().upper() for c in next(leitor, None) or []]
    if "ANO_ELEICAO" not in cab:
        raise ValueError("arquivo do TSE sem cabeçalho reconhecido")
    falta = set(obrigatorias) - set(cab)
    if falta:
        raise ValueError(f"colunas faltando no arquivo do TSE: {sorted(falta)}")
    idx = {c: i for i, c in enumerate(cab) if c in COLUNAS}
    for ln in leitor:
        if len(ln) < len(cab):
            continue
        yield {c: ln[i].strip() for c, i in idx.items()}


def cidade_da_linha(r: dict) -> str:
    return chave_cidade(r.get("NM_MUNICIPIO") or r.get("NM_UE") or "")


def linhas_do_zip(zip_path: Path, uf: str, cidades: set[str] | None, tipo: str) -> list[dict]:
    """Linhas de `uf` (e, se pedidas, só das `cidades`) de todos os CSVs do .zip que forem desse estado.

    Falha se alguma cidade pedida não aparecer: um arquivo sem a cidade quase sempre é um arquivo com outro
    formato, e guardar "nenhuma linha" no cache esconderia esse ano para sempre.
    """
    out = []
    with zipfile.ZipFile(zip_path) as z:
        nomes = [n for n in z.namelist() if n.lower().endswith((".csv", ".txt"))]
        do_estado = [n for n in nomes if re.search(rf"_{uf}\.(csv|txt)$", n, re.I)]
        if not nomes:
            raise ValueError("arquivo do TSE sem CSV dentro")
        for n in do_estado or nomes:  # anos antigos: um arquivo só, com todos os estados
            with z.open(n) as f:
                for r in ler_csv(f, OBRIGATORIAS[tipo]):
                    if r.get("SG_UF", uf) != uf:
                        continue
                    if cidades is None or cidade_da_linha(r) in cidades:
                        out.append(r)
    if cidades:
        faltam = cidades - {cidade_da_linha(r) for r in out}
        if faltam:
            raise ValueError(f"cidades sem nenhuma linha no arquivo do TSE: {sorted(faltam)}")
    return out


NOME_TIPO = {"votacao": "os votos", "cand": "a lista de candidatos"}


def _ler_cache(alvo: Path) -> dict | None:
    try:
        dados = json.loads(alvo.read_text(encoding="utf-8"))
        if isinstance(dados.get("linhas"), list) and isinstance(dados.get("cidades"), list):
            return dados
    except (OSError, ValueError, AttributeError):
        pass
    if alvo.exists():
        log.warning("Cache do TSE com defeito: %s", alvo.name)
    return None


def linhas(tipo: str, ano: int, uf: str, cidades: set[str], cache: Path, hoje: dt.date | None = None) -> list[dict] | None:
    """Linhas de uma eleição só das cidades acompanhadas, com cache permanente. None se não deu para obter."""
    alvo = cache / f"{tipo}_{ano}_{uf}.json"
    recente = ano >= (hoje or dt.date.today()).year - 1  # resultado pode ainda mudar (recontagem, cassação de registro)
    antigo = _ler_cache(alvo)
    if antigo and set(antigo["cidades"]) >= cidades and not (recente and _velho(alvo, 20)):
        return [r for r in antigo["linhas"] if cidade_da_linha(r) in cidades]
    zp = cache / "zips" / f"{tipo}_{ano}.zip"
    try:
        download(URL[tipo].format(ano=ano), zp, validar=eh_zip)
        rows = linhas_do_zip(zp, uf, cidades, tipo)
    except Exception as e:  # noqa: BLE001 - TSE fora do ar ou arquivo em outro formato: o resto do site segue
        log.warning("TSE %s %s: %s", tipo, ano, e)
        if antigo:  # cópia antiga, mesmo velha, é melhor que nada
            avisar(f"TSE: não foi possível atualizar {NOME_TIPO[tipo]} da eleição de {ano}; usamos a última cópia")
            return [r for r in antigo["linhas"] if cidade_da_linha(r) in cidades]
        avisar(f"TSE: {NOME_TIPO[tipo]} da eleição de {ano} não puderam ser baixados; o histórico das cidades ficou sem esse ano"
               if tipo == "votacao" else
               f"TSE: a lista de candidatos de {ano} não pôde ser baixada; o vice-prefeito desse ano ficou sem nome")
        return None
    finally:
        zp.unlink(missing_ok=True)
        zp.with_suffix(".zip.part").unlink(missing_ok=True)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(json.dumps({"cidades": sorted(cidades), "linhas": rows}, ensure_ascii=False), encoding="utf-8")
    return rows


def _velho(p: Path, horas: float) -> bool:
    return (time.time() - p.stat().st_mtime) / 3600 > horas


def linhas_estaduais(tipo: str, ano: int, uf: str, cargos: set[str], cache: Path) -> list[dict] | None:
    """Linhas de cargos estaduais (governador, vice, senador) de `uf`, com cache permanente (a eleição já fechou)."""
    alvo = cache / f"{tipo}_estado_{ano}_{uf}.json"
    antigo = _ler_cache(alvo)
    if antigo and set(antigo["cidades"]) >= cargos:
        return antigo["linhas"]
    zp = cache / "zips" / f"{tipo}_{ano}.zip"
    so = lambda r: re.sub(r"[^A-Z]", "", (r.get("DS_CARGO") or "").upper()) in cargos  # noqa: E731
    try:
        download(URL[tipo].format(ano=ano), zp, validar=eh_zip)
        rows = [r for r in linhas_do_zip(zp, uf, None, tipo) if so(r)]
        if not rows:
            raise ValueError(f"nenhuma linha de {sorted(cargos)}")
    except Exception as e:  # noqa: BLE001
        log.warning("TSE %s %s (estado): %s", tipo, ano, e)
        if antigo:
            return antigo["linhas"]
        avisar(f"TSE: {NOME_TIPO[tipo]} de {ano} para governador não puderam ser baixados")
        return None
    finally:
        zp.unlink(missing_ok=True)
        zp.with_suffix(".zip.part").unlink(missing_ok=True)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(json.dumps({"cidades": sorted(cargos), "linhas": rows}, ensure_ascii=False), encoding="utf-8")
    return rows
