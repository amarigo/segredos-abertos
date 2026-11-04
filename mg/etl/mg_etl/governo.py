"""Governo de Minas: quem foi eleito governador e vice, e links para o que o governo publica.

Fontes:
- TSE: resultado da eleição para governador (arquivo de votação) e o vice da chapa (lista de candidatos).
- Portal da Transparência de MG e Dados MG: salários, viagens, diárias e pagamentos do governo (links).
- Foto oficial do governador e do vice: arquivo de fotos dos candidatos do TSE (dados abertos, um ZIP por estado).
  O TSE não tem API de dados abertos com a foto (a do DivulgaCandContas recusa acesso automático, HTTP 403); o ZIP
  é oficial e traz a foto pelo número sequencial do candidato (SQ_CANDIDATO), o mesmo dos arquivos de votação.
  Só as fotos de quem foi eleito são copiadas para o site (fotos/tse/{ano}/{sq}.jpg).

O TSE registra quem foi eleito. Se o governador deixar o cargo (por exemplo, para disputar outra eleição), quem
assume é o vice; essa troca não aparece nos arquivos do TSE, e a página avisa.
"""
from __future__ import annotations

import logging
import re
import shutil
import zipfile
from pathlib import Path

from sa_etl.util import download, eh_zip

from . import partidos_hist, tse
from .cidades import _int, _nome, _ordinaria, _partido, _votos

log = logging.getLogger("mg_etl.governo")

LINKS = [
    {"nome": "Portal da Transparência de Minas Gerais", "url": "https://www.transparencia.mg.gov.br/",
     "explica": "Salário de cada servidor, despesas, contratos, convênios e repasses aos municípios."},
    {"nome": "Dados abertos do Governo de Minas", "url": "https://dados.mg.gov.br/",
     "explica": "Os arquivos completos: despesa por favorecido, remuneração, viagens e diárias."},
    {"nome": "Emendas estaduais (Dados MG)", "url": "https://dados.mg.gov.br/dataset/portal_emendas_estaduais",
     "explica": "Execução das emendas dos deputados estaduais: empenhos e pagamentos."},
    {"nome": "Assembleia Legislativa (ALMG)", "url": "https://www.almg.gov.br/",
     "explica": "Leis, projetos, gastos dos deputados estaduais e prestação de contas."},
    {"nome": "Tribunal de Contas do Estado (TCE-MG)", "url": "https://www.tce.mg.gov.br/",
     "explica": "Fiscaliza as contas do governo do estado e das prefeituras."},
]


FONTE_TSE = "https://dadosabertos.tse.jus.br/"
ZIP_FOTOS = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes{ano}/fotos/foto_cand{ano}_{uf}_div.zip"


def eleicao(ano: int, cache: Path, uf: str = "MG") -> dict | None:
    """Governador e vice eleitos em `ano` (eleição geral), com votos no estado."""
    vot = tse.linhas_estaduais("votacao", ano, uf, {"GOVERNADOR"}, cache)
    if not vot:
        return None
    soma: dict = {}
    for r in vot:
        if not _ordinaria(r):
            continue
        k = (_int(r.get("NR_TURNO")) or 1, r.get("SQ_CANDIDATO") or r.get("NR_CANDIDATO"))
        c = soma.setdefault(k, {"nome": _nome(r), "numero": r.get("NR_CANDIDATO") or "", "partido": _partido(r),
                                "sq": (r.get("SQ_CANDIDATO") or "").strip(),
                                "votos": 0, "sit": (r.get("DS_SIT_TOT_TURNO") or "").upper()})
        c["votos"] += _votos(r)
    if not soma:
        return None
    turno = max(t for t, _ in soma)
    cs = [c for (t, _), c in soma.items() if t == turno]
    total = sum(c["votos"] for c in cs) or 1
    eleitos = [c for c in cs if c["sit"].startswith("ELEITO")]
    if len(eleitos) != 1:
        log.warning("Governador %s: %d eleitos", ano, len(eleitos))
        return None
    g = eleitos[0]
    vice = None
    cand = tse.linhas_estaduais("cand", ano, uf, {"VICEGOVERNADOR"}, cache)
    for r in cand or []:
        if _int(r.get("NR_CANDIDATO")) == _int(g["numero"]) and _ordinaria(r):
            if vice is None or re.search(r"\b(APTO|DEFERIDO)\b", r.get("DS_SITUACAO_CANDIDATURA") or "", re.I):
                vice = r
    def pessoa(nome: str, partido: str, sq: str = "") -> dict:
        h = partidos_hist.hoje(partido, ano)
        p = {"nome": nome, "partido": partido, "partido_hoje": h["sigla"], "mudou": h["mudou"]}
        if re.fullmatch(r"\d{6,15}", sq or ""):
            p["sq"] = sq  # liga à foto do TSE (fotos())
        return p
    return {
        "eleicao": ano, "inicio": ano + 1, "fim": ano + 4, "turnos": turno,
        "governador": {**pessoa(g["nome"], g["partido"], g["sq"]), "votos": g["votos"], "pct": round(100 * g["votos"] / total, 2)},
        "vice": pessoa(_nome(vice), _partido(vice), (vice.get("SQ_CANDIDATO") or "").strip()) if vice else None,
        "candidatos": [{"nome": c["nome"], "partido": c["partido"], "votos": c["votos"], "pct": round(100 * c["votos"] / total, 2),
                        "eleito": c is g} for c in sorted(cs, key=lambda c: -c["votos"])[:6]],
    }


def _fotos_do_zip(ano: int, uf: str, sqs: set[str], cache: Path) -> dict[str, Path]:
    """Copia do ZIP de fotos do TSE só as fotos de `sqs` para o cache (guardadas para sempre: a eleição fechou)."""
    pasta = cache / "fotos" / str(ano)
    achadas = {sq: pasta / f"{sq}.jpg" for sq in sqs if (pasta / f"{sq}.jpg").exists()}
    sem_foto = pasta / "sem_foto.txt"  # quem o ZIP não tem: não adianta baixar dezenas de MB de novo todo dia
    ja_vistos = set(sem_foto.read_text(encoding="utf-8").split()) if sem_foto.exists() else set()
    faltam = sqs - set(achadas) - ja_vistos
    if not faltam:
        return achadas
    zp = cache / "zips" / f"fotos_{ano}_{uf}.zip"
    try:
        download(ZIP_FOTOS.format(ano=ano, uf=uf), zp, validar=eh_zip)
        with zipfile.ZipFile(zp) as z:
            for nome in z.namelist():
                m = re.fullmatch(r"F?[A-Z]{0,2}(\d+)(?:_div)?\.jpe?g", nome.rsplit("/", 1)[-1], re.I)
                if not m or m.group(1) not in faltam:
                    continue
                dados = z.read(nome)
                if not dados.startswith(b"\xff\xd8"):  # só JPEG de verdade
                    continue
                pasta.mkdir(parents=True, exist_ok=True)
                (pasta / f"{m.group(1)}.jpg").write_bytes(dados)
                achadas[m.group(1)] = pasta / f"{m.group(1)}.jpg"
        pasta.mkdir(parents=True, exist_ok=True)
        sem_foto.write_text("\n".join(sorted(ja_vistos | (faltam - set(achadas)))), encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        log.warning("TSE fotos %s %s: %s", ano, uf, e)
    finally:
        zp.unlink(missing_ok=True)
        zp.with_suffix(".zip.part").unlink(missing_ok=True)
    return achadas


def fotos(gov: dict, saida: Path, cache: Path, uf: str = "MG") -> int:
    """Põe a foto oficial (TSE) do governador e do vice de cada eleição em `saida`/fotos/tse/. Devolve quantas.

    Quem não tem foto fica sem o campo `foto`, e o site mostra as iniciais."""
    n = 0
    for e in gov.get("eleicoes") or []:
        pessoas = [p for p in (e.get("governador"), e.get("vice")) if p]
        achadas = _fotos_do_zip(e["eleicao"], uf, {p["sq"] for p in pessoas if p.get("sq")}, cache)
        for p in pessoas:
            sq = p.pop("sq", None)
            if sq and sq in achadas:
                rel = f"fotos/tse/{e['eleicao']}/{sq}.jpg"
                (saida / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(achadas[sq], saida / rel)
                p["foto"] = rel
                n += 1
    return n


def coletar(cache: Path) -> dict:
    _, gerais = tse.anos_ate()
    eleicoes = []
    for ano in gerais[-2:][::-1]:  # as duas últimas eleições gerais
        e = eleicao(ano, cache / "tse")
        if e:
            eleicoes.append(e)
    return {"eleicoes": eleicoes, "links": LINKS, "fonte_tse": FONTE_TSE}
