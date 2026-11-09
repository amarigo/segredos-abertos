"""Sonda temporária: roda a comparação dos gabinetes com os dados publicados e as APIs reais (apagar antes do merge)."""
from collections import Counter
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
for ano in ("2025", "2026"):
    hoje = sum((p["por_ano"].get(ano) or {}).get("verba_gabinete") or 0 for p in pols if p["casa"] == "camara" and p.get("em_exercicio") is not False)
    fora = sum((p["por_ano"].get(ano) or {}).get("verba_gabinete") or 0 for p in pols if p["casa"] == "camara" and p.get("em_exercicio") is False)
    meses = Counter(((p["por_ano"].get(ano) or {}).get("verba_ate_mes")) for p in pols if p["casa"] == "camara" and (p["por_ano"].get(ano) or {}).get("verba_gabinete"))
    print("VERBA", ano, "no cargo hoje", round(hoje, 2), "sairam", round(fora, 2), "meses", sorted(meses.items(), key=str), flush=True)
for u in (gabinetes.URL_POP, gabinetes.URL_REND):
    d = g(u, 60)
    print("SIDRA", json.dumps(d[:2] if isinstance(d, list) else d, ensure_ascii=False), flush=True)
