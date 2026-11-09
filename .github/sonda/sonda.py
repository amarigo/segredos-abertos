"""Sonda temporária: confere as APIs do IBGE e os dados publicados para a comparação justa dos gabinetes (apagar antes do merge)."""
import json, sys
import requests
S = requests.Session(); S.headers["User-Agent"] = "SegredosAbertos/0.1 (+https://github.com/amarigo/segredos-abertos)"
def g(u):
    try:
        r = S.get(u, timeout=90); print("GET", r.status_code, u); return r.json()
    except Exception as e:
        print("ERRO", u, e); return None
IB = "https://servicodados.ibge.gov.br/api/v3/agregados"
for t in (6579, 5429, 5436, 5442, 7531, 5434, 6468):
    m = g(f"{IB}/{t}/metadados")
    if m:
        print("== tabela", t, m.get("nome"), "| periodicidade", m.get("periodicidade"), "| niveis", m.get("nivelTerritorial", {}).get("Administrativo"))
        for v in m.get("variaveis", [])[:12]: print("   var", v["id"], v["nome"], v.get("unidade"))
        for c in m.get("classificacoes", []):
            print("   class", c["id"], c["nome"], [(x["id"], x["nome"]) for x in c.get("categorias", [])][:12])
d = g(f"{IB}/6579/periodos/-1/variaveis/9324?localidades=N3[all]")
if d: print(json.dumps(d, ensure_ascii=False)[:3000])
for t, v in ((5429, 5932), (5436, 5932), (5442, 5932), (7531, 10824)):
    d = g(f"{IB}/{t}/periodos/-1/variaveis/{v}?localidades=N3[all]")
    if d: print(json.dumps(d, ensure_ascii=False)[:2500])
pub = g("https://amarigo.github.io/segredos-abertos/data/politicos.json")
if pub:
    from collections import Counter
    print("politicos", len(pub), Counter((p["casa"], p.get("em_exercicio")) for p in pub))
    print("camara em exercicio por uf", sorted(Counter(p["uf"] for p in pub if p["casa"] == "camara" and p.get("em_exercicio") is not False).items()))
    for ano in ("2025", "2026"):
        s = Counter(); n = Counter()
        for p in pub:
            x = p["por_ano"].get(ano) or {}
            if p["casa"] == "camara" and x.get("verba_gabinete"): s[p["uf"]] += x["verba_gabinete"]; n[p["uf"]] += 1
        print("verba", ano, {k: round(v) for k, v in sorted(s.items())}, sum(s.values()))
    ex = [p for p in pub if p["casa"] == "camara" and p["uf"] == "SP"][0]
    print("exemplo por_ano", json.dumps(ex["por_ano"].get("2025"), ensure_ascii=False)[:800])
    q = g(f"https://amarigo.github.io/segredos-abertos/data/p/{ex['id']}.json")
    if q: print("recursos 2025", json.dumps({k: v for k, v in ((q["anos"].get("2025") or {}).get("recursos") or {}).items() if k != "equipe"}, ensure_ascii=False)[:1500])
    sen = [p for p in pub if p["casa"] == "senado"][0]
    q = g(f"https://amarigo.github.io/segredos-abertos/data/p/{sen['id']}.json")
    if q: print("senado recursos 2025", json.dumps({k: v for k, v in ((q["anos"].get("2025") or {}).get("recursos") or {}).items() if k != "equipe"}, ensure_ascii=False)[:1500])
dep = g("https://dadosabertos.camara.leg.br/api/v2/deputados?itens=1000")
if dep:
    from collections import Counter
    print("API camara em exercicio", len(dep["dados"]), sorted(Counter(x["siglaUf"] for x in dep["dados"]).items()))
