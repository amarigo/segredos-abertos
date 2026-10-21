import re, sys, json
from collections import defaultdict, Counter
from pathlib import Path
import requests
sys.path.insert(0, "etl")
from sa_etl.util import read_csv_file, to_float, get_json
H = {"User-Agent": "Mozilla/5.0 SegredosAbertos"}
cache = Path("etl/.cache")
# Aécio 74646? descobrir ids
deps = {d["nome"]: d["id"] for d in get_json("https://dadosabertos.camara.leg.br/api/v2/deputados", params={"siglaUf": "MG", "itens": 100})["dados"]}
alvo = {n: str(deps[n]) for n in ("Aécio Neves", "Nikolas Ferreira", "André Janones", "Reginaldo Lopes") if n in deps}
print(alvo)
for ano in (2025, 2026):
    f = cache / f"camara-cota-{ano}.csv.zip"
    import os, time
    print("== arquivo", f, os.path.getsize(f), time.ctime(os.path.getmtime(f)))
    rows = list(read_csv_file(f))
    print("colunas", list(rows[0].keys()))
    print("max datEmissao", max((r.get("datEmissao") or "") for r in rows), "meses", sorted(Counter(r.get("numMes") for r in rows).items()))
    for nome, i in alvo.items():
        mine = [r for r in rows if (r.get("ideCadastro") or "").strip() == i]
        byname = [r for r in rows if (r.get("txNomeParlamentar") or "").strip().lower() == nome.lower()]
        s = lambda rs, k: round(sum(to_float(r.get(k)) for r in rs), 2)
        print(nome, ano, "linhas", len(mine), "por nome", len(byname),
              "liq", s(mine, "vlrLiquido"), "doc", s(mine, "vlrDocumento"), "glosa", s(mine, "vlrGlosa"),
              "restit", s(mine, "vlrRestituicao"), "liq-nome", s(byname, "vlrLiquido"),
              "negativos", s([r for r in mine if to_float(r.get("vlrLiquido")) < 0], "vlrLiquido"))
        porcat = defaultdict(float)
        for r in mine: porcat[r.get("txtDescricao")] += to_float(r.get("vlrLiquido"))
        print("   cat", {k: round(v) for k, v in porcat.items()})
        # API
        tot, mes, url, params = 0.0, defaultdict(float), f"https://dadosabertos.camara.leg.br/api/v2/deputados/{i}/despesas", {"ano": ano, "itens": 100}
        n = 0
        while url:
            d = get_json(url, params=params); params = None
            for x in d["dados"]:
                tot += x["valorLiquido"]; mes[x["mes"]] += x["valorLiquido"]; n += 1
            url = next((l["href"] for l in d["links"] if l["rel"] == "next"), None)
        csvmes = defaultdict(float)
        for r in mine: csvmes[int(to_float(r.get("numMes")))] += to_float(r.get("vlrLiquido"))
        print("   API linhas", n, "total", round(tot, 2))
        t = requests.get(f"https://www.camara.leg.br/deputados/{i}?ano={ano}", headers=H, timeout=60).text
        sec = t[t.find("Cota parlamentar"):]
        sec = sec[:sec.find("Verba de gabinete")]
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", sec))
        print("   pagina:", txt[:900])
        print("   csv por mes", {k: round(v) for k, v in sorted(csvmes.items())})
        print("   api por mes", {k: round(v) for k, v in sorted(mes.items())})
