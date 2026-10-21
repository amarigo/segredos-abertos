"""Senado Federal: senadores em exercício, cota (CEAPS) e votações nominais do plenário.

Fontes:
- https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json
- https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/{ano}
- https://legis.senado.leg.br/dadosabertos/votacao?dataInicio=AAAA-MM-DD&dataFim=AAAA-MM-DD
"""
from __future__ import annotations

import calendar
import datetime as dt
import logging

from .camara import normaliza_voto
from .categorias import categoria_curta, grupo_de
from .util import digits, get_json, to_float

log = logging.getLogger("sa_etl.senado")

LEGIS = "https://legis.senado.leg.br/dadosabertos"
CEAPS = "https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/{ano}"


def pid(cod: str | int) -> str:
    return f"sen-{cod}"


def _as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def parse_senadores(data: dict) -> list[dict]:
    lista = data.get("ListaParlamentarEmExercicio", {}).get("Parlamentares", {}).get("Parlamentar", [])
    out = []
    for p in _as_list(lista):
        ident = p.get("IdentificacaoParlamentar", {})
        cod = ident.get("CodigoParlamentar")
        if not cod:
            continue
        bloco = ident.get("Bloco") or {}
        out.append({
            "id": pid(cod),
            "casa": "senado",
            "cargo": "Senador(a)",
            "nome": (ident.get("NomeParlamentar") or "").strip(),
            "partido": ident.get("SiglaPartidoParlamentar") or "",
            "uf": ident.get("UfParlamentar") or "",
            "foto": ident.get("UrlFotoParlamentar") or "",
            "bloco": bloco.get("NomeApelido") or bloco.get("NomeBloco") or "",
            "fonte": ident.get("UrlPaginaParlamentar") or f"https://www25.senado.leg.br/web/senadores/senador/-/perfil/{cod}",
        })
    return out


def senadores() -> list[dict]:
    out = parse_senadores(get_json(f"{LEGIS}/senador/lista/atual.json"))
    log.info("Senado: %d senadores em exercício", len(out))
    return out


def parse_ceaps(rows: list[dict], ids: set[str]) -> list[dict]:
    out = []
    for r in rows:
        p = pid(r.get("codSenador", ""))
        if p not in ids:
            continue
        valor = to_float(r.get("valorReembolsado"))
        if valor == 0:
            continue
        cat = r.get("tipoDespesa") or "Não informado"
        out.append({
            "politico": p,
            "ano": int(to_float(r.get("ano"))),
            "mes": int(to_float(r.get("mes"))),
            "data": (r.get("data") or "")[:10],
            "categoria": categoria_curta(cat),
            "grupo": grupo_de(cat),
            "fornecedor": (r.get("fornecedor") or "").strip(),
            "doc": digits(r.get("cpfCnpj")),
            "valor": round(valor, 2),
            "url": "",
        })
    return out


def despesas(anos: list[int], ids: set[str]) -> list[dict]:
    out = []
    for ano in anos:
        try:
            rows = get_json(CEAPS.format(ano=ano), timeout=300)
        except Exception as e:  # noqa: BLE001
            log.warning("CEAPS %s indisponível: %s", ano, e)
            continue
        got = parse_ceaps(rows, ids)
        log.info("Senado: %d despesas em %s", len(got), ano)
        out += got
    return out


def parse_votacoes(items: list[dict], ids: set[str]) -> tuple[list[dict], list[dict]]:
    votacoes, votos = [], []
    for v in items:
        if (v.get("votacaoSecreta") or "N") == "S":
            continue  # voto secreto: não há como saber quem votou como
        vid = f"sf-{v.get('codigoSessaoVotacao')}"
        vs = []
        for x in _as_list(v.get("votos")):
            p = pid(x.get("codigoParlamentar", ""))
            if p in ids:
                vs.append({"votacao": vid, "politico": p,
                           "voto": normaliza_voto_senado(x.get("siglaVotoParlamentar") or ""),
                           "partido": x.get("siglaPartidoParlamentar") or ""})
        if not vs:
            continue
        sigla, numero, ano = v.get("sigla") or "", v.get("numero") or "", v.get("ano") or ""
        votacoes.append({
            "id": vid,
            "casa": "senado",
            "data": (v.get("dataSessao") or "")[:10],
            "descricao": (v.get("descricaoVotacao") or "").strip(),
            "aprovada": (v.get("resultadoVotacao") or "") == "A",
            "proposicao": {
                "sigla": sigla, "numero": str(numero), "ano": str(ano),
                "ementa": (v.get("ementa") or "").strip(),
                "titulo": v.get("identificacao") or f"{sigla} {numero}/{ano}",
                "url": f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{v['codigoMateria']}" if v.get("codigoMateria") else "",
            },
            "orientacoes": {},
            "fonte": f"{LEGIS}/votacao?codigoSessaoVotacao={v.get('codigoSessaoVotacao')}",
        })
        votos += vs
    return votacoes, votos


def votacoes(anos: list[int], ids: set[str]) -> tuple[list[dict], list[dict]]:
    all_v, all_votos = [], []
    hoje = dt.date.today()
    for ano in anos:
        for mes in range(1, 13):
            ini = dt.date(ano, mes, 1)
            if ini > hoje:
                break
            fim = dt.date(ano, mes, calendar.monthrange(ano, mes)[1])
            try:
                items = get_json(f"{LEGIS}/votacao", params={"dataInicio": ini.isoformat(), "dataFim": fim.isoformat()})
            except Exception as e:  # noqa: BLE001
                log.warning("Votações do Senado %s-%02d indisponíveis: %s", ano, mes, e)
                continue
            v, vs = parse_votacoes(_as_list(items), ids)
            all_v += v
            all_votos += vs
        log.info("Senado: %d votações nominais até %s", len(all_v), ano)
    return all_v, all_votos


def normaliza_voto_senado(s: str) -> str:
    s = (s or "").strip()
    mapa = {"SIM": "Sim", "NÃO": "Não", "NAO": "Não", "ABST": "Abstenção", "ABSTENÇÃO": "Abstenção",
            "P-NRV": "Presente sem votar", "PRESIDENTE": "Presidente (art. 51)", "AP": "Ausente", "MIS": "Em missão",
            "LP": "Licença", "LS": "Licença", "NCOM": "Ausente", "REP": "Em missão"}
    return mapa.get(s.upper(), normaliza_voto(s))
