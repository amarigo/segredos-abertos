"""TEMPORÁRIO: confere se os links de nota fiscal dos dados abertos da Câmara abrem, e o que funciona quando não abrem."""
import random
import re
import sys
from collections import Counter
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from sa_etl.camara import COTA_URL, link_detalhe  # noqa: E402
from sa_etl.util import download, read_csv_file  # noqa: E402

random.seed(7)
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (segredos-abertos)"


def st(u, corpo=False):
    try:
        r = S.get(u, timeout=25, allow_redirects=True)
        return r.status_code, r.headers.get("content-type", "")[:25], (r.text if corpo and "html" in r.headers.get("content-type", "") else "")
    except Exception as e:  # noqa: BLE001
        return f"erro {type(e).__name__}", "", ""


cache = Path("/tmp/cache"); cache.mkdir(exist_ok=True)
from concurrent.futures import ThreadPoolExecutor


def cod(u):
    try:
        r = S.head(u, timeout=25, allow_redirects=True)
        return r.status_code
    except Exception as e:  # noqa: BLE001
        return type(e).__name__


for ano in (2026, 2025):
    rows = list(read_csv_file(download(COTA_URL.format(ano=ano), cache / f"c{ano}.zip")))
    pdf = [r for r in rows if (r.get("urlDocumento") or "").strip().endswith(".pdf")]
    nfe = [r for r in rows if "nota-fiscal-eletronica" in (r.get("urlDocumento") or "")]
    amostra = random.sample(pdf, 600) + random.sample(nfe, 200)
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda r: cod(r["urlDocumento"].strip()), amostra))
    por = Counter()
    ruins = []
    for r, c in zip(amostra, res):
        tipo = "pdf" if r["urlDocumento"].endswith(".pdf") else "nfe"
        por[(tipo, c)] += 1
        if c != 200:
            ruins.append(r)
    print(f"\n=== {ano}: {dict(por)}")
    print("   quebrados por categoria:", Counter(r["txtDescricao"][:40] for r in ruins).most_common(8))
    print("   quebrados por deputado:", Counter(r["nuDeputadoId"] for r in ruins).most_common(5))
    print("   quebrados por mês:", Counter(r["numMes"] for r in ruins).most_common(12))
    print("   quebrados por fornecedor:", Counter(r["txtFornecedor"][:30] for r in ruins).most_common(6))
    print("   categorias na amostra:", Counter(r["txtDescricao"][:40] for r in amostra if r["urlDocumento"].endswith(".pdf")).most_common(8))
    for r in ruins[:3]:
        print("   ex:", {k: r.get(k) for k in ("urlDocumento", "datEmissao", "numMes", "txtDescricao", "txtFornecedor", "indTipoDocumento", "vlrLiquido", "numRessarcimento", "vlrRestituicao")})
# Notas da mesma pessoa e mês do print
rows = list(read_csv_file(download(COTA_URL.format(ano=2026), cache / "c2026.zip")))
mes = [r for r in rows if r.get("nuDeputadoId") == "1649" and r.get("numMes") in ("9", "10") and r["urlDocumento"].endswith(".pdf")]
with ThreadPoolExecutor(8) as ex:
    cs = list(ex.map(lambda r: cod(r["urlDocumento"].strip()), mes))
print("\n=== deputado 1649, set-out/2026:", [(r["numMes"], r["datEmissao"][:10], r["txtDescricao"][:25], c) for r, c in zip(mes, cs)])
