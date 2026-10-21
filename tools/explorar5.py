import re, sys, json, html
import requests
H = {"User-Agent": "Mozilla/5.0 SegredosAbertos"}
def txt(h):
    h = re.sub(r"(?s)<(script|style|svg)[^>]*>.*?</\1>", " ", h); h = re.sub(r"<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(h))
t = requests.get("https://www.camara.leg.br/deputados/209787?ano=2025", headers=H, timeout=60).text
links = sorted(set(re.findall(r'href="([^"]*(?:gastos|cota|transparencia)[^"]*)"', t)))
print("LINKS", links)
for u in links[:6]:
    u = html.unescape(u if u.startswith("http") else "https://www.camara.leg.br" + u)
    r = requests.get(u, headers=H, timeout=60); print("=====", u, r.status_code); print(txt(r.text)[:5000])
for q in ["ano=2025&mes=8", "ano=2025&mes=8&itens=100&ordem=ASC&ordenarPor=dataDocumento", "ano=2026"]:
    r = requests.get(f"https://dadosabertos.camara.leg.br/api/v2/deputados/209787/despesas?{q}", headers={**H, "Accept": "application/json"}, timeout=60)
    print("API", q, r.status_code, r.text[:1500])
