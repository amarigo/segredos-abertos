"""Sonda temporária: onde começa cada ano na consulta de renúncia do Portal e quanto a API aguenta em paralelo."""
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, ".")
from sa_etl.util import _session, chave_portal  # noqa: E402

H = {"chave-api-dados": chave_portal(), "Accept": "application/json"}
API = "https://api.portaldatransparencia.gov.br/api-de-dados/renuncias-valor"


def p(*a):
    print(*a, flush=True)


def pagina(n):
    for _ in range(3):
        try:
            r = _session.get(API, params={"pagina": n}, headers=H, timeout=120)
            if r.status_code == 200:
                return r.json()
            p("  falha", n, r.status_code, r.text[:100])
        except Exception as e:  # noqa: BLE001
            p("  erro", n, e)
        time.sleep(3)
    return None


ULTIMA = 50144
anos_ult = sorted({x["ano"] for x in pagina(ULTIMA) or []})
p("ULTIMA", ULTIMA, anos_ult, "seguinte:", len(pagina(ULTIMA + 1) or []))


def inicio_do_ano(ano, lo=1, hi=ULTIMA):
    """Primeira página que tem alguma linha do ano (ou mais novo)."""
    while hi - lo > 1:
        mid = (lo + hi) // 2
        d = pagina(mid) or []
        if d and max(x["ano"] for x in d) >= ano:
            hi = mid
        else:
            lo = mid
    return hi


inicios = {}
for ano in (2021, 2022, 2023, 2024, 2025):
    inicios[ano] = inicio_do_ano(ano)
    p("ANO", ano, "começa na página", inicios[ano])
for ano in (2021, 2022, 2023, 2024):
    fim = inicios.get(ano + 1, ULTIMA + 1)
    p("PAGINAS DO ANO", ano, fim - inicios[ano], "≈ linhas", (fim - inicios[ano]) * 15)

# soma do ano 2024 numa amostra: as primeiras 30 páginas do ano (para comparar com o .zip, que tem 11732 empresas)
for par in (6, 12, 20):
    t = time.time()
    with ThreadPoolExecutor(par) as pool:
        res = list(pool.map(pagina, range(ULTIMA - 200 - par * 2, ULTIMA - 200)))
    s = time.time() - t
    p("PARALELO", par, "páginas", len(res), "ok", sum(r is not None for r in res), "em", round(s, 1), "s =>",
      round(len(res) / s * 60), "páginas/min")
