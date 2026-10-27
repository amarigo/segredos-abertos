"""Deputados federais e senadores de MG: um recorte dos arquivos que o Segredos Abertos nacional já gerou.

Nada é coletado de novo. Lemos a pasta de dados do nacional (gerada na mesma execução do GitHub Actions) e
copiamos só o que é de MG, refazendo as somas que mudam com o recorte:

- políticos: só os eleitos por MG; a ficha de cada um é copiada como está (a posição esquerda-direita continua
  calculada com a Casa inteira, que é a régua certa);
- votações: só as em que algum político de MG votou. A lista de votos fica só com os de MG, e o placar da Casa
  inteira vai em "placar_casa", para o site mostrar quem venceu;
- empresas: só as pagas por políticos de MG, com total, notas e meses refeitos só com esses políticos;
- partidos e meta.json: refeitos a partir dos políticos de MG.

O resultado passa pela mesma conferência do nacional (sa_etl.validar), com mínimos de MG.
"""
from __future__ import annotations

import json
import logging
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from sa_etl.util import write_json

log = logging.getLogger("mg_etl.recorte")

UF = "MG"


def _ler(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def recortar(nacional: Path, saida: Path, uf: str = UF) -> dict:
    """Copia de `nacional` para `saida` só o que é dos políticos eleitos por `uf`. Devolve contagens."""
    todos = _ler(nacional / "politicos.json")
    pols = [p for p in todos if (p.get("uf") or "").upper() == uf]
    if not pols:
        raise RuntimeError(f"Nenhum político de {uf} nos dados nacionais ({len(todos)} no total)")
    ids = {p["id"] for p in pols}
    meta_nac = _ler(nacional / "meta.json")
    anos = [str(a) for a in meta_nac.get("anos", [])]

    for p in pols:
        _copiar(nacional / "p" / f"{p['id']}.json", saida / "p" / f"{p['id']}.json")
    write_json(saida / "politicos.json", pols)

    vots = _votacoes(nacional, saida, ids)
    emps = _empresas(nacional, saida, ids)
    write_json(saida / "partidos.json", partidos(pols, anos))
    write_json(saida / "meta.json", meta(meta_nac, pols, anos, len(vots), emps))
    log.info("Recorte %s: %d políticos, %d votações, %d empresas", uf, len(pols), len(vots), len(emps))
    return {"politicos": len(pols), "votacoes": len(vots), "empresas": len(emps)}


def _copiar(de: Path, para: Path) -> None:
    para.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(de, para)


def _votacoes(nacional: Path, saida: Path, ids: set[str]) -> list[dict]:
    lista = []
    for v in _ler(nacional / "votacoes.json"):
        f = nacional / "v" / f"{v['id']}.json"
        if not f.exists():
            continue
        d = _ler(f)
        meus = [x for x in d.get("votos") or [] if x.get("politico") in ids]
        if not meus:
            continue
        cont = Counter(x["voto"] for x in meus)
        por_partido = defaultdict(Counter)
        for x in meus:
            por_partido[x["partido"]][x["voto"]] += 1
        placar_casa = {"sim": d.get("sim", 0), "nao": d.get("nao", 0), "contagem": d.get("contagem") or {}}
        d.update({"votos": meus, "sim": cont.get("Sim", 0), "nao": cont.get("Não", 0), "contagem": dict(cont),
                  "por_partido_mg": {k: dict(c) for k, c in sorted(por_partido.items())}, "placar_casa": placar_casa})
        write_json(saida / "v" / f"{v['id']}.json", d)
        lista.append({**v, "sim": d["sim"], "nao": d["nao"], "placar_casa": {"sim": placar_casa["sim"], "nao": placar_casa["nao"]}})
    write_json(saida / "votacoes.json", lista)
    return lista


def _empresas(nacional: Path, saida: Path, ids: set[str]) -> list[dict]:
    lista = []
    for e in _ler(nacional / "empresas.json"):
        f = nacional / "e" / f"{e['cnpj']}.json"
        if not f.exists():
            continue
        d = _ler(f)
        pag = [x for x in d.get("pagadores") or [] if x.get("politico") in ids]
        if not pag:
            continue
        c = d["cnpj"]
        total = round(sum(x["valor"] for x in pag), 2)
        notas_por_ano, n_notas = {}, 0
        for ano in (d.get("notas_por_ano") or {}):
            fn = nacional / "e" / "notas" / f"{c}-{ano}.json"
            notas = [n for n in (_ler(fn) if fn.exists() else []) if n[1] in ids]
            if notas:
                write_json(saida / "e" / "notas" / f"{c}-{ano}.json", notas)
                notas_por_ano[ano] = len(notas)
                n_notas += len(notas)
        d.update({
            "pagadores": pag, "total": total, "n_politicos": len(pag),
            "por_mes": [x for x in d.get("por_mes") or [] if x.get("politico") in ids],
            "notas_por_ano": notas_por_ano, "n_notas": n_notas,
            # empresas vizinhas e outras do mesmo dono podem ter sido pagas só por políticos de outros estados
            "mesmo_endereco": [], "socios": [{**s, "outras_empresas": []} for s in d.get("socios") or []],
            "donos_finais": [{**x, "outras_empresas": []} for x in d.get("donos_finais") or []],
        })
        por_ano: dict[str, list] = {}
        for x in d["por_mes"]:
            v = por_ano.setdefault(str(x["ano"]), [0.0, set()])
            v[0] += x["valor"]
            v[1].add(x["politico"])
        d["por_ano"] = {a: {"valor": round(v, 2), "n_politicos": len(ps)} for a, (v, ps) in sorted(por_ano.items())}
        write_json(saida / "e" / f"{c}.json", d)
        lista.append({**e, "total": total, "n_politicos": len(pag), "n_mesmo_endereco": 0, "por_ano": d["por_ano"]})
    lista.sort(key=lambda x: -x["total"])
    write_json(saida / "empresas.json", lista)
    return lista


def partidos(pols: list[dict], anos: list[str]) -> list[dict]:
    """Mesmo formato e mesmas contas do nacional (sa_etl.build.montar), só com os políticos do recorte."""
    part = defaultdict(list)
    for r in pols:
        part[(r["casa"], r["partido"])].append(r)
    out = []
    for (casa, sigla), rs in sorted(part.items()):
        def media(k):
            xs = [r[k] for r in rs if r.get(k) is not None]
            return round(sum(xs) / len(xs), 3) if xs else None
        anos_p = {}
        for a in anos:
            com = [r["por_ano"][a] for r in rs if a in (r.get("por_ano") or {})]
            if not com:
                continue
            cota = round(sum(x["total"] for x in com), 2)
            todos = round(sum(x["custo_total"] for x in com), 2)
            anos_p[a] = {"n": len(com), "cota": cota, "cota_por_membro": round(cota / len(com), 2),
                         "custo_total": todos, "custo_por_membro": round(todos / len(com), 2)}
        out.append({"casa": casa, "sigla": sigla, "n": len(rs), "posicao": media("posicao"),
                    "alinhamento_governo": media("alinhamento_governo"), "fidelidade": media("fidelidade_partido"),
                    "total": round(sum(r["total"] for r in rs), 2), "por_ano": anos_p})
    return out


def meta(meta_nac: dict, pols: list[dict], anos: list[str], n_vot: int, emps: list[dict]) -> dict:
    medias = {}
    for a in anos:
        medias[a] = {}
        for casa in ("camara", "senado"):
            ts = [r["por_ano"][a]["total"] for r in pols if r["casa"] == casa and (r["por_ano"].get(a) or {}).get("total", 0) > 0]
            medias[a][casa] = round(sum(ts) / len(ts), 2) if ts else 0
    return {
        "atualizado_em": meta_nac.get("atualizado_em"), "anos": meta_nac.get("anos", []),
        "avisos": list(meta_nac.get("avisos") or []), "grupos": meta_nac.get("grupos"), "medias": medias,
        "contagens": {"politicos": len(pols), "votacoes": n_vot, "empresas_com_socios": sum(1 for e in emps if e.get("tem_socios"))},
        "total_gasto": round(sum(p["total"] for p in pols), 2),
        "total_por_ano": {a: round(sum((p["por_ano"].get(a) or {}).get("total", 0) for p in pols), 2) for a in anos},
        "custo_por_ano": {a: round(sum((p["por_ano"].get(a) or {}).get("custo_total", 0) for p in pols), 2) for a in anos},
    }
