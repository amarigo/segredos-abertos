"""Patrimônio declarado ao TSE por cada deputado federal e senador do site, em todas as eleições desde 2014.

Todo candidato entrega ao TSE a lista dos seus bens no registro da candidatura. O TSE publica essa lista nos dados
abertos de cada eleição (tse.py). Aqui achamos, em cada eleição, o registro de cada parlamentar do site e somamos os
bens que ele declarou, por tipo (imóveis, veículos, aplicações...). Mostramos só tipo e valor; a descrição de cada bem
fica no TSE.

Como achamos a pessoa: o TSE não usa o código da Câmara nem o do Senado. Ligamos pelo dia de nascimento e pelo nome
civil (pessoas.mesma_pessoa). Nome civil e nascimento vêm do arquivo oficial de deputados da Câmara (a API só dá um
deputado por consulta: mais de 900 pedidos; o arquivo é a mesma publicação, de uma vez) e da API do Senado
(/senador/{codigo}). Quem não liga com nenhum candidato fica sem patrimônio no site (e conta no aviso da coleta).

Valor declarado não é valor de mercado: cada um declara o valor do imposto de renda (em geral, o de compra).

Grava data/pat/{id}.json (as declarações de cada parlamentar) e data/patrimonio.json (o resumo de todos).
"""
from __future__ import annotations

import datetime as dt
import logging
from collections import defaultdict
from pathlib import Path

from . import tse
from .pessoas import data_iso, mesma_pessoa
from .util import avisar, com_copia, get_json, id_seguro, write_json

log = logging.getLogger("sa_etl.patrimonio")

ARQ_DEPUTADOS = "https://dadosabertos.camara.leg.br/arquivos/deputados/json/deputados.json"
SENADOR = "https://legis.senado.leg.br/dadosabertos/senador/{cod}.json"
GERAIS = list(range(2014, 2100, 4))
MUNICIPAIS = list(range(2016, 2100, 4))
FONTES = {
    "tse": "https://dadosabertos.tse.jus.br/dataset/?groups=candidatos",
    "api_tse": "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=candidatos-2022",
    "camara": ARQ_DEPUTADOS,
    "senado": "https://legis.senado.leg.br/dadosabertos/senador/lista/atual",
}


def anos(hoje: dt.date | None = None) -> list[int]:
    """Eleições cujo registro de candidaturas já saiu (o prazo é em agosto; os bens chegam com o registro)."""
    hoje = hoje or dt.date.today()
    return sorted(a for a in GERAIS + MUNICIPAIS if dt.date(a, 9, 1) <= hoje)


PEQUENAS = {"de", "da", "do", "das", "dos", "e", "d'"}
RESULTADO = {"ELEITO": "Eleito", "ELEITO POR QP": "Eleito por quociente partidário", "ELEITO POR MÉDIA": "Eleito por média",
             "SUPLENTE": "Suplente", "NÃO ELEITO": "Não eleito", "2º TURNO": "Foi ao 2º turno"}


def titulo(s: str) -> str:
    """'SÃO JOÃO DEL REI' -> 'São João Del Rei'; 'DEPUTADO FEDERAL' -> 'Deputado Federal'."""
    ws = (s or "").lower().split()
    return " ".join(w if i and w in PEQUENAS else "-".join(x[:1].upper() + x[1:] for x in w.split("-"))
                    for i, w in enumerate(ws))


def resultado(s: str) -> str:
    s = (s or "").strip().upper()
    return RESULTADO.get(s, "" if not s or s.startswith("#") else titulo(s))


def nascimentos_camara(cache: Path) -> dict[str, tuple[str, str]]:
    """{dep-id: (nome civil, nascimento)} de todos os deputados que já passaram pela Câmara."""
    dados = com_copia(cache / "patrimonio" / "camara-deputados.json",
                      lambda: get_json(ARQ_DEPUTADOS, timeout=180)["dados"], "Arquivo de deputados da Câmara",
                      max_horas=24 * 7)
    out = {}
    for d in dados:
        num = str(d.get("uri") or "").rsplit("/", 1)[-1]
        if num.isdigit() and d.get("dataNascimento"):
            out[f"dep-{num}"] = (d.get("nomeCivil") or d.get("nome") or "", data_iso(d["dataNascimento"]))
    return out


def nascimento_senador(cod: str, cache: Path) -> tuple[str, str] | None:
    try:
        d = com_copia(cache / "patrimonio" / f"senador-{cod}.json",
                      lambda: get_json(SENADOR.format(cod=cod), timeout=60, headers={"Accept": "application/json"}),
                      f"Senador {cod}", max_horas=24 * 30)
        p = d["DetalheParlamentar"]["Parlamentar"]
        nome = p["IdentificacaoParlamentar"].get("NomeCompletoParlamentar") or ""
        nasc = (p.get("DadosBasicosParlamentar") or {}).get("DataNascimento") or ""
        return (nome, data_iso(nasc)) if nome and nasc else None
    except Exception as e:  # noqa: BLE001
        log.warning("Patrimônio: dados do senador %s indisponíveis (%s)", cod, e)
        return None


def quem_e_quem(politicos: list[dict], cache: Path) -> dict[str, tuple[str, str]]:
    """{id do site: (nome civil, nascimento)} de cada parlamentar do site."""
    camara = nascimentos_camara(cache) if any(p["casa"] == "camara" for p in politicos) else {}
    out = {}
    for p in politicos:
        if p["casa"] == "camara" and p["id"] in camara:
            out[p["id"]] = camara[p["id"]]
        elif p["casa"] == "senado":
            x = nascimento_senador(p["id"].removeprefix("sen-"), cache)
            if x:
                out[p["id"]] = x
    return out


def declaracoes_do_ano(cands: list[dict], bens: dict[str, list], pessoas: dict[str, tuple[str, str]]) -> dict[str, list[dict]]:
    """Para cada parlamentar, os registros de candidatura dele nesta eleição, com os bens somados."""
    por_nasc: dict[str, list[str]] = defaultdict(list)
    for pid, (_, nasc) in pessoas.items():
        por_nasc[nasc].append(pid)
    achados: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))  # pid -> sq -> linhas
    for c in cands:
        for pid in por_nasc.get(c["nasc"], ()):
            if mesma_pessoa(c["nome"], c["nasc"], pessoas[pid][0], pessoas[pid][1]):
                achados[pid][c["sq"]].append(c)
    out: dict[str, list[dict]] = {}
    for pid, por_sq in achados.items():
        lista = []
        for sq, linhas in por_sq.items():
            final = max(linhas, key=lambda x: x["turno"])  # o 2º turno, se houve, diz o resultado final
            b = bens.get(sq)
            tipos = sorted(((t, v) for t, v in (b[1] if b else {}).items()), key=lambda x: -x[1])
            lista.append({
                "ano": final["ano"], "cargo": titulo(final["cargo"]), "uf": final["uf"],
                "local": titulo(final["nm_ue"]), "partido": final["partido"], "urna": final["urna"],
                "resultado": resultado(final["resultado"]), "situacao": titulo(final["situacao"]),
                "suplementar": final["tipo"] == "sup",
                "total": b[0] if b else 0.0, "sem_bens": not b,
                "tipos": [{"tipo": t, "valor": v} for t, v in tipos],
                "fonte": tse.PAGINA.format(pacote=tse.pacote(final["ano"])),
            })
        out[pid] = lista
    return out


SALTO_VEZES = 20
SALTO_MIN = 10_000_000


def marcar(ds: list[dict]) -> None:
    """Ordena e marca, em cada eleição, o registro principal (o que foi à votação; senão, o de maior valor).

    Quem trocou de cargo ou foi substituído tem dois registros no mesmo ano (por exemplo, governador e depois
    senador). E marca "salto" quando o total é 20 vezes o da eleição anterior e passa de R$ 10 milhões: em 2026,
    Simplício Araújo declarou cada bem com três zeros a mais que em 2024 (apartamento de R$ 250 mil virou
    R$ 250 milhões, conferido no arquivo do TSE em 10/11/2026). O site mostra o número oficial e avisa."""
    ds.sort(key=lambda d: (d["ano"], not d["resultado"], -d["total"]))
    anterior = None
    vistos = set()
    for d in ds:
        d["principal"] = d["ano"] not in vistos
        vistos.add(d["ano"])
        if not d["principal"]:
            continue
        if anterior and anterior["total"] > 0 and d["total"] >= SALTO_MIN and d["total"] >= SALTO_VEZES * anterior["total"]:
            d["salto"] = True
        anterior = d


def coletar(saida: Path, cache: Path, politicos: list[dict], hoje: dt.date | None = None) -> dict | None:
    hoje = hoje or dt.date.today()
    pessoas = quem_e_quem(politicos, cache)
    if not pessoas:
        avisar("Patrimônio declarado: não foi possível ler o nome civil e o nascimento dos parlamentares")
        return None
    todas: dict[str, list[dict]] = defaultdict(list)
    lidos = []
    for ano in anos(hoje):
        try:
            cands = tse.candidatos(ano, cache)
            bens = tse.bens(ano, cache)
        except Exception as e:  # noqa: BLE001
            log.warning("Patrimônio %s indisponível (%s)", ano, e)
            avisar(f"Patrimônio declarado: os dados do TSE de {ano} não puderam ser lidos; o ano ficou de fora")
            continue
        lidos.append(ano)
        for pid, ds in declaracoes_do_ano(cands, bens, pessoas).items():
            todas[pid].extend(ds)
        del cands, bens
    por_id = {p["id"]: p for p in politicos}
    resumo = []
    for pid, ds in todas.items():
        if not id_seguro(pid) or pid not in por_id:
            continue
        marcar(ds)
        p = por_id[pid]
        write_json(saida / "pat" / f"{pid}.json", {"id": pid, "nome": p["nome"], "declaracoes": ds,
                                                   "anos_lidos": lidos, "fontes": FONTES, "atualizado": hoje.isoformat()})
        prin = [d for d in ds if d["principal"]]
        ult = prin[-1]
        ant = prin[-2] if len(prin) > 1 else None
        resumo.append({"id": pid, "nome": p["nome"], "casa": p["casa"], "uf": p.get("uf", ""), "partido": p.get("partido", ""),
                       "ultimo": {"ano": ult["ano"], "total": ult["total"], "cargo": ult["cargo"]},
                       **({"anterior": {"ano": ant["ano"], "total": ant["total"]}} if ant else {}),
                       "declaracoes": len(prin), **({"salto": True} if ult.get("salto") else {})})
    sem = [p["id"] for p in politicos if p["id"] not in todas]
    if sem:
        log.info("Patrimônio: %d parlamentares sem registro de candidatura achado no TSE (ex.: %s)", len(sem), sem[:5])
    resumo.sort(key=lambda x: -x["ultimo"]["total"])
    out = {"atualizado": hoje.isoformat(), "anos": lidos, "fontes": FONTES, "politicos": resumo,
           "sem_registro": len(sem), "total_politicos": len(politicos)}
    write_json(saida / "patrimonio.json", out)
    log.info("Patrimônio declarado: %d de %d parlamentares ligados ao TSE", len(resumo), len(politicos))
    return out
