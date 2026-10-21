import json, re, sys
from collections import defaultdict
from pathlib import Path
import requests
sys.path.insert(0, "etl")
from sa_etl import camara, senado
from sa_etl.util import read_csv_file, to_float

H = {"User-Agent": "Mozilla/5.0 SegredosAbertos"}
def br(s): return to_float(s)

print("=== Senado recursos-utilizados JSON 5967 2025")
for u in ["https://adm.senado.gov.br/ergon-ng-reports/api/v1/senadores/5967/recursos-utilizados?ano=2025&formato=json",
          "https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/5967/recursos-utilizados?ano=2025"]:
    r = requests.get(u, headers=H, timeout=60); print(u, r.status_code); print(r.text[:4000])
print("=== auxilio-moradia-imoveis-funcionais")
r = requests.get("https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/auxilio-moradia-imoveis-funcionais", headers=H, timeout=60); print(r.status_code, r.text[:1500])
print("=== escritorios-apoio")
r = requests.get("https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/escritorios-apoio", headers=H, timeout=60); print(r.status_code, r.text[:800])
print("=== pessoal gabinete senado")
t = requests.get("https://www6g.senado.leg.br/transparencia/sen/5967/pessoal/?local=gabinete&ano=2025&vinculo=TODOS", headers=H, timeout=60).text
t = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", "", t); t = re.sub(r"\s+", " ", t)
i = t.find("<table"); print(re.sub(r'<(\w+)[^>]*>', r'<\1>', t[i:i+3000]))

print("=== COMPARACAO MG Camara (cota gasto: oficial x nosso)")
deps = [d for d in camara.deputados() if d["uf"] == "MG"]
ids = {d["id"] for d in deps}
cache = Path("etl/.cache")
nosso = defaultdict(float)
for ano in (2025, 2026):
    f = cache / f"camara-cota-{ano}.csv.zip"
    for r in camara.parse_cota(read_csv_file(f), ids):
        nosso[(r["politico"], r["ano"])] += r["valor"]
print("nome;ano;oficial;nosso;diferenca")
for d in deps:
    num = d["id"].split("-")[1]
    for ano in (2025, 2026):
        t = requests.get(f"https://www.camara.leg.br/deputados/{num}?ano={ano}", headers=H, timeout=60).text
        m = re.search(r"Cota parlamentar.*?<td[^>]*>Gasto</td>\s*<td[^>]*>([\d.,]+)</td>", t, re.S)
        of = br(m.group(1)) if m else None
        n = round(nosso[(d["id"], ano)], 2)
        print(f"{d['nome']};{ano};{of};{n};{None if of is None else round(n-of,2)}")

print("=== COMPARACAO MG Senado")
sens = [s for s in senado.senadores() if s["uf"] == "MG"]
ids = {s["id"] for s in sens}
for ano in (2025, 2026):
    rows = senado.parse_ceaps(requests.get(senado.CEAPS.format(ano=ano), headers=H, timeout=300).json(), ids)
    tot = defaultdict(float)
    for r in rows: tot[r["politico"]] += r["valor"]
    for s in sens:
        cod = s["id"].split("-")[1]
        t = requests.get(f"https://www6g.senado.leg.br/transparencia/sen/{cod}/?ano={ano}", headers=H, timeout=60).text
        t2 = re.sub(r"<[^>]+>", " ", t); t2 = re.sub(r"\s+", " ", t2)
        m = re.search(r"Serviços de Segurança Privada.*?Total ([\d.,]+)", t2)
        print(f"{s['nome']};{ano};{m.group(1) if m else None};{round(tot[s['id']],2)}")
