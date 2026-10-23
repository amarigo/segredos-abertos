"""Página de cada cidade: quem governou e quem legislou, por partido, desde 1996, e como a cidade votou.

Tudo vem do TSE (ver tse.py). O TSE registra o partido no dia da eleição. Trocas de partido no meio do mandato,
cassações, renúncias e suplentes que assumiram não aparecem nesses arquivos; o site avisa isso na página.
"""
from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from pathlib import Path

from sa_etl.util import norm_name, write_json

from . import partidos_hist, tse

log = logging.getLogger("mg_etl.cidades")

CIDADES = [
    {"id": "itajuba", "nome": "Itajubá", "uf": "MG",
     "links": [{"nome": "Câmara Municipal de Itajubá", "url": "https://www.itajuba.mg.leg.br/"},
               {"nome": "Sessões e projetos da Câmara (SisCam)", "url": "https://itajuba.siscam.com.br/"},
               {"nome": "Portal da Transparência da Prefeitura", "url": "https://www.itajuba.mg.gov.br/transparencia"}]},
    {"id": "paraisopolis", "nome": "Paraisópolis", "uf": "MG",
     "links": [{"nome": "Câmara Municipal de Paraisópolis", "url": "https://www.paraisopolis.mg.leg.br/"},
               {"nome": "Portal da Transparência da Prefeitura", "url": "https://www.paraisopolis.mg.gov.br/servicos/portal-da-transparencia/"}]},
]

MAJORITARIOS = ["PRESIDENTE", "GOVERNADOR", "SENADOR"]
PROPORCIONAIS = ["DEPUTADO FEDERAL", "DEPUTADO ESTADUAL"]
TOP_MAJ, TOP_PROP = 6, 10


def _int(x) -> int:
    try:
        return int(float(str(x or "0").replace(",", ".")))
    except ValueError:
        return 0


def _ordinaria(r: dict) -> bool:
    """Só eleições ordinárias (as de outubro). Suplementares ficam de fora."""
    tipo = (r.get("NM_TIPO_ELEICAO") or "").upper()
    cod = r.get("CD_TIPO_ELEICAO") or ""
    return ("SUPLEMENTAR" not in tipo) and (cod in ("", "2") or "ORDIN" in tipo)


def _eleito(sit: str) -> bool:
    """'ELEITO', 'ELEITO POR QP', 'ELEITO POR MÉDIA' e, nos arquivos antigos, só 'MÉDIA'. 'NÃO ELEITO' não."""
    s = (sit or "").upper().strip()
    return s.startswith("ELEITO") or s in ("MÉDIA", "MEDIA")


NULOS = {"", "#NULO#", "#NULO", "#NE#", "#NE", "NULO", "-1", "-3"}


def _txt(v) -> str:
    """O TSE escreve '#NULO#' ou '#NE#' (não se aplica) onde não há valor."""
    v = (v or "").strip()
    return "" if v.upper() in NULOS else v


def _nome(r: dict) -> str:
    """Nome de urna (o que aparece na urna e que o eleitor conhece); se não houver, o nome completo."""
    nome = (_txt(r.get("NM_URNA_CANDIDATO")) or _txt(r.get("NM_CANDIDATO"))).title()
    return re.sub(r"(?<=\s)(Da|De|Do|Das|Dos|E)(?=\s)", lambda m: m.group(1).lower(), nome)


def _votos(r: dict) -> int:
    """Votos válidos quando o arquivo traz (desde 2020): candidato com registro negado tem os votos anulados."""
    v = r.get("QT_VOTOS_NOMINAIS_VALIDOS")
    return _int(v) if v not in (None, "", "#NULO#", "-1") else _int(r.get("QT_VOTOS_NOMINAIS"))


def _partido(r: dict) -> str:
    return partidos_hist.sigla_limpa(_txt(r.get("SG_PARTIDO")))


def _partidos_coligacao(r: dict) -> list[str]:
    """'PMDB / PSDB / PFL' -> ['PMDB', 'PSDB', 'PFL']. Federações (desde 2022) aparecem pelos partidos de dentro."""
    comp = re.sub(r"(?i)federa[çc][ãa]o|\(|\)|\[|\]", " ", r.get("DS_COMPOSICAO_COLIGACAO") or "")
    ps = []
    for x in re.split(r"[/,+]", comp):
        x = x.strip()
        if x and x.upper() not in ("#NULO#", "#NE#") and partidos_hist.sigla_limpa(x) not in ps:
            ps.append(partidos_hist.sigla_limpa(x))
    return ps or [_partido(r)]


def _coligacao_nome(r: dict) -> str:
    n = _txt(r.get("NM_COLIGACAO"))
    return "" if n.upper() == "PARTIDO ISOLADO" else n


def candidatos(rows: list[dict], cargo: str) -> dict[int, list[dict]]:
    """Votos somados por candidato (todas as zonas da cidade), por turno, do mais ao menos votado."""
    soma: dict[tuple, dict] = {}
    for r in rows:
        if (r.get("DS_CARGO") or "").upper() != cargo or not _ordinaria(r):
            continue
        turno = _int(r.get("NR_TURNO")) or 1
        k = (turno, r.get("SQ_CANDIDATO") or (r.get("NR_CANDIDATO"), r.get("NM_CANDIDATO")))
        c = soma.setdefault(k, {"nome": _nome(r), "numero": r.get("NR_CANDIDATO") or "", "partido": _partido(r),
                                "coligacao": _coligacao_nome(r), "partidos_coligacao": _partidos_coligacao(r),
                                "votos": 0, "situacao": (r.get("DS_SIT_TOT_TURNO") or "").upper()})
        c["votos"] += _votos(r)
    por_turno: dict[int, list[dict]] = defaultdict(list)
    for (turno, _), c in soma.items():
        por_turno[turno].append(c)
    for turno, cs in por_turno.items():
        total = sum(c["votos"] for c in cs)
        for c in cs:
            c["pct"] = round(100 * c["votos"] / total, 2) if total else None
            c["eleito"] = _eleito(c["situacao"])
        cs.sort(key=lambda c: (-c["votos"], c["nome"]))
    return dict(por_turno)


def _cargo(r: dict) -> str:
    return re.sub(r"[^A-Z]", "", (r.get("DS_CARGO") or "").upper())


def _pessoa(nome: str, partido: str, ano: int, **extra) -> dict:
    h = partidos_hist.hoje(partido, ano)
    return {"nome": nome, "partido": partido, "partido_hoje": h["sigla"], "mudou": h["mudou"], **extra}


def _vice(cand_rows: list[dict] | None, numero: str, ano: int, coligacao: str = "", partido: str = "") -> dict | None:
    """O vice da chapa do prefeito eleito, na lista de candidatos do TSE.

    Desde 2004 o vice tem o mesmo número do prefeito. Em 2000 não: o vice tinha o número do próprio partido com
    um dígito a mais (prefeito 40, vice 401; ou vice de outro partido da coligação, 331). Por isso, se o número
    não bate, procuramos o vice da mesma coligação. Em 1996 o arquivo do TSE não traz os vices."""
    if not cand_rows or not numero:
        return None
    vices = [r for r in cand_rows if _cargo(r) == "VICEPREFEITO" and _ordinaria(r)]
    # Arquivos antigos escrevem "VICE PREFEITO" (sem hífen) e às vezes o número com zero à esquerda
    achados = [r for r in vices if _int(r.get("NR_CANDIDATO")) == _int(numero)]
    if not achados and coligacao:
        chave = norm_name(coligacao)
        achados = [r for r in vices if _coligacao_nome(r) and norm_name(_coligacao_nome(r)) == chave]
    if not achados:  # partido sozinho (sem coligação): o vice é do mesmo partido, com o número começando igual
        achados = [r for r in vices if str(_int(r.get("NR_CANDIDATO"))).startswith(str(_int(numero)))
                   and len(str(_int(r.get("NR_CANDIDATO")))) == len(str(_int(numero))) + 1 and _partido(r) == partido]
    if not achados:
        return None
    # "INAPTO" e "INDEFERIDO" contêm "APTO" e "DEFERIDO": só a palavra inteira conta
    achados.sort(key=lambda r: 0 if re.search(r"\b(APTO|DEFERIDO)\b", f'{r.get("DS_SITUACAO_CANDIDATURA") or ""} '
                                                                        f'{r.get("DS_DETALHE_SITUACAO_CAND") or ""}', re.I) else 1)
    return _pessoa(_nome(achados[0]), _partido(achados[0]), ano)


def executivo(ano: int, rows: list[dict], cand_rows: list[dict] | None) -> dict | None:
    """Quem foi eleito prefeito (e vice) em `ano`, para o mandato que começa em 1º de janeiro seguinte."""
    turnos = candidatos(rows, "PREFEITO")
    if not turnos:
        return None
    ultimo = max(turnos)
    vencedores = [c for c in turnos[ultimo] if c["eleito"]]
    if len(vencedores) != 1:
        log.warning("Prefeito %s: %d eleitos no %dº turno", ano, len(vencedores), ultimo)
        return None
    p = vencedores[0]
    return {
        "eleicao": ano, "inicio": ano + 1, "fim": ano + 4, "turnos": ultimo,
        "prefeito": _pessoa(p["nome"], p["partido"], ano, votos=p["votos"], pct=p["pct"]),
        "vice": _vice(cand_rows, p["numero"], ano, p["coligacao"], p["partido"]),
        "coligacao": {"nome": p["coligacao"], "partidos": p["partidos_coligacao"]},
        "candidatos": [{"turno": t, **{k: c[k] for k in ("nome", "partido", "votos", "pct", "eleito")}}
                       for t in sorted(turnos) for c in turnos[t]],
    }


def camara(ano: int, rows: list[dict], coligacao_prefeito: list[str], partido_prefeito: str) -> dict | None:
    """Vereadores eleitos em `ano` e quantas cadeiras cada partido ganhou."""
    turnos = candidatos(rows, "VEREADOR")
    eleitos = [c for c in turnos.get(1, []) if c["eleito"]]
    if not eleitos:
        return None
    cad = Counter(c["partido"] for c in eleitos)
    colig = set(coligacao_prefeito)
    return {
        "eleicao": ano, "inicio": ano + 1, "fim": ano + 4, "vagas": len(eleitos),
        "por_partido": [{"partido": p, "partido_hoje": partidos_hist.hoje(p, ano)["sigla"], "cadeiras": n,
                         "do_prefeito": p == partido_prefeito, "da_coligacao": p in colig}
                        for p, n in sorted(cad.items(), key=lambda kv: (-kv[1], kv[0]))],
        "eleitos": [{k: c[k] for k in ("nome", "partido", "votos")} for c in eleitos],
        "do_partido_do_prefeito": cad.get(partido_prefeito, 0),
        "da_coligacao_do_prefeito": sum(n for p, n in cad.items() if p in colig),
    }


def gerais(ano: int, rows: list[dict]) -> dict | None:
    """Como a cidade votou para presidente, governador, senador e deputados (só os mais votados de cada cargo)."""
    cargos = []
    for cargo in MAJORITARIOS + PROPORCIONAIS:
        top = TOP_MAJ if cargo in MAJORITARIOS else TOP_PROP
        for turno, cs in sorted(candidatos(rows, cargo).items()):
            total = sum(c["votos"] for c in cs)
            if not total:
                continue
            cargos.append({"cargo": cargo.title(), "turno": turno, "total_votos": total, "n_candidatos": len(cs),
                           "candidatos": [{k: c[k] for k in ("nome", "partido", "votos", "pct", "eleito")} for c in cs[:top]]})
    return {"eleicao": ano, "cargos": cargos} if cargos else None


def resumo(exe: list[dict], cam: list[dict]) -> dict:
    """Quantos anos cada partido (pelo nome de hoje) governou a cidade, e quantas vezes o prefeito teve maioria."""
    anos: Counter = Counter()
    siglas: dict[str, list[str]] = defaultdict(list)
    for m in exe:
        hoje = m["prefeito"]["partido_hoje"]
        anos[hoje] += m["fim"] - m["inicio"] + 1
        if m["prefeito"]["partido"] not in siglas[hoje]:
            siglas[hoje].append(m["prefeito"]["partido"])
    cadeiras: Counter = Counter()
    for c in cam:
        for x in c["por_partido"]:
            cadeiras[x["partido_hoje"]] += x["cadeiras"]
    maioria = sum(1 for c in cam if c["da_coligacao_do_prefeito"] * 2 > c["vagas"])
    return {
        "anos_por_partido": [{"partido": p, "anos": n, "siglas": siglas[p]} for p, n in sorted(anos.items(), key=lambda kv: (-kv[1], kv[0]))],
        "cadeiras_por_partido": [{"partido": p, "cadeiras": n} for p, n in sorted(cadeiras.items(), key=lambda kv: (-kv[1], kv[0]))],
        "mandatos": len(exe), "camaras": len(cam), "coligacao_do_prefeito_com_maioria": maioria,
    }


def montar_cidade(cfg: dict, municipais: dict[int, tuple[list | None, list | None]], ger: dict[int, list | None]) -> dict:
    chave = tse.chave_cidade(cfg["nome"])
    so = lambda rows: [r for r in rows or [] if tse.chave_cidade(r.get("NM_MUNICIPIO") or r.get("NM_UE") or "") == chave]  # noqa: E731
    exe, cam, faltando = [], [], []
    for ano in sorted(municipais):
        vot, cand = municipais[ano]
        if vot is None:
            faltando.append(ano)
            continue
        e = executivo(ano, so(vot), so(cand) if cand is not None else None)
        if e:
            exe.append(e)
        c = camara(ano, so(vot), (e or {}).get("coligacao", {}).get("partidos", []), (e or {}).get("prefeito", {}).get("partido", ""))
        if c:
            cam.append(c)
    g = [x for x in (gerais(ano, so(rows)) for ano, rows in sorted(ger.items()) if rows is not None) if x]
    avisos = [f"Os dados do TSE da eleição de {a} não puderam ser baixados nesta atualização." for a in faltando]
    return {"id": cfg["id"], "nome": cfg["nome"], "uf": cfg["uf"], "links": cfg.get("links", []),
            "executivo": exe[::-1], "camara": cam[::-1], "gerais": g[::-1], "resumo": resumo(exe, cam), "avisos": avisos}


def coletar(saida: Path, cache: Path, cidades: list[dict] | None = None) -> list[dict]:
    cidades = cidades or CIDADES
    chaves = {tse.chave_cidade(c["nome"]) for c in cidades}
    mun_anos, ger_anos = tse.anos_ate()
    municipais = {a: (tse.linhas("votacao", a, "MG", chaves, cache / "tse"), tse.linhas("cand", a, "MG", chaves, cache / "tse"))
                  for a in mun_anos}
    ger = {a: tse.linhas("votacao", a, "MG", chaves, cache / "tse") for a in ger_anos}
    lista = []
    for cfg in cidades:
        d = montar_cidade(cfg, municipais, ger)
        write_json(saida / "cidades" / f"{cfg['id']}.json", d)
        atual = d["executivo"][0] if d["executivo"] else None
        lista.append({"id": cfg["id"], "nome": cfg["nome"], "uf": cfg["uf"],
                      "prefeito": atual["prefeito"] if atual else None, "desde": atual["inicio"] if atual else None,
                      "vereadores": d["camara"][0]["vagas"] if d["camara"] else None})
    write_json(saida / "cidades.json", lista)
    return lista
