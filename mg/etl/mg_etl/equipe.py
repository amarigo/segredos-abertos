"""Quem governa Minas hoje e quanto custa: salário e viagens do governador, do vice e dos secretários de estado.

Fontes (Dados MG, o portal de dados abertos do governo de Minas, https://dados.mg.gov.br/):
- "remuneracao-servidores-ativos": um arquivo por mês com o salário de cada servidor (nome, cargo, órgão,
  remuneração bruta, descontos, líquido e jetons das estatais). Usamos o mês mais recente.
- "viagens" (SCDP, o sistema de viagens do estado): cada trecho de viagem com diárias e passagens, o cargo de quem
  viajou, o destino e o motivo. Juntamos os arquivos de dimensão (pessoa, cargo, cidade, documento).

Os arquivos são grandes (o de salários tem mais de 200 MB). Não guardamos o arquivo inteiro: lemos linha a linha,
guardamos só o resumo das pessoas que interessam e, se o site do governo falhar, usamos o último resumo.

CPF: o arquivo de salários traz o CPF mascarado e o de viagens às vezes traz o CPF dentro do nome. Nada disso
sai daqui: o nome passa por fontes.sem_cpf e o CPF nunca é lido.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import io
import json
import logging
import re
from collections import Counter, defaultdict
from pathlib import Path

from sa_etl.util import get, norm_name

from . import fontes

log = logging.getLogger("mg_etl.equipe")

CKAN = "https://dados.mg.gov.br/api/3/action/package_show?id={id}"
PACOTE_SALARIOS = "remuneracao-servidores-ativos"
PACOTE_VIAGENS = "viagens"
PAGINA_SALARIOS = "https://dados.mg.gov.br/dataset/remuneracao-servidores-ativos"
PAGINA_VIAGENS = "https://dados.mg.gov.br/dataset/viagens"
PORTAL_PESSOAL = "https://www.transparencia.mg.gov.br/estado-pessoal"
PORTAL_VIAGENS = "https://www.transparencia.mg.gov.br/despesa-estado/viagens"

# Cargos de quem comanda o governo. Adjuntos, assessores e chefes de gabinete ficam de fora.
CARGO = re.compile(r"^(GOVERNADOR DO ESTADO|VICE[ -]*GOVERNADOR( DO ESTADO)?|SECRETARI[OA] DE ESTADO( EXTRAORDINARI[OA].*)?|"
                   r"SECRETARI[OA]-GERAL|ADVOGAD[OA] GERAL DO ESTADO|CONTROLADOR(A)? GERAL DO ESTADO)$")
ORDEM = ("GOVERNADOR", "VICE", "SECRETARIO-GERAL", "SECRETARIA-GERAL")
MESES = {m: i for i, m in enumerate(["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto",
                                      "setembro", "outubro", "novembro", "dezembro"], 1)}
ESTATAIS = ("bdmg", "cemig", "codemig", "cohab", "copasa", "emater", "epamig", "funpemg", "gasmig", "mgi", "mgs",
            "prodemge", "prominas", "emip", "codemge", "emc")


def cargo_chave(c: str) -> str:
    return re.sub(r"\s+", " ", norm_name(c or "")).strip()


def eh_da_equipe(cargo: str) -> bool:
    return bool(CARGO.match(cargo_chave(cargo)))


def _recursos(pacote: str) -> list[dict]:
    try:
        return get(CKAN.format(id=pacote), timeout=60).json()["result"]["resources"]
    except Exception as e:  # noqa: BLE001
        log.warning("Dados MG %s: %s", pacote, e)
        return []


def mes_do_recurso(nome: str) -> tuple[int, int] | None:
    """'Remuneração de Agosto de 2026' -> (2026, 8)."""
    n = norm_name(nome or "").lower()
    m = re.search(r"(janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\D+(\d{4})", n)
    return (int(m.group(2)), MESES[m.group(1)]) if m else None


def _linhas_csv(raw: bytes):
    """Linhas de um CSV (talvez .gz), lidas aos poucos, com o nome das colunas sem BOM nem espaço."""
    f = io.BytesIO(raw)
    if raw[:2] == b"\x1f\x8b":
        f = gzip.GzipFile(fileobj=f)
    txt = io.TextIOWrapper(f, encoding="utf-8", errors="replace", newline="")
    primeira = txt.readline()
    sep = ";" if primeira.count(";") >= primeira.count(",") else ","
    cab = [c.strip().lstrip("﻿") for c in next(csv.reader([primeira], delimiter=sep))]
    for ln in csv.reader(txt, delimiter=sep):
        if len(ln) >= len(cab):
            yield dict(zip(cab, (x.strip() for x in ln)))


# ---------------------------------------------------------------- salários

def resumir_salarios(linhas) -> list[dict]:
    """Uma entrada por pessoa da equipe de governo: cargo, órgão, bruto, descontos, líquido e jetons."""
    out = []
    for r in linhas:
        cargo = r.get("cargo_comissao") or ""
        if not eh_da_equipe(cargo):
            continue
        v = lambda k: fontes.valor(r.get(k))  # noqa: E731
        jetons = v("jetons") + sum(v(k) for k in ESTATAIS)
        out.append({
            "nome": fontes.sem_cpf(fontes.bonito(r.get("nome") or "")), "cargo": fontes.bonito(cargo_chave(cargo)),
            "orgao": fontes.bonito(r.get("orgao_exercicio") or ""),
            "bruto": round(v("remuneracao"), 2), "abate_teto": round(v("abate_teto"), 2),
            "ferias_13": round(v("ferias") + v("decimo_terceiro"), 2), "eventual": round(v("eventual"), 2),
            "jetons": round(jetons, 2), "descontos": round(v("imposto_renda") + v("previdencia"), 2),
            "liquido": round(v("remuneracao_liquida"), 2),
        })
    out.sort(key=lambda p: (_ordem(p["cargo"]), p["orgao"], p["nome"]))
    return out


def _ordem(cargo: str) -> int:
    c = norm_name(cargo)
    for i, k in enumerate(ORDEM):
        if c.startswith(k):
            return i
    return len(ORDEM)


def salarios(cache: Path) -> dict | None:
    """Salários do mês mais recente publicado. Guarda só o resumo; o arquivo (200+ MB) é lido e descartado."""
    pasta = cache / "governo"
    recs = [(mes_do_recurso(r.get("name") or ""), r) for r in _recursos(PACOTE_SALARIOS)]
    recs = sorted(((m, r) for m, r in recs if m and r.get("url")), key=lambda x: x[0])
    antigos = sorted(pasta.glob("salarios_*.json"))
    if recs:
        (a, m), rec = recs[-1]
        alvo = pasta / f"salarios_{a}-{m:02d}.json"
        if alvo.exists():
            return json.loads(alvo.read_text(encoding="utf-8"))
        try:
            raw = get(rec["url"], timeout=900, tries=3).content
            pessoas = resumir_salarios(_linhas_csv(raw))
            del raw
            if not pessoas:
                raise ValueError("nenhum governador ou secretário no arquivo")
            d = {"mes": f"{a}-{m:02d}", "pessoas": pessoas, "fonte": PAGINA_SALARIOS, "portal": PORTAL_PESSOAL}
            pasta.mkdir(parents=True, exist_ok=True)
            alvo.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            return d
        except Exception as e:  # noqa: BLE001
            log.warning("Salários do governo: %s", e)
    if antigos:
        fontes.avisar("Salários do governo de MG: o arquivo novo não pôde ser lido; mostramos o último mês baixado")
        return json.loads(antigos[-1].read_text(encoding="utf-8"))
    fontes.avisar("Salários do governo de MG: o Dados MG não respondeu; essa parte ficou de fora")
    return None


# ---------------------------------------------------------------- viagens

ARQ_VIAGENS = {"funcao": "dm_funcao_scdp", "favorecido": "dm_favorecido_scdp", "cidade": "dm_cidade",
               "documento": "dm_documento_viagem", "trechos": "ft_diarias_scdp"}


def _arquivos_viagens() -> dict[str, str]:
    urls = {}
    for r in _recursos(PACOTE_VIAGENS):
        u = r.get("url") or ""
        for k, nome in ARQ_VIAGENS.items():
            if u.rsplit("/", 1)[-1].startswith(nome + ".") and k not in urls:
                urls[k] = u
    return urls


def resumir_viagens(funcoes, favorecidos, cidades, documentos, trechos, hoje: dt.date) -> dict[str, dict]:
    """Por pessoa (nome-chave): viagens, diárias e passagens por ano, destinos mais comuns e as últimas viagens.

    funcoes/favorecidos/cidades/documentos/trechos: linhas dos arquivos do SCDP. Os documentos são lidos só para as
    viagens da equipe (o arquivo tem mais de um milhão de linhas)."""
    ids_funcao = {r.get("id_funcao") for r in funcoes if eh_da_equipe(r.get("nome") or "")}
    nomes_cargo = {r.get("id_funcao"): fontes.bonito(cargo_chave(r.get("nome") or "")) for r in funcoes}
    sel = [t for t in trechos if t.get("id_funcao_scdp") in ids_funcao]
    pessoas_ids = {t.get("id_favorecido") for t in sel}
    nomes = {r["id_favorecido"]: fontes.sem_cpf(fontes.bonito(r.get("nome_anonimizado") or ""))
             for r in favorecidos if r.get("id_favorecido") in pessoas_ids}
    cid = {r.get("id_cidade"): fontes.bonito(r.get("nome") or "") for r in cidades}
    docs_ids = {t.get("id_documento_viagem") for t in sel}
    motivos = {r["id_documento_viagem"]: fontes.sem_cpf(r.get("motivo") or "")[:200]
               for r in documentos if r.get("id_documento_viagem") in docs_ids}
    acc: dict = defaultdict(lambda: {"nome": "", "cargos": Counter(), "anos": defaultdict(lambda: {"viagens": set(), "diarias": 0.0,
                                                                                                    "passagens": 0.0}),
                                     "destinos": Counter(), "viagens": {}})
    for t in sel:
        nome = nomes.get(t.get("id_favorecido"))
        if not nome:
            continue
        p = acc[fontes.chave_nome(nome)]
        p["nome"] = nome
        p["cargos"][nomes_cargo.get(t.get("id_funcao_scdp"), "")] += 1
        data = (t.get("dt_inicio_trecho") or "")[:10]
        try:
            ano = int(data[:4])
        except ValueError:
            continue
        doc = t.get("id_documento_viagem")
        d, ps = fontes.valor(t.get("vr_diaria")), fontes.valor(t.get("vr_passagem"))
        a = p["anos"][ano]
        a["viagens"].add(doc)
        a["diarias"] += d
        a["passagens"] += ps
        destino = cid.get(t.get("id_cidade_destino"), "")
        if destino and (d or ps):
            p["destinos"][destino] += 1
        v = p["viagens"].setdefault(doc, {"inicio": data, "fim": "", "destinos": [], "valor": 0.0, "motivo": motivos.get(doc, "")})
        v["inicio"] = min(v["inicio"], data) if v["inicio"] else data
        v["fim"] = max(v["fim"], (t.get("dt_fim_trecho") or "")[:10])
        if destino and destino not in v["destinos"]:
            v["destinos"].append(destino)
        v["valor"] += d + ps
    out = {}
    for k, p in acc.items():
        anos = [{"ano": a, "viagens": len(x["viagens"]), "diarias": round(x["diarias"], 2), "passagens": round(x["passagens"], 2)}
                for a, x in sorted(p["anos"].items(), reverse=True) if a >= hoje.year - 3]
        ultimas = sorted(p["viagens"].values(), key=lambda v: v["inicio"], reverse=True)[:12]
        out[k] = {"nome": p["nome"], "cargo": p["cargos"].most_common(1)[0][0] if p["cargos"] else "", "anos": anos,
                  "destinos": [{"nome": n, "vezes": c} for n, c in p["destinos"].most_common(6)],
                  "ultimas": [{**v, "valor": round(v["valor"], 2)} for v in ultimas]}
    return out


def viagens(cache: Path, hoje: dt.date | None = None) -> dict | None:
    """Viagens da equipe de governo (SCDP). Se o Dados MG falhar, usa o último resumo (e avisa)."""
    hoje = hoje or dt.date.today()
    alvo = cache / "governo" / "viagens.json"
    try:
        urls = _arquivos_viagens()
        falta = set(ARQ_VIAGENS) - set(urls)
        if falta:
            raise ValueError(f"arquivos do SCDP não encontrados: {sorted(falta)}")
        brutos = {k: get(u, timeout=900, tries=3).content for k, u in urls.items()}
        pessoas = resumir_viagens(list(_linhas_csv(brutos["funcao"])), _linhas_csv(brutos["favorecido"]),
                                  _linhas_csv(brutos["cidade"]), _linhas_csv(brutos["documento"]), _linhas_csv(brutos["trechos"]), hoje)
        if not pessoas:
            raise ValueError("nenhuma viagem do governador ou de secretários")
        d = {"atualizado": hoje.isoformat(), "pessoas": pessoas, "fonte": PAGINA_VIAGENS, "portal": PORTAL_VIAGENS}
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return d
    except Exception as e:  # noqa: BLE001
        log.warning("Viagens do governo: %s", e)
        if alvo.exists():
            fontes.avisar("Viagens do governo de MG: o Dados MG não respondeu; mostramos o último resumo baixado")
            return json.loads(alvo.read_text(encoding="utf-8"))
        fontes.avisar("Viagens do governo de MG: o Dados MG não respondeu; essa parte ficou de fora")
        return None


def coletar(cache: Path, hoje: dt.date | None = None) -> dict:
    """Junta salário e viagens de cada pessoa da equipe (pelo nome)."""
    sal = salarios(cache)
    via = viagens(cache, hoje)
    pessoas = []
    vistos = set()
    for p in (sal or {}).get("pessoas", []):
        k = fontes.chave_nome(p["nome"])
        vistos.add(k)
        pessoas.append({**p, "viagens": (via or {}).get("pessoas", {}).get(k)})
    # quem viajou como secretário mas não está mais no cargo no mês do salário fica de fora: a lista é de quem está lá hoje
    return {
        "mes_salarios": (sal or {}).get("mes"), "pessoas": pessoas,
        "fontes": {"salarios": PAGINA_SALARIOS, "viagens": PAGINA_VIAGENS, "portal_salarios": PORTAL_PESSOAL,
                   "portal_viagens": PORTAL_VIAGENS},
        "tem_salarios": sal is not None, "tem_viagens": via is not None,
    }
