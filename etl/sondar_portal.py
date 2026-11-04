"""Sonda temporária: o que a API de renúncia do Portal aceita e quantas páginas tem (roda só no Actions)."""
import json
import sys
import time

sys.path.insert(0, ".")
from sa_etl.util import _session, chave_portal  # noqa: E402

CH = chave_portal()
H = {"chave-api-dados": CH, "Accept": "application/json"}
API = "https://api.portaldatransparencia.gov.br/api-de-dados/renuncias-valor"


def p(*a):
    print(*a, flush=True)


def pedir(url, params, h=H):
    t = time.time()
    try:
        r = _session.get(url, params=params, headers=h, timeout=120)
    except Exception as e:  # noqa: BLE001
        return None, f"erro {e}"[:150], time.time() - t
    try:
        d = r.json()
    except ValueError:
        d = None
    return d, f"HTTP {r.status_code} {r.headers.get('content-type')} {(r.text or '')[:150]!r}" if r.status_code != 200 else "200", time.time() - t


# 1. a documentação (swagger)
for u in ("https://api.portaldatransparencia.gov.br/v3/api-docs", "https://api.portaldatransparencia.gov.br/v3/api-docs/swagger-config"):
    d, m, s = pedir(u, {}, {"Accept": "application/json"})
    p("DOC", u, m[:80], round(s, 1))
    if isinstance(d, dict) and "paths" in d:
        for path, ops in d["paths"].items():
            if "renuncia" in path.lower():
                for met, op in ops.items():
                    p("  PATH", met, path, "|", op.get("summary"))
                    for par in op.get("parameters", []):
                        p("     param", par.get("name"), par.get("in"), "req" if par.get("required") else "", par.get("schema"), par.get("description"))
        break

# 2. primeira página sem filtro: campos e anos
d, m, s = pedir(API, {"pagina": 1})
p("SEM FILTRO p1", m, round(s, 1), len(d) if isinstance(d, list) else d)
if isinstance(d, list) and d:
    p("  exemplo", json.dumps(d[0], ensure_ascii=False)[:800])

# 3. filtros candidatos para o ano
for k in ("ano", "anoCalendario", "anoReferencia", "anoBase", "exercicio"):
    for v in ("2024", "2025"):
        d, m, s = pedir(API, {"pagina": 1, k: v})
        anos = sorted({str(x.get("ano") or x.get("anoCalendario") or x.get("anoReferencia")) for x in d}) if isinstance(d, list) else None
        p("FILTRO", k, v, m[:120], round(s, 1), "linhas", len(d) if isinstance(d, list) else "-", "anos", anos)


def ultima_pagina(params, limite=400000):
    """Busca binária da última página com linhas."""
    lo, hi = 1, 1
    while True:
        d, m, _ = pedir(API, {**params, "pagina": hi})
        if not isinstance(d, list):
            return f"falhou em {hi}: {m[:100]}"
        if not d:
            break
        lo, hi = hi, hi * 2
        if hi > limite:
            return f">{limite}"
    while hi - lo > 1:
        mid = (lo + hi) // 2
        d, m, _ = pedir(API, {**params, "pagina": mid})
        if not isinstance(d, list):
            return f"falhou em {mid}: {m[:100]}"
        lo, hi = (mid, hi) if d else (lo, mid)
    d, _, _ = pedir(API, {**params, "pagina": lo})
    anos = sorted({str(x.get("ano")) for x in d}) if isinstance(d, list) else None
    return f"{lo} páginas (última com {len(d) if isinstance(d, list) else '?'} linhas, anos {anos})"


# 4. quantas páginas tem cada consulta
p("PAGINAS sem filtro:", ultima_pagina({}))
for uf in ("SP", "MG", "AC", "DF"):
    p("PAGINAS UF", uf, ultima_pagina({"nomeSiglaUF": uf}))

# 5. anos em várias profundidades da consulta sem filtro
for pg in (1, 5000, 15000, 26573, 40000, 60000):
    d, m, s = pedir(API, {"pagina": pg})
    anos = sorted({str(x.get("ano")) for x in d}) if isinstance(d, list) else None
    p("PROFUNDIDADE", pg, m[:60], round(s, 1), "s", "linhas", len(d) if isinstance(d, list) else "-", "anos", anos)

# 6. arquivos de download
for ano in (2023, 2024, 2025, 2026):
    for u in (f"https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/renuncias/{ano}_RenunciasFiscais.zip",):
        try:
            r = _session.head(u, timeout=60, allow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0"})
            p("ZIP", ano, r.status_code, r.headers.get("content-length"), r.headers.get("last-modified"), r.headers.get("server"))
        except Exception as e:  # noqa: BLE001
            p("ZIP", ano, e)
try:
    r = _session.get("https://portaldatransparencia.gov.br/download-de-dados/renuncias", timeout=60,
                     headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0", "Accept": "text/html"})
    import re
    p("PAGINA DOWNLOAD", r.status_code, sorted(set(re.findall(r"20[12]\d", r.text)))[-12:])
    for linha in re.findall(r".{0,120}(?:arquivos|anos|ano)\s*[=:].{0,200}", r.text)[:8]:
        p("   ", linha.strip()[:300])
except Exception as e:  # noqa: BLE001
    p("PAGINA DOWNLOAD", e)
