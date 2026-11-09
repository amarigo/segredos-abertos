"""Mapa de Minas Gerais para mostrar as cidades visitadas nas viagens do governo.

Fonte: API de malhas e de localidades do IBGE (oficial, https://servicodados.ibge.gov.br/api/docs/):
- /api/v3/malhas/estados/31: o contorno do estado (qualidade mínima, para ficar leve no site);
- /api/v3/malhas/estados/31?intrarregiao=municipio: o contorno de cada cidade, de onde tiramos o ponto central;
- /api/v1/localidades/estados/31/municipios: o nome oficial (com acento) de cada código do IBGE.

O site recebe só o desenho do contorno (estado/mapa-mg.json). O ponto de cada cidade fica aqui e entra no arquivo
de viagens de cada pessoa, só para as cidades que ela visitou. A divisão das cidades quase nunca muda: se o IBGE
falhar, usamos a última cópia baixada.
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path

from sa_etl.util import get_json

from . import fontes

log = logging.getLogger("mg_etl.mapa_mg")

IBGE = "https://servicodados.ibge.gov.br/api"
CONTORNO = f"{IBGE}/v3/malhas/estados/31?formato=application/vnd.geo%2Bjson&qualidade=minima"
MALHA_CIDADES = f"{IBGE}/v3/malhas/estados/31?formato=application/vnd.geo%2Bjson&qualidade=minima&intrarregiao=municipio"
NOMES = f"{IBGE}/v1/localidades/estados/31/municipios"
PAGINA = "https://servicodados.ibge.gov.br/api/docs/malhas?versao=3"

LARGURA = 600  # largura do desenho no site (o SVG se ajusta à tela)


def _aneis(geom: dict) -> list[list[list[float]]]:
    """Anéis externos de um Polygon ou MultiPolygon do GeoJSON."""
    if geom.get("type") == "Polygon":
        return [geom["coordinates"][0]]
    if geom.get("type") == "MultiPolygon":
        return [p[0] for p in geom["coordinates"]]
    return []


class Projecao:
    """Longitude/latitude -> x/y do desenho. Projeção simples (equiretangular corrigida pela latitude do meio):
    para um estado do tamanho de Minas a deformação é pequena."""

    def __init__(self, aneis):
        lons = [p[0] for a in aneis for p in a]
        lats = [p[1] for a in aneis for p in a]
        self.lon0, self.lat1 = min(lons), max(lats)
        self.k = math.cos(math.radians((min(lats) + max(lats)) / 2))
        self.esc = LARGURA / ((max(lons) - self.lon0) * self.k)
        self.altura = (self.lat1 - min(lats)) * self.esc

    def xy(self, lon: float, lat: float) -> tuple[float, float]:
        return round((lon - self.lon0) * self.k * self.esc, 1), round((self.lat1 - lat) * self.esc, 1)


def _centro(anel, proj: Projecao) -> tuple[float, float]:
    """Centro de área de um anel (fórmula do polígono), já no desenho."""
    pts = [proj.xy(*p[:2]) for p in anel]
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        c = x0 * y1 - x1 * y0
        a += c
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    if abs(a) < 1e-9:
        return pts[0]
    return round(cx / (3 * a), 1), round(cy / (3 * a), 1)


def _area(anel) -> float:
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0, *_), (x1, y1, *_) in zip(anel, anel[1:] + anel[:1]))) / 2


def montar(contorno: dict, malha: dict, nomes: list[dict]) -> dict:
    """{"vb", "contorno" (caminho SVG), "cidades": {chave do nome: [x, y, nome oficial]}}."""
    aneis = [a for f in contorno.get("features") or [] for a in _aneis(f.get("geometry") or {})]
    if not aneis:
        raise ValueError("contorno de MG vazio")
    proj = Projecao(aneis)
    caminho = " ".join("M" + " ".join("%g,%g" % proj.xy(*p[:2]) for p in a) + "Z" for a in aneis)
    nome_cod = {str(n["id"]): n["nome"] for n in nomes}
    cidades = {}
    for f in malha.get("features") or []:
        cod = str((f.get("properties") or {}).get("codarea") or "")
        nome = nome_cod.get(cod)
        partes = _aneis(f.get("geometry") or {})
        if not nome or not partes:
            continue
        x, y = _centro(max(partes, key=_area), proj)
        cidades[fontes.chave_nome(nome)] = [x, y, nome]
    if len(cidades) < 800:  # Minas tem 853 cidades
        raise ValueError(f"só {len(cidades)} cidades no mapa do IBGE")
    return {"vb": f"0 0 {LARGURA} {math.ceil(proj.altura)}", "contorno": caminho, "cidades": cidades,
            "fonte": PAGINA}


def coletar(cache: Path) -> dict | None:
    alvo = cache / "governo" / "mapa-mg.json"
    try:
        d = montar(get_json(CONTORNO, timeout=120), get_json(MALHA_CIDADES, timeout=300), get_json(NOMES, timeout=120))
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return d
    except Exception as e:  # noqa: BLE001
        log.warning("Mapa de MG (IBGE): %s", e)
        if alvo.exists():
            return json.loads(alvo.read_text(encoding="utf-8"))
        fontes.avisar("Mapa de MG: a API de malhas do IBGE não respondeu; as viagens aparecem sem o mapa")
        return None
