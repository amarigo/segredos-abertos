import json, re, sys, requests
sys.path.insert(0, "etl")
H = {"User-Agent": "Mozilla/5.0 SegredosAbertos"}
def strip(t):
    t = re.sub(r"(?s)<(script|style|svg|noscript)[^>]*>.*?</\1>", "", t)
    t = re.sub(r"\s+", " ", t)
    return t

print("=== API docs paths")
d = requests.get("https://adm.senado.gov.br/adm-dadosabertos/v3/api-docs", headers=H, timeout=60).json()
for p in d["paths"]:
    print(p)

print("=== Senado page links")
t = requests.get("https://www6g.senado.leg.br/transparencia/sen/5967/?ano=2025", headers=H, timeout=60).text
for h in sorted(set(re.findall(r'href="([^"]+)"', t))):
    if any(k in h.lower() for k in ("json", "csv", "formato", "pessoal", "subsid", "remuner", "export", "cota", "lotac", "servidor")):
        print(h)

print("=== Camara main page gastos section")
t = strip(requests.get("https://www.camara.leg.br/deputados/209787?ano=2025", headers=H, timeout=60).text)
i = t.find("Gastos e recursos")
s = t[i:i+14000]
s = re.sub(r'<(\w+)[^>]*?(class="[^"]*")?[^>]*>', lambda m: f"<{m.group(1)} {m.group(2) or ''}>", s)
print(s)
