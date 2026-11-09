"""Sonda temporária: roda a comparação dos gabinetes com os dados publicados e as APIs reais (apagar antes do merge)."""
import json, logging, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
sys.path.insert(0, "etl")
from sa_etl import gabinetes
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s", stream=sys.stdout)
S = requests.Session()
def g(u, t=40):
    t0 = time.time()
    try:
        r = S.get(u, timeout=t); print("GET", r.status_code, round(time.time() - t0, 1), "s", u, flush=True); return r.json()
    except Exception as e:
        print("ERRO", round(time.time() - t0, 1), "s", u, e, flush=True); return None
IB = "https://servicodados.ibge.gov.br/api/v3/agregados"
for t in (5436, 5429):
    m = g(f"{IB}/{t}/metadados")
    if m:
        print("== tabela", t, m.get("nome"), "|", m.get("periodicidade"), "|", m.get("nivelTerritorial", {}).get("Administrativo"), flush=True)
        for v in m.get("variaveis", [])[:8]: print("   var", v["id"], v["nome"], v.get("unidade"), flush=True)
        for c in m.get("classificacoes", []): print("   class", c["id"], c["nome"], [(x["id"], x["nome"]) for x in c.get("categorias", [])][:8], flush=True)
BASE = "https://amarigo.github.io/segredos-abertos/data"
pols = g(BASE + "/politicos.json", 120)
def det(p):
    return p["id"], g(f"{BASE}/p/{p['id']}.json", 30)
with ThreadPoolExecutor(12) as ex:
    dets = dict(ex.map(det, [p for p in pols if p["casa"] == "camara"]))
for p in pols:
    d = dets.get(p["id"])
    for a, x in p["por_ano"].items():
        r = ((d or {}).get("anos", {}).get(a) or {}).get("recursos") or {}
        if x.get("verba_gabinete"):
            x["verba_disponivel"] = r.get("verba_disponivel")
            ms = [m["mes"] for m in r.get("verba_meses") or [] if m.get("valor")]
            x["verba_ate_mes"] = max(ms) if ms else None
saida = Path(tempfile.mkdtemp()); (saida / "politicos.json").write_text(json.dumps(pols))
r = gabinetes.coletar(saida, Path(tempfile.mkdtemp()), [2025, 2026])
print("RESULTADO", json.dumps(r, ensure_ascii=False), flush=True)
