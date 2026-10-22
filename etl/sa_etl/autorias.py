"""Propostas de cada parlamentar no ano, separando autoria própria de apoio.

A página do deputado na Câmara mostra um único número de "propostas de sua autoria". Esse número soma projetos,
requerimentos, emendas, pareceres de relator e até as propostas de colegas que o deputado só assinou junto. No Senado,
a lista de processos de um senador também traz tudo o que ele assinou. Para comparar parlamentares de forma justa,
contamos aqui, por ano:

- projetos: projetos (de lei, de lei complementar, de emenda à Constituição, de decreto legislativo e de resolução)
  em que o parlamentar é o primeiro autor;
- projetos_apoio: projetos de outro primeiro autor que ele assinou como coautor ou apoiador;
- requerimentos: requerimentos e indicações em que é o primeiro autor.

Câmara: arquivos anuais dos dados abertos (autores de cada proposição, com a ordem de assinatura, e o tipo de cada
proposição). Senado: lista de processos do senador; o primeiro nome na autoria é o autor principal.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import re
import tempfile
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import util

log = logging.getLogger("sa_etl.autorias")

VERSAO = 1  # aumente quando mudar a forma de contar, para não reaproveitar cache antigo
CAMARA_AUTORES = "https://dadosabertos.camara.leg.br/arquivos/proposicoesAutores/csv/proposicoesAutores-{ano}.csv"
CAMARA_PROPOSICOES = "https://dadosabertos.camara.leg.br/arquivos/proposicoes/csv/proposicoes-{ano}.csv"
SENADO_PROCESSOS = "https://legis.senado.leg.br/dadosabertos/processo?codigoParlamentarAutor={cod}&ano={ano}"

# Câmara: PRC é resolução da Câmara. Senado: PRS é resolução do Senado; PRN, do Congresso. PDC, PLS e PLC são siglas antigas.
PROJETOS = {"PL", "PLP", "PEC", "PDL", "PRC", "PRS", "PRN", "PDC", "PLS", "PLC"}
# Requerimentos (RIC e RQS incluem os pedidos de informação a ministérios) e indicações (INC, INS). Ficam de fora os
# requerimentos de procedimento da Câmara (RPD: adiar a votação, votação nominal...), usados aos milhares na obstrução.
REQUERIMENTOS = {"REQ", "RIC", "INC", "RQS", "RQN", "INS"}


def tipo(sigla: str) -> str | None:
    s = (sigla or "").strip().upper()
    return "projeto" if s in PROJETOS else "requerimento" if s in REQUERIMENTOS else None


def _vazio() -> dict[str, int]:
    return {"projetos": 0, "projetos_apoio": 0, "requerimentos": 0}


def contar_camara(autores, tipos: dict[str, str]) -> dict[str, dict[str, int]]:
    """autores: linhas de proposicoesAutores; tipos: {idProposicao: siglaTipo}. Devolve {id do deputado: contagens}."""
    out: dict[str, dict[str, int]] = defaultdict(_vazio)
    vistos: set[tuple[str, str]] = set()
    for a in autores:
        dep, prop = (a.get("idDeputadoAutor") or "").strip(), (a.get("idProposicao") or "").strip()
        if not dep.isdigit() or not prop or (dep, prop) in vistos:
            continue
        vistos.add((dep, prop))
        t = tipo(tipos.get(prop, ""))
        principal = (a.get("ordemAssinatura") or "").strip() == "1"
        if t == "projeto":
            out[dep]["projetos" if principal else "projetos_apoio"] += 1
        elif t == "requerimento" and principal:
            out[dep]["requerimentos"] += 1
        else:
            out.setdefault(dep, _vazio())  # assinou outro tipo de documento: aparece com zero
    return dict(out)


def _sem_acento(s: str) -> str:
    return util.norm_name(s)


def primeiro_autor(autoria: str) -> str:
    """'Senador Fulano (PL/RJ), Senadora Beltrana (PT/BA)' -> 'Senador Fulano (PL/RJ'."""
    return re.split(r"\)\s*,\s*", autoria or "", maxsplit=1)[0]


def contar_senado(processos: list[dict], nome: str) -> dict[str, int]:
    out = _vazio()
    alvo = _sem_acento(nome)
    vistos = set()
    for p in processos:
        chave = p.get("codigoMateria") or p.get("id")
        if chave in vistos:
            continue
        vistos.add(chave)
        t = tipo((p.get("identificacao") or "").split(" ")[0])
        principal = bool(alvo) and alvo in _sem_acento(primeiro_autor(p.get("autoria") or ""))
        if t == "projeto":
            out["projetos" if principal else "projetos_apoio"] += 1
        elif t == "requerimento" and principal:
            out["requerimentos"] += 1
    return out


def _fresco(f: Path, ano: int) -> bool:
    """Ano atual e anterior: refaz a cada 20 horas. Anos mais antigos: a cada 7 dias."""
    if not f.exists():
        return False
    horas = 20 if ano >= dt.date.today().year - 1 else 24 * 7
    return (time.time() - f.stat().st_mtime) / 3600 < horas


def _ler(f: Path):
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def camara(anos: list[int], cache: Path) -> dict[tuple[str, int], dict[str, int]]:
    """{("dep-123", 2025): contagens}. Guarda só o resumo de cada ano: os arquivos oficiais passam de 100 MB."""
    out: dict[tuple[str, int], dict[str, int]] = {}
    for ano in anos:
        f = cache / f"camara-{ano}-v{VERSAO}.json"
        resumo = _ler(f) if _fresco(f, ano) else None
        if resumo is None:
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    t = Path(tmp)
                    arq_aut = util.download(CAMARA_AUTORES.format(ano=ano), t / "autores.csv", validar=util.eh_csv)
                    arq_pro = util.download(CAMARA_PROPOSICOES.format(ano=ano), t / "proposicoes.csv", validar=util.eh_csv)
                    tipos = {r.get("id", ""): r.get("siglaTipo", "") for r in util.read_csv_file(arq_pro)}
                    resumo = contar_camara(util.read_csv_file(arq_aut), tipos)
                if not resumo:
                    raise ValueError("arquivo sem deputados")
                util.write_json(f, resumo)
            except Exception as e:  # noqa: BLE001 - sem o arquivo, usa o resumo anterior (se houver)
                log.warning("Câmara: autorias de %s indisponíveis (%s)", ano, e)
                resumo = _ler(f)
        for dep, c in (resumo or {}).items():
            out[(f"dep-{dep}", ano)] = c
    return out


def senado(senadores: list[dict], anos: list[int], cache: Path, workers: int = 6) -> dict[tuple[str, int], dict[str, int]]:
    tarefas = [(p, a) for p in senadores for a in anos]

    def um(pa):
        p, ano = pa
        f = cache / f"{p['id']}-{ano}-v{VERSAO}.json"
        if _fresco(f, ano):
            c = _ler(f)
            if c is not None:
                return c
        cod = p["id"].split("-", 1)[1]
        try:
            lista = util.get_json(SENADO_PROCESSOS.format(cod=cod, ano=ano), tries=3)
            if not isinstance(lista, list):
                raise ValueError("resposta não é uma lista")
        except Exception as e:  # noqa: BLE001
            log.debug("Senado: autorias de %s em %s indisponíveis (%s)", p["id"], ano, e)
            return _ler(f)
        c = contar_senado(lista, p.get("nome", ""))
        util.write_json(f, c)
        return c

    out = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for (p, ano), c in zip(tarefas, ex.map(um, tarefas)):
            if c is not None:
                out[(p["id"], ano)] = c
    return out


def coletar(politicos: list[dict], anos: list[int], cache: Path) -> dict[str, dict[int, dict[str, int]]]:
    """{politico_id: {ano: contagens}}, só para os parlamentares da lista."""
    cache.mkdir(parents=True, exist_ok=True)
    ids = {p["id"] for p in politicos}
    tudo = {}
    try:
        tudo.update(camara(anos, cache))
    except Exception as e:  # noqa: BLE001
        log.warning("Câmara: autorias indisponíveis (%s)", e)
    try:
        tudo.update(senado([p for p in politicos if p["casa"] == "senado"], anos, cache))
    except Exception as e:  # noqa: BLE001
        log.warning("Senado: autorias indisponíveis (%s)", e)
    out: dict[str, dict[int, dict[str, int]]] = {}
    for (pid, ano), c in tudo.items():
        if pid in ids:
            out.setdefault(pid, {})[ano] = c
    n = Counter(pid.split("-")[0] for pid in out)
    log.info("Autorias: %d deputados e %d senadores", n["dep"], n["sen"])
    return out
