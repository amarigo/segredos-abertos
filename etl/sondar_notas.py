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
print("print do usuário:", st("https://www.camara.leg.br/cota-parlamentar/documentos/publ/1649/2026/8165838.pdf")[:2])
rows = list(read_csv_file(download(COTA_URL.format(ano=2026), cache / "c2026.zip")))
import datetime as dt
hoje = dt.date.today()
faixas = Counter()
exemplos = {}
for r in rows:
    u = (r.get("urlDocumento") or "").strip()
    d = (r.get("datEmissao") or "")[:10]
    if not u or not d:
        continue
    dias = (hoje - dt.date.fromisoformat(d)).days
    f = "0-15" if dias <= 15 else "16-30" if dias <= 30 else "31-60" if dias <= 60 else "61-120" if dias <= 120 else "120+"
    exemplos.setdefault((f, "pdf" if u.endswith(".pdf") else "nfe"), []).append(r)
for (f, tipo), rs in sorted(exemplos.items()):
    amostra = random.sample(rs, min(25, len(rs)))
    c = Counter(st(r["urlDocumento"].strip())[0] for r in amostra)
    print(f"emitidas há {f} dias, {tipo}: {len(rs)} notas · amostra {dict(c)}")
# Mês de lançamento (numMes) x emissão: quando a nota entra nos dados abertos?
print("notas por mês de emissão em 2026:", sorted(Counter((r.get("datEmissao") or "")[:7] for r in rows).items())[-6:])
