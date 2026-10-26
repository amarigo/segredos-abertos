"""Emendas parlamentares: para onde foi o dinheiro, quem mandou mais e para quê.

Fonte: Portal da Transparência (CGU), arquivo completo de emendas, atualizado todo dia:
    https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares/UNICO

O arquivo .zip traz três tabelas. Usamos duas:
- EmendasParlamentares.csv: uma linha por emenda (autor, tipo, local, área do governo e valores)
- EmendasParlamentares_PorFavorecido.csv: quem recebeu o dinheiro (prefeituras, estados, entidades, empresas)

Os nomes de coluna são achados por palavras-chave, para o coletor não quebrar se a CGU mudar um acento.
"""
from __future__ import annotations

import csv
import io
import logging
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from .util import _session, avisar, data_do_arquivo, digits, get_json, norm_name, to_float, write_json

log = logging.getLogger("sa_etl.emendas")

URLS = [
    "https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares/UNICO",
    "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/emendas-parlamentares/EmendasParlamentares.zip",
]
FONTE = "https://portaldatransparencia.gov.br/emendas"
CAMARA_API = "https://dadosabertos.camara.leg.br/api/v2/deputados"

UFS = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAZONAS": "AM", "BAHIA": "BA", "CEARA": "CE", "DISTRITO FEDERAL": "DF",
    "ESPIRITO SANTO": "ES", "GOIAS": "GO", "MARANHAO": "MA", "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS",
    "MINAS GERAIS": "MG", "PARA": "PA", "PARAIBA": "PB", "PARANA": "PR", "PERNAMBUCO": "PE", "PIAUI": "PI",
    "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN", "RIO GRANDE DO SUL": "RS", "RONDONIA": "RO", "RORAIMA": "RR",
    "SANTA CATARINA": "SC", "SAO PAULO": "SP", "SERGIPE": "SE", "TOCANTINS": "TO",
}
SIGLAS = set(UFS.values())
SEM_AREA_PIX = "Sem finalidade definida (emenda Pix)"


# ---------------------------------------------------------------- download e leitura

PASTA_CACHE = "emendas"  # dentro do cache da coleta nacional (o Minas Nossa lê o .zip daqui)
ARQUIVO_ZIP = "EmendasParlamentares.zip"


def zip_no_cache(cache_raiz: Path) -> Path:
    """Onde a coleta nacional guarda o .zip, a partir da pasta raiz do cache (etl/.cache)."""
    return cache_raiz / PASTA_CACHE / ARQUIVO_ZIP


def baixar(cache: Path, max_horas: float = 20) -> Path | None:
    """Baixa o .zip para o cache. Se o Portal estiver fora do ar, usa a última cópia que tiver."""
    import time
    dest = cache / ARQUIVO_ZIP
    if dest.exists() and dest.stat().st_size > 0 and (time.time() - dest.stat().st_mtime) / 3600 < max_horas:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    agentes = [_session.headers["User-Agent"],
               "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"]
    for url in URLS:
        for ua in agentes:
            for tentativa in range(3):
                try:
                    r = _session.get(url, timeout=900, stream=True, allow_redirects=True,
                                     headers={"Accept": "application/zip,application/octet-stream,*/*", "User-Agent": ua})
                    if r.status_code != 200:
                        log.warning("Emendas: %s respondeu %s", url, r.status_code)
                        break
                    tmp = dest.with_suffix(".part")
                    with tmp.open("wb") as f:
                        for bloco in r.iter_content(1 << 20):
                            f.write(bloco)
                    if not zipfile.is_zipfile(tmp):
                        log.warning("Emendas: %s não devolveu um .zip (%s)", url, r.headers.get("content-type"))
                        tmp.unlink(missing_ok=True)
                        break
                    tmp.rename(dest)
                    log.info("Emendas: baixado %s (%.1f MB)", r.url, dest.stat().st_size / 1e6)
                    return dest
                except Exception as e:  # noqa: BLE001
                    log.warning("Emendas: falha em %s (%s); tentativa %d", url, e, tentativa + 1)
                    time.sleep(2 ** (tentativa + 1))
    if dest.exists():
        log.warning("Emendas: usando a cópia antiga do cache")
        avisar(f"Emendas: o Portal da Transparência não respondeu; usamos a última cópia baixada, de {data_do_arquivo(dest)}")
        return dest
    log.error("Emendas: não foi possível baixar o arquivo do Portal da Transparência")
    avisar("Emendas: o Portal da Transparência não respondeu; a página de emendas não foi atualizada")
    return None


def _encoding(z: zipfile.ZipFile, nome: str) -> str:
    with z.open(nome) as f:
        amostra = f.read(4 << 20)
    try:
        amostra.decode("utf-8")
        return "utf-8-sig"
    except UnicodeDecodeError as e:
        # pode ter cortado um caractere no fim da amostra
        if e.start >= len(amostra) - 4:
            return "utf-8-sig"
        return "latin-1"


def linhas(zip_path: Path, parte: str):
    """Lê uma tabela do .zip sem carregar tudo na memória. parte: '' (principal) ou 'favorecido'."""
    with zipfile.ZipFile(zip_path) as z:
        csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if parte:
            nomes = [n for n in csvs if parte in norm_name(n).lower()]
        else:
            nomes = [n for n in csvs if "favorecido" not in n.lower() and "convenio" not in norm_name(n).lower()]
        if not nomes:
            log.warning("Emendas: tabela '%s' não encontrada no .zip (%s)", parte or "principal", csvs)
            return
        nome = nomes[0]
        enc = _encoding(z, nome)
        with z.open(nome) as f:
            texto = io.TextIOWrapper(f, encoding=enc, errors="replace", newline="")
            leitor = csv.DictReader(texto, delimiter=";")
            log.info("Emendas: %s (%s) colunas: %s", nome, enc, leitor.fieldnames)
            yield from leitor


def _chave(nome: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", norm_name(nome).lower()).strip()


def achar_colunas(campos: list[str], regras: dict[str, list[list[str]]]) -> dict[str, str | None]:
    """Para cada campo desejado, a coluna que tem todas as palavras de uma regra (a mais curta, se houver várias).
    Colunas de código ('Código ...') só valem quando a regra pede 'codigo'."""
    norm = {c: _chave(c).split() for c in campos or []}
    out = {}
    for alvo, opcoes in regras.items():
        achada = None
        for palavras in opcoes:
            cands = [c for c, ws in norm.items() if all(p in ws for p in palavras)
                     and (ws[:1] != ["codigo"] or palavras[0] == "codigo")]
            if cands:
                achada = min(cands, key=lambda c: len(norm[c]))
                break
        out[alvo] = achada
    return out


REGRAS = {
    "codigo": [["codigo", "emenda"]],
    "ano": [["ano", "emenda"], ["ano"]],
    "tipo": [["tipo", "emenda"]],
    "autor": [["nome", "autor"], ["autor"]],
    "local": [["localidade"]],
    "municipio": [["municipio"]],
    "uf": [["uf"]],
    "funcao": [["nome", "funcao"], ["funcao"]],
    "subfuncao": [["nome", "subfuncao"], ["subfuncao"]],
    "acao": [["nome", "acao"]],
    "empenhado": [["valor", "empenhado"]],
    "liquidado": [["valor", "liquidado"]],
    "pago": [["valor", "pago"]],
    "rap_pago": [["restos", "pagos"], ["restos", "pago"]],
}
REGRAS_FAV = {
    "codigo": [["codigo", "emenda"]],
    "autor": [["nome", "autor"], ["autor"]],
    "tipo_emenda": [["tipo", "emenda"]],
    "anomes": [["ano", "mes"]],
    "doc": [["codigo", "favorecido"]],
    "nome": [["favorecido"]],
    "natureza": [["natureza"]],
    "tipo": [["tipo", "favorecido"]],
    "uf": [["uf", "favorecido"], ["uf"]],
    "municipio": [["municipio", "favorecido"], ["municipio"]],
    "valor": [["valor", "recebido"], ["valor"]],
}


# ---------------------------------------------------------------- classificação

def tipo_curto(tipo: str) -> str:
    t = _chave(tipo)
    if "especia" in t:
        return "pix"
    if "individual" in t:
        return "individual"
    if "bancada" in t:
        return "bancada"
    if "comiss" in t:
        return "comissao"
    if "relator" in t:
        return "relator"
    return "outro"


TIPOS = {
    "individual": "Individual, com finalidade definida",
    "pix": "Individual, transferência especial (emenda Pix)",
    "bancada": "De bancada (deputados e senadores de um estado)",
    "comissao": "De comissão",
    "relator": "Do relator do Orçamento",
    "outro": "Outras",
}


def autor_coletivo(autor: str, tipo: str) -> str | None:
    """Emendas que não são de uma pessoa só: bancadas, comissões e relator."""
    a = _chave(autor)
    if tipo in ("bancada", "comissao", "relator") or a.startswith(("bancada", "comissao", "relator", "com ")):
        return tipo if tipo in ("bancada", "comissao", "relator") else ("bancada" if a.startswith("bancada") else
                                                                         "relator" if a.startswith("relator") else "comissao")
    return None


def bonito(nome: str) -> str:
    """CAIXA ALTA → Nome Próprio, mantendo de/da/do minúsculos."""
    if not nome or not nome.isupper():
        return nome
    pequenas = {"de", "da", "do", "das", "dos", "e"}
    return " ".join(p.lower() if p.lower() in pequenas and i else p.capitalize() for i, p in enumerate(nome.lower().split()))


# ---------------------------------------------------------------- autores → parlamentares

SENADO_LEG = "https://legis.senado.leg.br/dadosabertos/senador/lista/legislatura/{leg}.json"


def deputados_legislatura(leg: int = 57) -> list[dict]:
    """Todos que foram deputados na legislatura (inclui quem saiu), com o último partido. Só para achar o partido do autor."""
    out, url, params = [], CAMARA_API, {"idLegislatura": leg, "itens": 100, "ordem": "ASC", "ordenarPor": "nome"}
    try:
        while url:
            data = get_json(url, params=params)
            for d in data.get("dados", []):
                out.append({"nome": d.get("nome", ""), "partido": d.get("siglaPartido") or "", "uf": d.get("siglaUf") or "",
                            "casa": "camara"})
            url = next((l["href"] for l in data.get("links", []) if l.get("rel") == "next"), None)
            params = None
    except Exception as e:  # noqa: BLE001
        log.warning("Emendas: não foi possível listar os deputados da legislatura %d (%s)", leg, e)
    return out


def senadores_legislatura(leg: int = 57) -> list[dict]:
    """Senadores da legislatura, inclusive licenciados e suplentes que já saíram."""
    ps = None
    for tentativa in range(3):
        try:
            d = get_json(SENADO_LEG.format(leg=leg))
            ps = d.get("ListaParlamentarLegislatura", {}).get("Parlamentares", {}).get("Parlamentar", [])
            break
        except Exception as e:  # noqa: BLE001
            log.warning("Emendas: não foi possível listar os senadores da legislatura %d (%s)", leg, e)
    if not ps:
        return []
    out = []
    for p in ps if isinstance(ps, list) else [ps]:
        i = p.get("IdentificacaoParlamentar") or {}
        if i.get("NomeParlamentar"):
            out.append({"nome": i["NomeParlamentar"], "partido": i.get("SiglaPartidoParlamentar") or "",
                        "uf": i.get("UfParlamentar") or "", "casa": "senado"})
    return out


def indice_nomes(politicos: list[dict], extras: list[dict]) -> dict[str, dict]:
    """Nome normalizado → parlamentar. Os atuais têm prioridade; nomes repetidos (ambíguos) ficam de fora."""
    idx: dict[str, dict] = {}
    ambiguos: set[str] = set()
    for grupo in (politicos, extras):
        vistos: dict[str, dict] = {}
        for p in grupo:
            k = _chave(p["nome"])
            if not k:
                continue
            # mesmo nome com partidos diferentes: pode ser outra pessoa, então não arriscamos
            if k in vistos and vistos[k].get("id") != p.get("id") and \
                    (vistos[k].get("id") or (vistos[k].get("partido") and p.get("partido") and vistos[k]["partido"] != p["partido"])):
                ambiguos.add(k)
            if k not in vistos or (not vistos[k].get("partido") and p.get("partido")):
                vistos[k] = p
        for k, p in vistos.items():
            if k in idx:
                ambiguos.discard(k)  # o parlamentar atual resolve a dúvida
            idx.setdefault(k, p)
    for k in ambiguos:
        idx.pop(k, None)
    return idx


SUBSTITUTO = re.compile(r"^(.+?)\s*\(\s*ex-parlamentar\s+(.+?)\s*(,.*)?\)\s*$", re.I)


def nome_autor(autor: str) -> tuple[str, str]:
    """(nome para procurar o partido, nome para mostrar). Emendas herdadas trazem 'NOVO (ex-parlamentar ANTIGO, nos termos...)'."""
    m = SUBSTITUTO.match(autor or "")
    if m:
        return m.group(1), f"{bonito(m.group(1))} (no lugar de {bonito(m.group(2))})"
    return autor, bonito(autor)


# ---------------------------------------------------------------- resumo

def _top(d: dict, n: int) -> list:
    return [[k, round(v, 2)] for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:n] if v]


def resumir(rows, anos: list[int], politicos: list[dict], extras: list[dict] | None = None) -> dict[int, dict]:
    """Soma as emendas pelo ano do Orçamento: tipo, área, autor e partido."""
    idx = indice_nomes(politicos, extras or [])
    anos_set = set(anos)
    col = None
    soma = {a: {"tipo": defaultdict(lambda: [0.0, 0.0, 0]), "area": defaultdict(lambda: [0.0, 0.0]),
                "autor": {}, "total": [0.0, 0.0, 0]} for a in anos}
    for r in rows:
        if col is None:
            col = achar_colunas(list(r.keys()), REGRAS)
            log.info("Emendas: colunas usadas %s", col)
            if not col["autor"] or not col["ano"] or not (col["pago"] or col["empenhado"]):
                log.error("Emendas: colunas essenciais não encontradas")
                return {}
        try:
            ano = int(to_float(r.get(col["ano"])))
        except (TypeError, ValueError):
            continue
        if ano not in anos_set:
            continue
        emp = to_float(r.get(col["empenhado"])) if col["empenhado"] else 0.0
        pago = (to_float(r.get(col["pago"])) if col["pago"] else 0.0) + (to_float(r.get(col["rap_pago"])) if col["rap_pago"] else 0.0)
        if not emp and not pago:
            continue
        s = soma[ano]
        tipo = tipo_curto(r.get(col["tipo"]) or "") if col["tipo"] else "outro"
        autor = (r.get(col["autor"]) or "").strip() or "Sem autor informado"
        area = (r.get(col["funcao"]) or "").strip() if col["funcao"] else ""
        # Na emenda Pix o dinheiro vai direto para o caixa da prefeitura ou do estado, sem área definida
        area = SEM_AREA_PIX if tipo == "pix" else (bonito(area) or "Não informada")
        cod = (r.get(col["codigo"]) or "").strip() if col["codigo"] else ""

        s["total"][0] += emp; s["total"][1] += pago; s["total"][2] += 1
        t = s["tipo"][tipo]; t[0] += emp; t[1] += pago; t[2] += 1
        a = s["area"][area]; a[0] += emp; a[1] += pago
        au = s["autor"].setdefault(autor, {"emp": 0.0, "pago": 0.0, "n": set(), "tipos": Counter(), "area": defaultdict(float),
                                                  "acao": defaultdict(float), "pix_cod": {}})
        au["emp"] += emp; au["pago"] += pago; au["tipos"][tipo] += pago or emp
        au["n"].add(cod if cod and cod.isdigit() else len(au["n"]))
        au["area"][area] += pago or emp
        acao = bonito((r.get(col["acao"]) or "").strip()) if col.get("acao") else ""
        if acao and tipo != "pix":  # na Pix a ação é só "Transferências Especiais"
            au["acao"][acao] += pago or emp
        if tipo == "pix" and cod:  # cada emenda Pix, para a pessoa abrir o plano de ação dela
            local = (r.get(col["local"]) or "").strip() if col["local"] else ""
            local = re.sub(r"- (\w\w)$", lambda m: "- " + m.group(1).upper(), bonito(local))
            x = au["pix_cod"].setdefault(cod, [local, 0.0])
            x[1] += pago or emp

    out = {}
    for ano, s in soma.items():
        if not s["total"][2]:
            continue
        autores, coletivos = [], []
        for nome, au in s["autor"].items():
            coletivo = autor_coletivo(nome, au["tipos"].most_common(1)[0][0] if au["tipos"] else "outro")
            busca, mostra = nome_autor(nome)
            p = None if coletivo else idx.get(_chave(busca))
            item = {"nome": mostra if (not p or busca != nome) else p["nome"], "chave": _chave(nome),
                    "empenhado": round(au["emp"], 2), "pago": round(au["pago"], 2), "n": len(au["n"]),
                    "areas": _top(au["area"], 4), "acoes": _top(au["acao"], 5),
                    "pix_emendas": [[c, l, round(v, 2)] for c, (l, v) in sorted(au["pix_cod"].items(), key=lambda kv: -kv[1][1])[:30] if v],
                    "pix": round(au["tipos"].get("pix", 0), 2)}
            if coletivo:
                coletivos.append({**item, "tipo": coletivo})
            else:
                item.update({"politico": (p or {}).get("id"), "partido": (p or {}).get("partido", ""), "uf": (p or {}).get("uf", ""),
                             "casa": (p or {}).get("casa", "")})
                autores.append(item)
        autores.sort(key=lambda x: -(x["pago"] or x["empenhado"]))
        coletivos.sort(key=lambda x: -(x["pago"] or x["empenhado"]))
        partidos = defaultdict(lambda: {"n": 0, "empenhado": 0.0, "pago": 0.0, "pix": 0.0, "area": defaultdict(float),
                                        "camara": 0, "senado": 0})
        for a in autores:
            if not a["partido"]:
                continue
            p = partidos[a["partido"]]
            p["n"] += 1; p["empenhado"] += a["empenhado"]; p["pago"] += a["pago"]; p["pix"] += a["pix"]
            p[a["casa"] or "camara"] += 1
            for area, v in a["areas"]:
                p["area"][area] += v
        sem_partido = [a for a in autores if not a["partido"]]
        out[ano] = {
            "ano": ano, "fonte": FONTE,
            "total": {"empenhado": round(s["total"][0], 2), "pago": round(s["total"][1], 2), "n": s["total"][2]},
            "por_tipo": sorted(({"tipo": k, "rotulo": TIPOS[k], "empenhado": round(v[0], 2), "pago": round(v[1], 2), "n": v[2]}
                                for k, v in s["tipo"].items()), key=lambda x: -x["empenhado"]),
            "por_area": sorted(({"area": k, "empenhado": round(v[0], 2), "pago": round(v[1], 2)} for k, v in s["area"].items()),
                               key=lambda x: -x["empenhado"]),
            "autores": autores,
            "coletivos": coletivos[:200],
            "partidos": sorted(({"sigla": k, "n": v["n"], "camara": v["camara"], "senado": v["senado"],
                                 "empenhado": round(v["empenhado"], 2), "pago": round(v["pago"], 2), "pix": round(v["pix"], 2),
                                 "areas": _top(v["area"], 5)} for k, v in partidos.items()), key=lambda x: -x["empenhado"]),
            "sem_partido": {"n": len(sem_partido), "empenhado": round(sum(a["empenhado"] for a in sem_partido), 2),
                            "pago": round(sum(a["pago"] for a in sem_partido), 2), "nomes": [a["nome"] for a in sem_partido][:40]},
        }
        log.info("Emendas %d: %d linhas, R$ %.0f empenhados, R$ %.0f pagos, %d autores (%d sem partido identificado)",
                 ano, s["total"][2], s["total"][0], s["total"][1], len(autores), len(sem_partido))
    return out


# ---------------------------------------------------------------- quem recebeu

CATEGORIAS = {
    "prefeitura": "Prefeituras e fundos municipais",
    "estado": "Governos estaduais e fundos estaduais",
    "entidade": "Entidades sem fins lucrativos",
    "empresa": "Empresas",
    "federal": "Órgãos federais e bancos públicos",
    "pessoa": "Pessoas físicas",
    "outro": "Outros",
}


def categoria(natureza: str, tipo: str) -> str:
    """Classifica quem recebeu pela natureza jurídica informada pela Receita."""
    n, t = _chave(natureza), _chave(tipo)
    if "fisica" in t:
        return "pessoa"
    if "municipal" in n or "municipio" in n:
        return "prefeitura"
    if "estadual" in n or "distrito federal" in n or n.startswith("estado"):
        return "estado"
    if "federal" in n or "empresa publica" in n or "economia mista" in n or "unidade gestora" in t:
        return "federal"
    if any(x in n for x in ("associacao", "fundacao privada", "organizacao religiosa", "organizacao social",
                            "servico social", "entidade sindical", "partido")):
        return "entidade"
    if any(x in n for x in ("sociedade", "empresari", "limitada", "eireli", "cooperativa", "empresa individual", "consorcio")):
        return "empresa"
    return "outro"


def favorecidos(rows, anos: list[int], n: int = 150) -> dict[int, dict]:
    """Quem recebeu o dinheiro das emendas e onde fica, pelo ano do pagamento."""
    col = None
    anos_set = set(anos)
    nova = lambda: {"valor": 0.0, "nome": "", "cat": "", "natureza": "", "uf": "", "municipio": "", "autores": defaultdict(float)}  # noqa: E731
    por = {a: defaultdict(nova) for a in anos}
    cats = {a: defaultdict(lambda: [0.0, set()]) for a in anos}
    ufs = {a: defaultdict(float) for a in anos}
    muns = {a: defaultdict(lambda: [0.0, set()]) for a in anos}
    autor_rec = {a: defaultdict(lambda: defaultdict(float)) for a in anos}  # autor -> recebedor -> valor
    autor_cod = {a: defaultdict(lambda: defaultdict(set)) for a in anos}  # autor -> recebedor -> códigos das emendas
    for r in rows:
        if col is None:
            col = achar_colunas(list(r.keys()), REGRAS_FAV)
            log.info("Emendas (favorecidos): colunas usadas %s", col)
            if not col["valor"] or not col["nome"] or not col["anomes"]:
                log.error("Emendas (favorecidos): colunas essenciais não encontradas")
                return {}
        am = digits(r.get(col["anomes"]))
        if len(am) < 6:
            continue
        ano = int(am[:4]) if am[:2] in ("19", "20") else int(am[-4:])
        if ano not in anos_set:
            continue
        v = to_float(r.get(col["valor"]))
        if not v:
            continue
        g = lambda k: ((r.get(col[k]) or "").strip() if col.get(k) else "")  # noqa: E731
        doc, nome = digits(g("doc")), g("nome")
        chave = doc if len(doc) == 14 else nome
        cat = categoria(g("natureza"), g("tipo"))
        uf = g("uf").upper() if g("uf").upper() in SIGLAS else UFS.get(norm_name(g("uf")), "")
        mun = bonito(g("municipio"))
        f = por[ano][chave]
        f["valor"] += v
        f["nome"] = f["nome"] or bonito(nome)
        f["cat"], f["natureza"] = f["cat"] or cat, f["natureza"] or g("natureza")
        f["uf"], f["municipio"] = f["uf"] or uf, f["municipio"] or mun
        autor = g("autor")
        f["autores"][nome_autor(autor)[1]] += v
        c = cats[ano][cat]; c[0] += v; c[1].add(chave)
        # Mapa: o dinheiro de bancos e órgãos federais (como a Caixa, que repassa a obras) não tem a cidade final
        if cat != "federal" and uf:
            ufs[ano][uf] += v
            if cat != "estado" and mun:
                m = muns[ano][(mun, uf)]; m[0] += v; m[1].add(chave)
        autor_rec[ano][_chave(autor)][chave] += v
        if g("codigo"):
            autor_cod[ano][_chave(autor)][chave].add(g("codigo"))
    out = {}
    for ano, fs in por.items():
        if not fs:
            continue
        def item(k, f):
            return {"doc": k if len(k) == 14 and k.isdigit() else "", "nome": f["nome"], "cat": f["cat"], "natureza": f["natureza"],
                    "uf": f["uf"], "municipio": f["municipio"], "valor": round(f["valor"], 2), "autores": _top(f["autores"], 5)}
        ordem = sorted(fs.items(), key=lambda kv: -kv[1]["valor"])
        por_autor = {}
        for a, recs in autor_rec[ano].items():
            top = sorted(recs.items(), key=lambda kv: -kv[1])[:8]
            por_autor[a] = [[fs[k]["nome"] + (f" ({fs[k]['municipio']}-{fs[k]['uf']})" if fs[k]["municipio"] and fs[k]["cat"] not in ("estado", "federal") else
                                              f" ({fs[k]['uf']})" if fs[k]["uf"] else ""), round(x, 2),
                            k if len(k) == 14 and k.isdigit() else "", sorted(autor_cod[ano][a][k])[:3]] for k, x in top]
        out[ano] = {
            "n": len(fs), "total": round(sum(f["valor"] for f in fs.values()), 2),
            "por_categoria": [{"cat": k, "rotulo": CATEGORIAS[k], "valor": round(v[0], 2), "n": len(v[1])}
                              for k, v in sorted(cats[ano].items(), key=lambda kv: -kv[1][0])],
            "lista": [item(k, f) for k, f in ordem[:n]],
            "empresas": [item(k, f) for k, f in ordem if f["cat"] == "empresa"][:100],
            "entidades": [item(k, f) for k, f in ordem if f["cat"] == "entidade"][:100],
            "por_uf": _top(ufs[ano], 30),
            "municipios": [{"nome": k[0], "uf": k[1], "valor": round(v[0], 2), "n": len(v[1])}
                           for k, v in sorted(muns[ano].items(), key=lambda kv: -kv[1][0])[:400]],
            "n_municipios": len(muns[ano]),
            "_por_autor": por_autor,
        }
    return out


def coletar(politicos: list[dict], anos: list[int], cache: Path, saida: Path, pagos: dict | None = None,
            receita: dict[str, dict] | None = None, paginas: set[str] | None = None) -> dict | None:
    """Baixa, resume e grava data/emendas/{ano}.json. Se o Portal falhar, não interrompe o resto do site.

    pagos: os pagamentos ligados às emendas (pagamentos.resumir), com quem pagou, a quem e os documentos.
    receita: dados da Receita das empresas (para separar empresas de órgãos públicos); paginas: CNPJs com página no site.
    Devolve o índice dos anos e, em "autores", o nome e o partido de cada autor (para as páginas das empresas)."""
    try:
        z = baixar(cache)
        if not z:
            return None
        extras = (deputados_legislatura(57) + senadores_legislatura(57)
                  + deputados_legislatura(56) + senadores_legislatura(56))
        log.info("Emendas: %d ex-parlamentares e licenciados para achar o partido dos autores", len(extras))
        res = resumir(linhas(z, ""), anos, politicos, extras)
        fav = favorecidos(linhas(z, "favorecido"), anos)
    except Exception:  # noqa: BLE001
        log.exception("Emendas: erro ao montar os dados; a página de emendas fica sem atualização")
        avisar("Emendas: o arquivo do Portal da Transparência veio com problema; a página de emendas não foi atualizada")
        return None
    if not res:
        avisar("Emendas: o arquivo do Portal da Transparência veio sem as colunas esperadas; a página de emendas não foi atualizada")
        return None
    nomes: dict[str, dict] = {}
    for ano in sorted(res, reverse=True):  # o nome e o partido mais recentes valem
        for a in res[ano]["autores"] + res[ano]["coletivos"]:
            nomes.setdefault(a["chave"], {"nome": a["nome"], "politico": a.get("politico"), "partido": a.get("partido", ""),
                                          "uf": a.get("uf", ""), "casa": a.get("casa", "")})
    for ano, d in res.items():
        f = fav.get(ano)
        por_autor = (f or {}).pop("_por_autor", {})
        pg = ((pagos or {}).get("anos") or {}).get(ano)
        for a in d["autores"] + d["coletivos"]:
            chave = a.pop("chave")
            a["recebedores"] = com_motivo(por_autor.get(chave, []), (pg or {}).get("autores", {}).get(chave))
            if pg and chave in pg["autores"]:
                a["pagamentos"] = {"valor": round(pg["autores"][chave]["valor"], 2), "arquivo": arquivo_docs(chave)}
        d["favorecidos"] = f
        d["pagamentos"] = resumo_pagamentos(pg, nomes, pagos.get("ate", ""), receita or {}, paginas or set()) if pg else None
        if pg:
            for chave, au in pg["autores"].items():
                write_json(saida / "emendas" / "docs" / str(ano) / f"{arquivo_docs(chave)}.json",
                           {"nome": _mostrar(chave, au["nome"], nomes), "valor": round(au["valor"], 2), "n": au["n"],
                            "docs": [_documento(i) for i in au["docs"]]})
        write_json(saida / "emendas" / f"{ano}.json", d)
    indice = {"anos": sorted(res), "totais": {str(a): d["total"] for a, d in res.items()}}
    write_json(saida / "emendas" / "anos.json", indice)
    return {**indice, "autores": nomes}


def com_motivo(recebedores: list, pag_autor: dict | None) -> list:
    """Junta a cada recebedor o motivo do maior pagamento a ele (a descrição da nota de empenho) e o link da nota."""
    if not pag_autor:
        return recebedores
    from .pagamentos import url_documento
    maior: dict[str, dict] = {}
    for d in pag_autor["docs"]:
        if d["doc"] and d["desc"] and (d["doc"] not in maior or d["valor"] > maior[d["doc"]]["valor"]):
            maior[d["doc"]] = d
    out = []
    for r in recebedores:
        d = maior.get(r[2]) if len(r) > 2 else None
        out.append(r + [d["desc"], url_documento(d["emp"])] if d else r)
    return out


def arquivo_docs(chave: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", chave)[:80].strip("-") or "sem-nome"


def _mostrar(chave: str, bruto: str, nomes: dict[str, dict]) -> str:
    return (nomes.get(chave) or {}).get("nome") or nome_autor(bruto)[1]


def _documento(i: dict) -> dict:
    from .pagamentos import documento
    return documento(i)


def tipo_pela_receita(e: dict | None) -> str:
    """empresa, entidade, publico ou '' (sem dados), pela natureza jurídica na Receita."""
    if not e or not e.get("natureza"):
        return ""
    c = categoria(e["natureza"], "Pessoa Jurídica")
    return "publico" if c in ("prefeitura", "estado", "federal") else c if c in ("empresa", "entidade") else "outro"


def resumo_pagamentos(pg: dict, nomes: dict[str, dict], ate: str, receita: dict[str, dict], paginas: set[str]) -> dict:
    """Quem pagou (órgãos), quem mais teve pagamentos e quais empresas e entidades receberam, num ano."""
    def autor(k: str, bruto: str) -> dict:
        n = nomes.get(k) or {}
        return {"nome": _mostrar(k, bruto, nomes), "politico": n.get("politico"), "partido": n.get("partido", "")}
    brutos = {k: a["nome"] for k, a in pg["autores"].items()}
    empresas = sorted(((d, f) for d, f in pg["favorecidos"].items() if tipo_pela_receita(receita.get(d)) != "publico"),
                      key=lambda kv: -kv[1]["valor"])
    return {
        "ate": ate, "total": round(pg["total"], 2), "n": pg["n"],
        "orgaos": [{"nome": k, "valor": round(o["valor"], 2), "n": o["n"], "ugs": _top(o["ugs"], 5)}
                   for k, o in sorted(pg["orgaos"].items(), key=lambda kv: -kv[1]["valor"])[:40]],
        "autores": [{**autor(k, a["nome"]), "valor": round(a["valor"], 2), "n": a["n"], "orgaos": _top(a["orgaos"], 3),
                     "arquivo": arquivo_docs(k)}
                    for k, a in sorted(pg["autores"].items(), key=lambda kv: -kv[1]["valor"])],
        "empresas": [{"cnpj": doc, "nome": bonito((receita.get(doc) or {}).get("razao_social") or f["nome"]),
                      "tipo": tipo_pela_receita(receita.get(doc)), "pagina": doc in paginas,
                      "valor": round(f["valor"], 2), "n": f["n"],
                      "autores": [{**autor(k, brutos.get(k, k)), "valor": round(v, 2)}
                                  for k, v in sorted(f["autores"].items(), key=lambda kv: -kv[1])[:5]],
                      "orgaos": _top(f["orgaos"], 2)} for doc, f in empresas[:200]],
        "n_empresas": len(empresas),
    }
