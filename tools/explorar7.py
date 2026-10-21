import json, requests, sys
from collections import defaultdict
sys.path.insert(0, "etl")
from sa_etl.util import to_float
H = {"User-Agent": "Mozilla/5.0 SegredosAbertos"}
rows = requests.get("https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/2025", headers=H, timeout=300).json()
print("campos", list(rows[0].keys()))
for cod in ("5967", "739"):
    mine = [r for r in rows if str(r.get("codSenador")) == cod]
    cat = defaultdict(float)
    for r in mine: cat[r.get("tipoDespesa")] += to_float(r.get("valorReembolsado"))
    print("CEAPS", cod, {k: round(v, 2) for k, v in cat.items()}, round(sum(cat.values()), 2))
    j = requests.get(f"https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/{cod}/recursos-utilizados?ano=2025", headers=H, timeout=60).json()
    print("PAGINA", cod, json.dumps(j["data"][0]["cotas"], ensure_ascii=False))
    big = sorted(mine, key=lambda r: -to_float(r.get("valorReembolsado")))[:8]
    for r in big: print("   ", {k: r.get(k) for k in ("tipoDespesa", "fornecedor", "valorReembolsado", "mes", "data", "tipoDocumento", "detalhamento")})
