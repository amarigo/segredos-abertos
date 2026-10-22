"""Senado Federal: senadores em exercício, cota (CEAPS) e votações nominais do plenário.

Fontes:
- https://legis.senado.leg.br/dadosabertos/senador/lista/atual.json
- https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/{ano}
- https://legis.senado.leg.br/dadosabertos/votacao?dataInicio=AAAA-MM-DD&dataFim=AAAA-MM-DD
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
import logging
from pathlib import Path

from .camara import normaliza_voto
from .categorias import categoria_curta, grupo_de
from .util import avisar, digits, get_json, norm_name, to_float, url_segura

log = logging.getLogger("sa_etl.senado")

LEGIS = "https://legis.senado.leg.br/dadosabertos"
CEAPS = "https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/{ano}"

# O Senado não publica a orientação do governo em cada votação. Usamos o voto do líder do
# governo no Senado como referência. Atualize o nome se o líder mudar.
LIDER_GOVERNO_SENADO = "Jaques Wagner"


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
        cod = str(ident.get("CodigoParlamentar") or "").strip()
        if not cod.isdigit():
            continue
        bloco = ident.get("Bloco") or {}
        out.append({
            "id": pid(cod),
            "casa": "senado",
            "cargo": "Senador(a)",
            "nome": (ident.get("NomeParlamentar") or "").strip(),
            "partido": ident.get("SiglaPartidoParlamentar") or "",
            "uf": ident.get("UfParlamentar") or "",
            "foto": url_segura(ident.get("UrlFotoParlamentar")),
            "bloco": bloco.get("NomeBloco") or bloco.get("NomeApelido") or "",
            "fonte": url_segura(ident.get("UrlPaginaParlamentar")) or f"https://www25.senado.leg.br/web/senadores/senador/-/perfil/{cod}",
        })
    return out


def senadores() -> list[dict]:
    out = parse_senadores(get_json(f"{LEGIS}/senador/lista/atual.json"))
    log.info("Senado: %d senadores em exercício", len(out))
    return out


LISTA_CEAPS = "https://www6g.senado.leg.br/transparencia/sen/{cod}/ceaps/{n}/?ano={ano}#conteudo_transparencia"
SENADOR_ANO = "https://www6g.senado.leg.br/transparencia/sen/{cod}/?ano={ano}"
# Número de cada tipo de despesa nas páginas de transparência do Senado (sen/{cod}/ceaps/{n}/)
TIPOS_CEAPS = [("aluguel", 1), ("material de consumo", 2), ("locomoc", 3), ("consultoria", 4), ("servicos de apoio", 4),
               ("divulgac", 5), ("passage", 8), ("seguranca", 9)]


def link_lista(cod, tipo: str, ano) -> str:
    """O Senado não publica a imagem das notas. O link leva à lista oficial do senador, por tipo de despesa e ano."""
    t = norm_name(tipo).lower()
    n = next((n for chave, n in TIPOS_CEAPS if chave in t), None)
    return LISTA_CEAPS.format(cod=cod, n=n, ano=ano) if n else SENADOR_ANO.format(cod=cod, ano=ano)


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
            "url": link_lista(r.get("codSenador"), cat, int(to_float(r.get("ano")))),
            "link": "lista",
            "detalhe": " · ".join(x for x in (
                f"{r['tipoDocumento']} nº {r['documento']}" if r.get("documento") and r.get("tipoDocumento") else
                f"Documento nº {r['documento']}" if r.get("documento") else "",
                (r.get("detalhamento") or "").strip()) if x),
        })
    return out


def _ler_cache(f: Path | None):
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f and f.exists() else None
    except ValueError:
        return None


def _recente(f: Path | None, dias: float) -> bool:
    import time
    return bool(f and f.exists() and time.time() - f.stat().st_mtime < dias * 86400)


def _gravar_cache(f: Path | None, dados) -> None:
    if f is None:
        return
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".part")
    tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def despesas(anos: list[int], ids: set[str], cache: Path | None = None) -> list[dict]:
    """Cota dos senadores. A API do Senado cai com frequência: se falhar, usa a última resposta boa guardada."""
    out = []
    for ano in anos:
        f = cache / f"senado-ceaps-{ano}.json" if cache else None
        try:
            rows = get_json(CEAPS.format(ano=ano), timeout=300)
            if not isinstance(rows, list):
                raise ValueError(f"resposta inesperada ({type(rows).__name__})")
            if not rows and _ler_cache(f):
                raise ValueError("resposta vazia para um ano que tinha despesas")
            _gravar_cache(f, rows)
        except Exception as e:  # noqa: BLE001
            rows = _ler_cache(f)
            if rows is None:
                log.warning("CEAPS %s indisponível: %s", ano, e)
                avisar(f"Cota do Senado {ano}: a API oficial não respondeu; as despesas de senadores neste ano estão faltando")
                continue
            log.warning("CEAPS %s indisponível (%s); usando a última cópia", ano, e)
            avisar(f"Cota do Senado {ano}: a API oficial não respondeu; usamos a última cópia baixada")
        got = parse_ceaps(rows, ids)
        log.info("Senado: %d despesas em %s", len(got), ano)
        out += got
    return out


def parse_votacoes(items: list[dict], ids: set[str]) -> tuple[list[dict], list[dict]]:
    votacoes, votos = [], []
    vistas = set()
    for v in items:
        if not isinstance(v, dict) or (v.get("votacaoSecreta") or "N") == "S":
            continue  # voto secreto: não há como saber quem votou como
        cod = str(v.get("codigoSessaoVotacao") or "").strip()
        if not cod.isdigit() or cod in vistas:
            continue  # sem código, ou a mesma votação repetida na resposta
        vistas.add(cod)
        vid = f"sf-{cod}"
        vs, ja = [], set()
        orient = {}
        for x in _as_list(v.get("votos")):
            if (x.get("nomeParlamentar") or "").strip().lower() == LIDER_GOVERNO_SENADO.lower():
                o = normaliza_voto_senado(x.get("siglaVotoParlamentar") or "")
                if o in ("Sim", "Não"):
                    orient["Governo (voto do líder)"] = o
            p = pid(x.get("codigoParlamentar", ""))
            if p in ids and p not in ja:
                ja.add(p)
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
            "orientacoes": orient,
            "fonte": f"{LEGIS}/votacao?codigoSessaoVotacao={v.get('codigoSessaoVotacao')}",
        })
        votos += vs
    return votacoes, votos


def votacoes(anos: list[int], ids: set[str], cache: Path | None = None) -> tuple[list[dict], list[dict]]:
    """Votações do Senado, mês a mês. A API às vezes falha num mês: cada mês bom fica guardado no cache;
    meses com mais de 60 dias não mudam mais e são lidos do cache. Um mês que falhou e não tem cópia vira aviso."""
    all_v, all_votos, faltando = [], [], []
    hoje = dt.date.today()
    for ano in anos:
        for mes in range(1, 13):
            ini = dt.date(ano, mes, 1)
            if ini > hoje:
                break
            fim = dt.date(ano, mes, calendar.monthrange(ano, mes)[1])
            f = cache / f"senado-votacao-{ano}-{mes:02d}.json" if cache else None
            items = _ler_cache(f) if (hoje - fim).days > 60 and _recente(f, dias=30) else None
            if not items:  # resposta vazia guardada pode ter sido a API instável: pergunta de novo
                try:
                    items = get_json(f"{LEGIS}/votacao", params={"dataInicio": ini.isoformat(), "dataFim": fim.isoformat()})
                    if not isinstance(items, (list, dict)):
                        raise ValueError(f"resposta inesperada ({type(items).__name__})")
                    if not _as_list(items) and _ler_cache(f):
                        raise ValueError("resposta vazia para um mês que tinha votações")
                    _gravar_cache(f, items)
                except Exception as e:  # noqa: BLE001
                    items = _ler_cache(f)
                    if items is None:
                        log.warning("Votações do Senado %s-%02d indisponíveis: %s", ano, mes, e)
                        faltando.append(f"{mes:02d}/{ano}")
                        continue
                    log.warning("Votações do Senado %s-%02d indisponíveis (%s); usando a última cópia", ano, mes, e)
            v, vs = parse_votacoes(_as_list(items), ids)
            all_v += v
            all_votos += vs
        log.info("Senado: %d votações nominais até %s", len(all_v), ano)
    if faltando:
        avisar(f"Votações do Senado: a API oficial não respondeu para {', '.join(faltando)}; as votações desses meses estão faltando")
    return all_v, all_votos


def normaliza_voto_senado(s: str) -> str:
    s = (s or "").strip()
    mapa = {"SIM": "Sim", "NÃO": "Não", "NAO": "Não", "ABST": "Abstenção", "ABSTENÇÃO": "Abstenção",
            "P-NRV": "Presente sem votar", "PRESIDENTE": "Presidente (art. 51)", "AP": "Em atividade parlamentar",
            "MIS": "Em missão", "LP": "Licença", "LS": "Licença", "LAP": "Licença", "LG": "Licença", "LC": "Licença",
            "NCOM": "Ausente", "REP": "Em missão"}
    return mapa.get(s.upper(), normaliza_voto(s))
