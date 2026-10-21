"""Confere o conteúdo das páginas oficiais de lista de despesas (Câmara 'analitico' e Senado 'ceaps')."""
import html as H
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sa_etl.util import _session, read_csv_file  # noqa: E402


def get(u):
    for t in range(4):
        try:
            r = _session.get(u, timeout=60, headers={"Accept": "text/html"})
            return r.status_code, r.text
        except Exception as e:  # noqa: BLE001
            err = type(e).__name__
            time.sleep(5)
    return f"erro {err}", ""


def texto(h):
    h = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", h)
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def analitico(nu, mes, ano, desp):
    return (f"https://www.camara.leg.br/cota-parlamentar/analitico?nuDeputadoId={nu}&dataInicio={mes}/{ano}&dataFim={mes}/{ano}"
            f"&despesa={desp}&nomeHospede=&nomePassageiro=&nomeFornecedor=&cnpjFornecedor=&numDocumento=&sguf=")


rows = list(read_csv_file(Path("etl/.cache/camara-cota-2025.csv.zip")))
sig = next(r for r in rows if "SIGEPA" in (r.get("txtDescricao") or "") and r.get("txtPassageiro"))
nu = sig["nuDeputadoId"]
for mes, desp in ((sig["numMes"], "998"), ("10", "998"), ("11", "998"), ("1", "10")):
    u = analitico(nu, mes, "2025", desp)
    st, h = get(u)
    t = texto(h)
    i = max(0, t.find("Fornecedor") - 200)
    print(f"\n## {st} len={len(h)} mes={mes} despesa={desp} · {u}")
    print("   TEXTO:", t[i:i + 1500])
    print("   LINKS:", sorted({m for m in re.findall(r'href="([^"]+)"', h) if re.search(r"documento|nota|pdf", m)})[:8])

print("\n## Senado")
for n in (1, 2, 3, 4, 5, 8, 9):
    u = f"https://www6g.senado.leg.br/transparencia/sen/6008/ceaps/{n}/?ano=2025"
    st, h = get(u)
    t = texto(h)
    i = t.find("Total")
    print(f"- {st} ceaps/{n}: {t[max(0, t.find('Cota') - 50):][:200]}")
    print("   TRECHO:", t[max(0, i - 600):i + 100][:700])
    print("   LINKS:", sorted({m for m in re.findall(r'href="([^"]+)"', h) if re.search(r"documento|nota|pdf|ceaps", m)})[:8])
