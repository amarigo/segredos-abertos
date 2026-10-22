"""Sonda temporária 3: contagens de autoria com os dados reais."""
import logging, statistics, sys
from pathlib import Path
sys.path.insert(0, "etl")
from sa_etl import autorias, camara, senado

logging.basicConfig(level=logging.INFO)
deps, sens = camara.deputados(), senado.senadores()
print("deputados", len(deps), "senadores", len(sens))
pols = deps + sens
nome = {p["id"]: f'{p["nome"]} ({p["partido"]}-{p.get("uf","")})' for p in pols}
aut = autorias.coletar(pols, [2025, 2026], Path("/tmp/cache-aut"))
for casa, pref in (("camara", "dep-"), ("senado", "sen-")):
    for ano in (2025, 2026):
        linhas = {pid: a[ano] for pid, a in aut.items() if pid.startswith(pref) and ano in a}
        print(f"\n== {casa} {ano}: {len(linhas)} parlamentares com contagem")
        for m in ("projetos", "projetos_apoio", "requerimentos"):
            v = sorted(x[m] for x in linhas.values())
            if not v:
                continue
            top = sorted(linhas.items(), key=lambda kv: -kv[1][m])[:4]
            print(f"  {m}: mediana {statistics.median(v)} · p90 {v[int(.9*len(v))]} · máx {v[-1]} · zeros {sum(1 for x in v if x == 0)}")
            print("     maiores:", "; ".join(f"{nome.get(k, k)} {c[m]}" for k, c in top))
for pid, n in nome.items():
    if "Eunício" in n or "Flávio Bolsonaro" in n or "Tabata" in n or "Nikolas" in n:
        print(pid, n, aut.get(pid))
