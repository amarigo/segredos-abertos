"""Candidatos e bens declarados ao TSE, pelos dados abertos de cada eleição.

API primeiro: o Portal de Dados Abertos do TSE tem uma API (CKAN, dadosabertos.tse.jus.br/api/3) que diz onde está
cada arquivo de cada eleição ("Candidatos" e "Bens de candidatos"). Os dados em si só existem como CSV dentro de ZIP,
no CDN do TSE: o portal não liga a consulta de dados (datastore) e a API do DivulgaCandContas, que mostra cada
candidato, recusa acesso automático (HTTP 403, conferido do GitHub Actions em 04/11/2026; veja
eleicao2026/etl/el_etl/eleitos.py). Por isso a API serve para achar o arquivo e o arquivo traz os dados.

Os arquivos trazem CPF, e-mail e título de eleitor. Lemos só as colunas de COLUNAS_CAND e COLUNAS_BEM: nada disso
entra no cache nem no site. Do arquivo de bens não guardamos a descrição de cada bem (pode ter endereço, placa,
número de conta): só o tipo e o valor.

O cache guarda, por eleição, a lista reduzida de candidatos (tse/cand-{ano}.json.gz) e a soma dos bens de cada
candidato (tse/bens-{ano}.json.gz). O ZIP é apagado depois de lido. Eleição passada muda pouco (o TSE corrige um
registro ou outro): lemos de novo a cada 30 dias.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import json
import logging
import tempfile
import time
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Iterator

from .util import (
    _BRASILIA,
    avisar,
    data_do_arquivo,
    download,
    eh_zip,
    get_json,
    to_float,
)

log = logging.getLogger("sa_etl.tse")

CKAN = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id={pacote}"
PAGINA = "https://dadosabertos.tse.jus.br/dataset/{pacote}"
CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele"
ARQUIVO = {"cand": CDN + "/consulta_cand/consulta_cand_{ano}.zip",
           "bens": CDN + "/bem_candidato/bem_candidato_{ano}.zip"}
PREFIXO = {"cand": "consulta_cand_", "bens": "bem_candidato_"}
DIAS = 30

# Colunas lidas (e só elas). Nada de CPF, e-mail, título de eleitor.
COLUNAS_CAND = ["ANO_ELEICAO", "NM_TIPO_ELEICAO", "NR_TURNO", "DT_ELEICAO", "DS_ELEICAO", "SG_UF", "SG_UE", "NM_UE",
                "DS_CARGO", "SQ_CANDIDATO", "NR_CANDIDATO", "NM_CANDIDATO", "NM_URNA_CANDIDATO", "SG_PARTIDO",
                "DT_NASCIMENTO", "DS_SITUACAO_CANDIDATURA", "DS_SIT_TOT_TURNO"]
CAMPOS = ["ano", "tipo", "turno", "data", "eleicao", "uf", "ue", "nm_ue", "cargo", "sq", "nr", "nome", "urna",
          "partido", "nasc", "situacao", "resultado"]
COLUNAS_BEM = ["SQ_CANDIDATO", "DS_TIPO_BEM_CANDIDATO", "VR_BEM_CANDIDATO"]


BUSCA = "https://dadosabertos.tse.jus.br/api/3/action/package_search?q=name:candidatos-{ano}*&rows=5"
_PACOTE: dict[int, str] = {}  # nome achado na API (2020 se chama "candidatos-2020-subtemas")


def pacote(ano: int) -> str:
    return _PACOTE.get(ano, f"candidatos-{ano}")


def _recursos(ano: int) -> list[dict]:
    """Arquivos do pacote da eleição. Quase todo ano o pacote é "candidatos-{ano}"; se não for, a busca da API acha."""
    try:
        d = get_json(CKAN.format(pacote=pacote(ano)), timeout=60, tries=2)
        return (d.get("result") or {}).get("resources") or []
    except Exception:  # noqa: BLE001
        d = get_json(BUSCA.format(ano=ano), timeout=60, tries=2)
        for r in (d.get("result") or {}).get("results") or []:
            if str(r.get("name") or "").startswith(f"candidatos-{ano}"):
                _PACOTE[ano] = r["name"]
                return r.get("resources") or []
        raise


def url(tipo: str, ano: int) -> str:
    """Endereço do arquivo pela API do portal; se a API não responder, o endereço de sempre no CDN."""
    try:
        for r in _recursos(ano):
            u = str(r.get("url") or "")
            if u.rsplit("/", 1)[-1] == f"{PREFIXO[tipo]}{ano}.zip":
                return u
        log.warning("TSE: a API do portal não lista %s de %s; usando o endereço do CDN", tipo, ano)
    except Exception as e:  # noqa: BLE001
        log.warning("TSE: API do portal sem resposta para %s %s (%s); usando o endereço do CDN", tipo, ano, e)
    return ARQUIVO[tipo].format(ano=ano)


def _csvs(caminho: Path, tipo: str) -> list[str]:
    """O arquivo de todo o país (_BRASIL.csv) quando existe; senão, um por estado."""
    with zipfile.ZipFile(caminho) as z:
        nomes = [n for n in z.namelist() if n.lower().endswith(".csv") and n.startswith(PREFIXO[tipo])]
    br = [n for n in nomes if n.upper().endswith("_BRASIL.CSV")]
    return br or nomes


def ler(caminho: Path, tipo: str, colunas: list[str]) -> Iterator[dict[str, str]]:
    """Linhas do ZIP do TSE (latin-1, ';'), só com as colunas pedidas. Falta coluna: erro (não adivinhamos)."""
    with zipfile.ZipFile(caminho) as z:
        for nome in _csvs(caminho, tipo):
            with z.open(nome) as f:
                leitor = csv.reader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";", quotechar='"')
                cab = [c.strip().upper() for c in next(leitor, None) or []]
                falta = set(colunas) - set(cab)
                if falta:
                    raise ValueError(f"{nome}: colunas faltando no arquivo do TSE: {sorted(falta)}")
                idx = [cab.index(c) for c in colunas]
                for ln in leitor:
                    if len(ln) >= len(cab):
                        yield {c: ln[i].strip() for c, i in zip(colunas, idx)}


def _ler_gz(f: Path):
    with gzip.open(f, "rt", encoding="utf-8") as g:
        return json.load(g)


def _gravar_gz(f: Path, dados) -> None:
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".part")
    with gzip.open(tmp, "wt", encoding="utf-8") as g:
        json.dump(dados, g, ensure_ascii=False, separators=(",", ":"))
    tmp.replace(f)


def _com_cache(f: Path, montar, descricao: str):
    """Cópia com menos de DIAS dias serve; senão monta de novo. Se a fonte falhar, usa a cópia antiga e avisa."""
    if f.exists() and (time.time() - f.stat().st_mtime) < DIAS * 86400:
        try:
            return _ler_gz(f)
        except (OSError, ValueError):
            pass
    try:
        dados = montar()
    except Exception as e:  # noqa: BLE001
        if f.exists():
            log.warning("%s: fonte fora do ar (%s); usando a cópia de %s", descricao, e, data_do_arquivo(f))
            avisar(f"{descricao}: o TSE não respondeu; usando a cópia de {data_do_arquivo(f)}")
            return _ler_gz(f)
        raise
    _gravar_gz(f, dados)
    return dados


def _baixar(tipo: str, ano: int, pasta: Path) -> Path:
    return download(url(tipo, ano), pasta / f"{tipo}-{ano}.zip", validar=eh_zip)


def _norm_data(s: str) -> str:
    """'30/04/1981' -> '1981-04-30'; outro formato (ou 'NÃO DIVULGÁVEL') -> ''."""
    s = (s or "").strip()
    return f"{s[6:10]}-{s[3:5]}-{s[0:2]}" if len(s) == 10 and s[2] == "/" and s[5] == "/" else ""


def linha_candidato(r: dict[str, str]) -> list:
    return [int(to_float(r["ANO_ELEICAO"])), "sup" if "SUPLEMENTAR" in r["NM_TIPO_ELEICAO"].upper() else "ord",
            int(to_float(r["NR_TURNO"]) or 1), _norm_data(r["DT_ELEICAO"]), r["DS_ELEICAO"], r["SG_UF"], r["SG_UE"],
            r["NM_UE"], r["DS_CARGO"].upper(), r["SQ_CANDIDATO"], r["NR_CANDIDATO"], r["NM_CANDIDATO"],
            r["NM_URNA_CANDIDATO"], r["SG_PARTIDO"], _norm_data(r["DT_NASCIMENTO"]), r["DS_SITUACAO_CANDIDATURA"],
            r["DS_SIT_TOT_TURNO"]]


def candidatos(ano: int, cache: Path) -> list[dict]:
    """Todos os candidatos da eleição (uma linha por candidato e turno), só com os CAMPOS."""
    pasta = cache / "tse"

    def montar():
        with tempfile.TemporaryDirectory() as tmp:
            z = _baixar("cand", ano, Path(tmp))
            return [linha_candidato(r) for r in ler(z, "cand", COLUNAS_CAND)]
    linhas = _com_cache(pasta / f"cand-{ano}.json.gz", montar, f"Candidatos de {ano} (TSE)")
    return [dict(zip(CAMPOS, x)) for x in linhas]


def somar_bens(linhas) -> dict[str, list]:
    """{sq: [total, {tipo: valor}]}. Valor com vírgula decimal ('5059,16')."""
    out: dict[str, list] = {}
    for r in linhas:
        v = to_float(r["VR_BEM_CANDIDATO"].replace(".", "").replace(",", ".")) if "," in r["VR_BEM_CANDIDATO"] \
            else to_float(r["VR_BEM_CANDIDATO"])
        if v < 0:
            continue
        x = out.setdefault(r["SQ_CANDIDATO"], [0.0, defaultdict(float)])
        x[0] += v
        x[1][r["DS_TIPO_BEM_CANDIDATO"].strip() or "Não informado"] += v
    return {sq: [round(t, 2), {k: round(v, 2) for k, v in tipos.items()}] for sq, (t, tipos) in out.items()}


def bens(ano: int, cache: Path) -> dict[str, list]:
    pasta = cache / "tse"

    def montar():
        with tempfile.TemporaryDirectory() as tmp:
            z = _baixar("bens", ano, Path(tmp))
            return somar_bens(ler(z, "bens", COLUNAS_BEM))
    return _com_cache(pasta / f"bens-{ano}.json.gz", montar, f"Bens de candidatos de {ano} (TSE)")


def lido_em(tipo: str, ano: int, cache: Path) -> str:
    """Dia (AAAA-MM-DD, horário de Brasília) em que a cópia guardada do arquivo foi lida do TSE."""
    f = cache / "tse" / f"{tipo}-{ano}.json.gz"
    quando = f.stat().st_mtime if f.exists() else time.time()
    return dt.datetime.fromtimestamp(quando, _BRASILIA).date().isoformat()
