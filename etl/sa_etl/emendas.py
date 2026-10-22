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

from .util import _session, digits, get_json, norm_name, to_float, write_json

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

def baixar(cache: Path, max_horas: float = 20) -> Path | None:
    """Baixa o .zip para o cache. Se o Portal estiver fora do ar, usa a última cópia que tiver."""
    import time
    dest = cache / "EmendasParlamentares.zip"
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
        return dest
    log.error("Emendas: não foi possível baixar o arquivo do Portal da Transparência")
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
    "empenhado": [["valor", "empenhado"]],
    "liquidado": [["valor", "liquidado"]],
    "pago": [["valor", "pago"]],
    "rap_pago": [["restos", "pagos"], ["restos", "pago"]],
}
REGRAS_FAV = {
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


def local_de(r: dict, col: dict) -> tuple[str, str, str]:
    """(nível, município, UF) a partir da localidade da emenda. Nível: municipio, estado, regiao, nacional, outro."""
    loc = (r.get(col["local"]) or "").strip() if col["local"] else ""
    mun = (r.get(col["municipio"]) or "").strip() if col["municipio"] else ""
    uf = (r.get(col["uf"]) or "").strip() if col["uf"] else ""
    uf = uf if uf.upper() in SIGLAS else UFS.get(norm_name(uf), "")
    m = re.match(r"^(.+?)\s*[-/]\s*([A-Z]{2})$", loc)
    if m and m.group(2) in SIGLAS:
        return "municipio", m.group(1).strip(), m.group(2)
    m = re.match(r"^(.+?)\s*\(UF\)$", loc, flags=re.I)
    if m:
        return "estado", "", UFS.get(norm_name(m.group(1)), uf)
    n = norm_name(loc)
    if n in UFS:
        return "estado", "", UFS[n]
    if "NACIONAL" in n or n in ("BRASIL", "EXTERIOR"):
        return "nacional", "", ""
    if "REGIAO" in n:
        return "regiao", loc, ""
    if mun and uf and norm_name(mun) not in ("", "SEM INFORMACAO", "MULTIPLO"):
        return "municipio", mun, uf
    if uf:
        return "estado", "", uf
    return "outro", loc, ""


def bonito(nome: str) -> str:
    """CAIXA ALTA → Nome Próprio, mantendo de/da/do minúsculos."""
    if not nome or not nome.isupper():
        return nome
    pequenas = {"de", "da", "do", "das", "dos", "e"}
    return " ".join(p.lower() if p.lower() in pequenas and i else p.capitalize() for i, p in enumerate(nome.lower().split()))


# ---------------------------------------------------------------- autores → parlamentares

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
            if k in vistos and vistos[k].get("id") != p.get("id"):
                ambiguos.add(k)
            vistos[k] = p
        for k, p in vistos.items():
            idx.setdefault(k, p)
    for k in ambiguos:
        idx.pop(k, None)
    return idx


# ---------------------------------------------------------------- resumo

def _top(d: dict, n: int) -> list:
    return [[k, round(v, 2)] for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:n] if v]


def resumir(rows, anos: list[int], politicos: list[dict], extras: list[dict] | None = None) -> dict[int, dict]:
    """Soma as emendas por ano: tipo, área, estado, município, autor e partido."""
    idx = indice_nomes(politicos, extras or [])
    anos_set = set(anos)
    col = None
    soma = {a: {"tipo": defaultdict(lambda: [0.0, 0.0, 0]), "area": defaultdict(lambda: [0.0, 0.0]),
                "uf": defaultdict(lambda: [0.0, 0.0]), "nivel": defaultdict(lambda: [0.0, 0.0]),
                "mun": defaultdict(lambda: [0.0, 0.0, 0]), "autor": {}, "total": [0.0, 0.0, 0]} for a in anos}
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
        nivel, mun, uf = local_de(r, col)
        cod = (r.get(col["codigo"]) or "").strip() if col["codigo"] else ""

        s["total"][0] += emp; s["total"][1] += pago; s["total"][2] += 1
        t = s["tipo"][tipo]; t[0] += emp; t[1] += pago; t[2] += 1
        a = s["area"][area]; a[0] += emp; a[1] += pago
        nv = s["nivel"][nivel]; nv[0] += emp; nv[1] += pago
        if uf:
            u = s["uf"][uf]; u[0] += emp; u[1] += pago
        destino = f"{bonito(mun)} ({uf})" if nivel == "municipio" else (f"Estado: {uf}" if nivel == "estado" and uf else
                                                                         "Nacional" if nivel == "nacional" else bonito(mun) or "Outro")
        if nivel == "municipio":
            m = s["mun"][(bonito(mun), uf)]; m[0] += emp; m[1] += pago; m[2] += 1
        au = s["autor"].setdefault(autor, {"emp": 0.0, "pago": 0.0, "n": set(), "tipos": Counter(),
                                           "area": defaultdict(float), "destino": defaultdict(float)})
        au["emp"] += emp; au["pago"] += pago; au["n"].add(cod or id(r)); au["tipos"][tipo] += pago or emp
        au["area"][area] += pago or emp
        au["destino"][destino] += pago or emp

    out = {}
    for ano, s in soma.items():
        if not s["total"][2]:
            continue
        autores, coletivos = [], []
        for nome, au in s["autor"].items():
            coletivo = autor_coletivo(nome, au["tipos"].most_common(1)[0][0] if au["tipos"] else "outro")
            p = None if coletivo else idx.get(_chave(nome))
            item = {"nome": bonito(nome), "empenhado": round(au["emp"], 2), "pago": round(au["pago"], 2), "n": len(au["n"]),
                    "areas": _top(au["area"], 4), "destinos": _top(au["destino"], 5),
                    "pix": round(au["tipos"].get("pix", 0), 2)}
            if coletivo:
                coletivos.append({**item, "tipo": coletivo})
            else:
                item.update({"politico": (p or {}).get("id"), "partido": (p or {}).get("partido", ""), "uf": (p or {}).get("uf", ""),
                             "casa": (p or {}).get("casa", ""), "foto": (p or {}).get("foto", "")})
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
            "por_uf": sorted(({"uf": k, "empenhado": round(v[0], 2), "pago": round(v[1], 2)} for k, v in s["uf"].items()),
                             key=lambda x: -x["empenhado"]),
            "por_nivel": {k: {"empenhado": round(v[0], 2), "pago": round(v[1], 2)} for k, v in s["nivel"].items()},
            "municipios": sorted(({"nome": k[0], "uf": k[1], "empenhado": round(v[0], 2), "pago": round(v[1], 2), "n": v[2]}
                                  for k, v in s["mun"].items()), key=lambda x: -x["empenhado"])[:300],
            "n_municipios": len(s["mun"]),
            "autores": autores,
            "coletivos": coletivos[:200],
            "partidos": sorted(({"sigla": k, "n": v["n"], "camara": v["camara"], "senado": v["senado"],
                                 "empenhado": round(v["empenhado"], 2), "pago": round(v["pago"], 2), "pix": round(v["pix"], 2),
                                 "areas": _top(v["area"], 5)} for k, v in partidos.items()), key=lambda x: -x["empenhado"]),
            "sem_partido": {"n": len(sem_partido), "empenhado": round(sum(a["empenhado"] for a in sem_partido), 2),
                            "pago": round(sum(a["pago"] for a in sem_partido), 2)},
        }
        log.info("Emendas %d: %d linhas, R$ %.0f empenhados, R$ %.0f pagos, %d autores (%d sem partido identificado)",
                 ano, s["total"][2], s["total"][0], s["total"][1], len(autores), len(sem_partido))
    return out


def favorecidos(rows, anos: list[int], n: int = 150) -> dict[int, dict]:
    """Quem recebeu o dinheiro das emendas, pelo ano do pagamento."""
    col = None
    anos_set = set(anos)
    por = {a: defaultdict(lambda: {"valor": 0.0, "nome": "", "tipo": "", "uf": "", "municipio": "", "autores": defaultdict(float)})
           for a in anos}
    tipos = {a: defaultdict(float) for a in anos}
    for r in rows:
        if col is None:
            col = achar_colunas(list(r.keys()), REGRAS_FAV)
            log.info("Emendas (favorecidos): colunas usadas %s", col)
            if not col["valor"] or not col["nome"] or not col["anomes"]:
                log.error("Emendas (favorecidos): colunas essenciais não encontradas")
                return {}
        am = digits(r.get(col["anomes"]))
        if len(am) < 4:
            continue
        ano = int(am[:4]) if am[:2] in ("19", "20") else int(am[-4:])
        if ano not in anos_set:
            continue
        v = to_float(r.get(col["valor"]))
        if not v:
            continue
        doc = digits(r.get(col["doc"])) if col["doc"] else ""
        nome = (r.get(col["nome"]) or "").strip()
        f = por[ano][doc or nome]
        f["valor"] += v
        f["nome"] = f["nome"] or nome
        f["tipo"] = f["tipo"] or ((r.get(col["tipo"]) or "").strip() if col["tipo"] else "")
        f["natureza"] = f.get("natureza") or ((r.get(col["natureza"]) or "").strip() if col["natureza"] else "")
        f["uf"] = f["uf"] or ((r.get(col["uf"]) or "").strip() if col["uf"] else "")
        f["municipio"] = f["municipio"] or ((r.get(col["municipio"]) or "").strip() if col["municipio"] else "")
        if col["autor"]:
            f["autores"][bonito((r.get(col["autor"]) or "").strip())] += v
        tipos[ano][(r.get(col["tipo"]) or "Não informado").strip() if col["tipo"] else "Não informado"] += v
    out = {}
    for ano, fs in por.items():
        if not fs:
            continue
        lista = []
        for doc, f in sorted(fs.items(), key=lambda kv: -kv[1]["valor"])[:n]:
            d = doc if doc.isdigit() else ""
            lista.append({"doc": d if len(d) == 14 else "", "nome": bonito(f["nome"]), "tipo": f["tipo"], "natureza": f.get("natureza", ""),
                          "uf": f["uf"], "municipio": bonito(f["municipio"]), "valor": round(f["valor"], 2),
                          "autores": _top(f["autores"], 5)})
        out[ano] = {"lista": lista, "n": len(fs), "total": round(sum(f["valor"] for f in fs.values()), 2),
                    "por_tipo": _top(tipos[ano], 12)}
    return out


def coletar(politicos: list[dict], anos: list[int], cache: Path, saida: Path) -> dict | None:
    """Baixa, resume e grava data/emendas/{ano}.json. Se o Portal falhar, não interrompe o resto do site."""
    try:
        z = baixar(cache)
        if not z:
            return None
        extras = deputados_legislatura(57) + deputados_legislatura(56)
        res = resumir(linhas(z, ""), anos, politicos, extras)
        fav = favorecidos(linhas(z, "favorecido"), anos)
    except Exception:  # noqa: BLE001
        log.exception("Emendas: erro ao montar os dados; a página de emendas fica sem atualização")
        return None
    for ano, d in res.items():
        d["favorecidos"] = fav.get(ano)
        write_json(saida / "emendas" / f"{ano}.json", d)
    indice = {"anos": sorted(res), "totais": {str(a): d["total"] for a, d in res.items()}}
    write_json(saida / "emendas" / "anos.json", indice)
    return indice
