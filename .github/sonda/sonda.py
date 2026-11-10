"""Sonda temporária (5): roda o coletor de punições (etl/sa_etl/sancoes.py) com os dados publicados e as fontes reais
(apagar antes do merge)."""
import json, logging, sys, time
from pathlib import Path
import requests
sys.path.insert(0, "etl")
from sa_etl import sancoes
from sa_etl.validar import Resultado, _conferir_sancoes
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
S = requests.Session(); S.headers["User-Agent"] = "SegredosAbertos/0.1 (+https://github.com/amarigo/segredos-abertos)"
BASE = "https://amarigo.github.io/segredos-abertos/data"
saida, cache = Path("/tmp/saida"), Path("/tmp/cache")
(saida / "e").mkdir(parents=True, exist_ok=True)
pols = S.get(f"{BASE}/politicos.json", timeout=120).json()
(saida / "politicos.json").write_text(json.dumps(pols))
todas = S.get(f"{BASE}/empresas-todas.json", timeout=120).json()
print("empresas no site:", len(todas))
t0 = time.time(); n = 0
for linha in todas[:1500]:
    c = linha[0]
    try:
        r = S.get(f"{BASE}/e/{c}.json", timeout=60)
        if r.status_code == 200:
            (saida / "e" / f"{c}.json").write_text(r.text); n += 1
    except Exception as e:
        print("erro", c, e)
print("páginas de empresa baixadas:", n, f"{time.time()-t0:.0f}s")
d = sancoes.coletar(saida, cache, minutos=12)
print("FONTES", json.dumps({k: {x: v[x] for x in ("situacao", "n", "lida_em", "referencia")} for k, v in d["fontes"].items()}, ensure_ascii=False))
print("COBERTURA", d["cobertura"])
print("EMPRESAS", len(d["empresas"]), "com registro próprio", sum(1 for e in d["empresas"] if e["registros"]), "com sócio", sum(1 for e in d["empresas"] if e["socios"]))
print("POLITICOS", len(d["politicos"]))
for p in d["politicos"]:
    print("  POL", p["id"], p["nome"], p["partido"], p["uf"], [(r["cad"], r.get("tipo"), r.get("inicio"), r.get("fim"), r.get("vigente"), r.get("processo"), r.get("link")) for r in p["registros"]])
for e in d["empresas"][:40]:
    print("  EMP", e["cnpj"], e["nome"], [(r["cad"], r.get("tipo"), r.get("orgao"), r.get("inicio"), r.get("fim"), r.get("vigente")) for r in e["registros"]][:3],
          "| socios:", [(s["nome"], s["doc"], [r["cad"] for r in s["registros"]]) for s in e["socios"]][:3])
r = Resultado(); _conferir_sancoes(saida, pols, r)
print("VALIDAR erros:", r.erros[:20], "alertas:", r.alertas[:5])
print("tamanho sancoes.json:", (saida / "sancoes.json").stat().st_size)
