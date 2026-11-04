"""Sonda temporária: a API de renúncia traz os mesmos dados dos arquivos .zip? (contagem de linhas e valores)"""
import csv
import io
import json
import random
import sys
import time
import zipfile

sys.path.insert(0, ".")
from sa_etl.util import _session, chave_portal, digits  # noqa: E402

H = {"chave-api-dados": chave_portal(), "Accept": "application/json"}
API = "https://api.portaldatransparencia.gov.br/api-de-dados/renuncias-valor"
ZIP = "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/renuncias/{ano}_RenunciasFiscais.zip"
NAV = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
INICIO = {2023: 39978, 2024: 47258, 2025: 50144}
ULTIMA = 50144


def p(*a):
    print(*a, flush=True)


def pagina(n):
    for _ in range(3):
        try:
            r = _session.get(API, params={"pagina": n}, headers=H, timeout=120)
            if r.status_code == 200:
                return r.json()
        except Exception as e:  # noqa: BLE001
            p("  erro", n, e)
        time.sleep(3)
    return None


ult = pagina(ULTIMA)
p("CAMPOS", json.dumps(ult[0], ensure_ascii=False))


def linhas_api_do_ano(ano):
    """Linhas do ano: páginas inteiras entre o início e o fim, mais as pontas."""
    ini, fim = INICIO[ano], INICIO[ano + 1]
    a = [x for x in pagina(ini) if x["ano"] == ano]
    b = [x for x in pagina(fim) if x["ano"] == ano]
    return len(a) + (fim - ini - 1) * 15 + len(b) if fim > ini else len(a)


for ano in (2023, 2024):
    r = _session.get(ZIP.format(ano=ano), headers={"User-Agent": NAV, "Accept": "application/zip,*/*"}, timeout=300)
    p("ZIP", ano, r.status_code, len(r.content), r.headers.get("last-modified"))
    z = zipfile.ZipFile(io.BytesIO(r.content))
    p("  arquivos", z.namelist())
    nome = next(n for n in z.namelist() if n.lower().endswith(".csv") and "benefici" not in n.lower()
                and not any(x in n.lower() for x in ("habilitad", "imune", "isent")))
    rows = list(csv.DictReader(io.TextIOWrapper(z.open(nome), encoding="latin-1", newline=""), delimiter=";"))
    p("  colunas", list(rows[0].keys()))
    col_v = next(c for c in rows[0] if "valor" in c.lower())
    col_c = next(c for c in rows[0] if "cnpj" in c.lower())
    total = sum(float(x[col_v].replace(".", "").replace(",", ".") or 0) for x in rows)
    p("  ZIP linhas", len(rows), "total", round(total, 2))
    n_api = linhas_api_do_ano(ano)
    p("  API linhas (pelas páginas)", n_api)
    # amostra: 10 páginas do meio do ano na API, cada linha procurada no .zip pelo CNPJ e valor
    idx = {}
    for x in rows:
        idx.setdefault(digits(x[col_c]).zfill(14), set()).add(round(float(x[col_v].replace(".", "").replace(",", ".") or 0), 2))
    achadas = faltam = 0
    random.seed(1)
    for pg in random.sample(range(INICIO[ano] + 1, INICIO[ano + 1]), 10):
        for x in pagina(pg) or []:
            if round(float(x["valorRenunciado"]), 2) in idx.get(digits(str(x["cnpj"])).zfill(14), set()):
                achadas += 1
            else:
                faltam += 1
                if faltam <= 3:
                    p("    na API e não no zip:", json.dumps(x, ensure_ascii=False)[:300])
    p("  AMOSTRA", ano, "linhas da API achadas no zip:", achadas, "não achadas:", faltam)
