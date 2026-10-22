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
alvo = None
for ano in (2026, 2025, 2024, 2023):
    rows = list(read_csv_file(download(COTA_URL.format(ano=ano), cache / f"c{ano}.zip")))
    com = [r for r in rows if (r.get("urlDocumento") or "").strip()]
    tipos = Counter(re.sub(r"\d+", "N", r["urlDocumento"].split("?")[0])[:70] for r in com)
    print(f"\n=== {ano}: {len(rows)} linhas, {len(com)} com urlDocumento. Padrões: {tipos.most_common(4)}")
    print("    indTipoDocumento:", Counter(r.get("indTipoDocumento") for r in com).most_common(5))
    for r in rows:
        if r.get("ideDocumento") == "8165838":
            alvo = r
    res = Counter()
    ruins = []
    for r in random.sample(com, min(40, len(com))):
        s, ct, _ = st(r["urlDocumento"].strip())
        chave = ("pdf" if r["urlDocumento"].endswith(".pdf") else "nfe", r.get("indTipoDocumento"), s)
        res[chave] += 1
        if s != 200:
            ruins.append(r)
    print("    status (formato, tipo de documento, http):", dict(res))
    for r in ruins[:4]:
        nu, ide, cad = r.get("nuDeputadoId"), r.get("ideDocumento"), r.get("ideCadastro")
        print("    -- quebrado:", {k: r.get(k) for k in ("urlDocumento", "indTipoDocumento", "datEmissao", "numMes", "txtDescricao", "ideCadastro", "nuDeputadoId", "txtFornecedor")})
        det = link_detalhe(nu, ano, int(r.get("numMes") or 0), r.get("numSubCota"), r.get("txtCNPJCPF"), r.get("txtNumero"), ide)
        s, ct, h = st(det, corpo=True)
        links = sorted(set(re.findall(r'href="([^"]*(?:publ|nota-fiscal|\.pdf)[^"]*)"', h)))[:5]
        print(f"       detalhe {s} {ct} · links na página: {links}")
        for alt in (f"https://www.camara.leg.br/cota-parlamentar/nota-fiscal-eletronica?ideDocumentoFiscal={ide}",
                    f"https://www.camara.leg.br/cota-parlamentar/documentos/publ/{cad}/{ano}/{ide}.pdf",
                    r["urlDocumento"].replace("http://", "https://").replace("//camara", "//www.camara")):
            print(f"       {st(alt)[:2]} {alt}")
print("\n=== Nota do print (ideDocumento 8165838):", {k: (alvo or {}).get(k) for k in ("urlDocumento", "indTipoDocumento", "datEmissao", "numMes", "numAno", "txtDescricao", "nuDeputadoId", "ideCadastro", "txtFornecedor", "numSubCota", "txtNumero")})
if alvo:
    det = link_detalhe(alvo["nuDeputadoId"], 2026, int(alvo["numMes"]), alvo.get("numSubCota"), alvo.get("txtCNPJCPF"), alvo.get("txtNumero"), alvo["ideDocumento"])
    s, ct, h = st(det, corpo=True)
    print("    detalhe:", s, ct, det)
    i = h.find("Documento")
    print("    trecho:", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))[:1200])
    print("    links:", sorted(set(re.findall(r'href="([^"]+)"', h)))[-30:])
