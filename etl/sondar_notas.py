"""TEMPORÁRIO: as notas sem PDF são as mais recentes? Confere todas as notas de out/2026 e amostras mais antigas."""
import random
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from sa_etl.camara import COTA_URL  # noqa: E402
from sa_etl.util import download, read_csv_file  # noqa: E402

random.seed(11)
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (segredos-abertos)"
cache = Path("/tmp/cache"); cache.mkdir(exist_ok=True)


def cod(u):
    for _ in range(2):
        try:
            return S.head(u, timeout=25, allow_redirects=True).status_code
        except Exception as e:  # noqa: BLE001
            err = type(e).__name__
    return err


def checa(nome, rs):
    with ThreadPoolExecutor(16) as ex:
        cs = list(ex.map(lambda r: cod(r["urlDocumento"].strip()), rs))
    c = Counter(cs)
    ruins = [(r, x) for r, x in zip(rs, cs) if x != 200]
    print(f"\n=== {nome}: {len(rs)} links · {dict(c)}")
    print("   quebrados por data de emissão:", Counter(r["datEmissao"][:10] for r, _ in ruins).most_common(15))
    print("   quebrados por categoria:", Counter(r["txtDescricao"][:30] for r, _ in ruins).most_common(6))
    print("   quebrados por deputado:", Counter(r["nuDeputadoId"] for r, _ in ruins).most_common(6))
    print("   quebrados por fornecedor:", Counter(r["txtFornecedor"][:25] for r, _ in ruins).most_common(6))
    for r, x in ruins[:6]:
        print("   ex:", x, r["urlDocumento"].strip(), r["datEmissao"][:10], r["numMes"], r["txtDescricao"][:30], r["txtFornecedor"][:25], r.get("indTipoDocumento"))
    return ruins


print("link do print:", cod("https://www.camara.leg.br/cota-parlamentar/documentos/publ/1649/2026/8165838.pdf"))
rows = [r for r in read_csv_file(download(COTA_URL.format(ano=2026), cache / "c2026.zip")) if (r.get("urlDocumento") or "").strip().endswith(".pdf")]
print("PDFs em 2026:", len(rows), "· por mês:", sorted(Counter(int(r["numMes"]) for r in rows).items()))
print("emissão mais recente:", max(r["datEmissao"][:10] for r in rows))
checa("2026, mês 10 (todas)", [r for r in rows if r["numMes"] == "10"])
checa("2026, mês 9 (todas)", [r for r in rows if r["numMes"] == "9"])
ant = [r for r in rows if int(r["numMes"]) <= 8]
checa("2026, meses 1-8 (amostra)", random.sample(ant, 3000))
