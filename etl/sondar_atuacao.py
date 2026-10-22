"""TEMPORÁRIO: confere os maiores números de atuação da Câmara na página oficial."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sa_etl import recursos as R  # noqa: E402

regs = []
for f in Path("etl/.cache/recursos").glob("dep-*-v3.json"):
    a = (json.loads(f.read_text()) or {}).get("atuacao") or {}
    pid, ano = f.stem.split("-")[1], int(f.stem.split("-")[2])
    regs.append((pid, ano, a))
print("arquivos:", len(regs))
for k in ("autoria", "relatadas"):
    top = sorted((r for r in regs if r[2].get(k) is not None), key=lambda r: -r[2][k])
    print(f"\n{k}: maiores", [(p, a, x.get(k), x.get("autoria"), x.get("relatadas")) for p, a, x in top[:8]])
    vs = sorted(r[2][k] for r in regs if r[2].get(k) is not None)
    print(f"{k}: percentis", [vs[int(len(vs) * q)] for q in (0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99)])
alvos = sorted((r for r in regs if r[2].get("relatadas") is not None), key=lambda r: -r[2]["relatadas"])[:3]
alvos += sorted((r for r in regs if r[2].get("autoria") is not None), key=lambda r: -r[2]["autoria"])[:2]
alvos += [r for r in regs if r[2].get("autoria") and 150 < r[2]["autoria"] < 300][:2]
for pid, ano, a in alvos:
    h = R._get_text(R.CAMARA.format(id=pid, sub="", ano=ano))
    t = R._texto(h or "")
    i = t.find("Atuação no Plenário e Comissões")
    print(f"\n=== {pid} {ano} {a}\n{t[max(0, i - 300):i + 900]}")
