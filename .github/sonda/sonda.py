"""Sonda temporária (2): campos do CEIS/CNEP, paginação e lista eleitoral do TCU, CPF na API da Câmara (apagar antes do merge)."""
import json, os, re, time
import requests
S = requests.Session(); S.headers["User-Agent"] = "SegredosAbertos/0.1 (+https://github.com/amarigo/segredos-abertos)"
bruto = os.environ.get("CHAVE", "")
ach = re.findall(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])", bruto)
CH = ach[0] if ach else bruto.strip()
def g(u, params=None, headers=None, n=1500, js=True, quieto=False):
    try:
        t = time.time(); r = S.get(u, params=params, headers=headers, timeout=60)
        print(f"GET {r.status_code} {time.time()-t:.1f}s {r.url} ctype={r.headers.get('content-type')} len={len(r.content)}")
        if js:
            try:
                d = r.json()
                if not quieto: print(json.dumps(d, ensure_ascii=False)[:n])
                return d
            except Exception:
                print(r.text[:n]); return None
        if not quieto: print(r.text[:n])
        return r.text
    except Exception as e:
        print("ERRO", u, e); return None
def sem_fund(x):
    return {k: v for k, v in x.items() if k != "fundamentacao"} | {"fundamentacao": [f.get("codigo", "")[:120] for f in x.get("fundamentacao") or []]}
P = "https://api.portaldatransparencia.gov.br/api-de-dados"
H = {"chave-api-dados": CH, "Accept": "application/json"}
for ep in ("ceis", "cnep"):
    d = g(f"{P}/{ep}", {"pagina": 2}, H, 0, quieto=True)
    for x in (d or [])[:3]:
        print(ep, json.dumps(sem_fund(x), ensure_ascii=False)[:2500])
    # pessoa física no CEIS? procura uma página com PF
    for pg in (300, 900):
        d = g(f"{P}/{ep}", {"pagina": pg}, H, 0, quieto=True)
        pf = [x for x in d or [] if (x.get("sancionado") or {}).get("codigoFormatado", "").startswith("***")]
        print(ep, "pagina", pg, "PF:", len(pf), "tipos:", sorted({(x.get('pessoa') or {}).get('tipo', '') for x in d or []}))
        if pf: print(json.dumps(sem_fund(pf[0]), ensure_ascii=False)[:2000])
    # limites de paginas
    lo, hi = (1200, 1600) if ep == "ceis" else (100, 400)
    while hi - lo > 1:
        m = (lo + hi) // 2
        d = g(f"{P}/{ep}", {"pagina": m}, H, 0, quieto=True)
        lo, hi = (m, hi) if d else (lo, m)
    print(ep, "ultima pagina", lo)
for ep in ("ceaf",):
    lo, hi = 100, 400
    while hi - lo > 1:
        m = (lo + hi) // 2
        d = g(f"{P}/{ep}", {"pagina": m}, H, 0, quieto=True)
        lo, hi = (m, hi) if d else (lo, m)
    print(ep, "ultima pagina", lo)
# filtros
g(f"{P}/ceis", {"codigoSancionado": "30139983000102", "pagina": 1}, H, 600)
g(f"{P}/cnep", {"codigoSancionado": "30139983000102", "pagina": 1}, H, 600)
print("===== TCU")
T = "https://contas.tcu.gov.br/ords/condenacao/consulta"
for nome in ("inabilitados", "inidoneos"):
    d = g(f"{T}/{nome}", quieto=True)
    if d:
        print(nome, "chaves", list(d.keys()), "itens", len(d.get("items", [])), {k: v for k, v in d.items() if k != "items"})
    d = g(f"{T}/{nome}", {"limit": 10000}, quieto=True)
    if d:
        print(nome, "limit 10000 -> itens", len(d.get("items", [])), {k: v for k, v in d.items() if k != "items"})
for nome in ("implicacao-eleitoral", "implicacao_eleitoral", "eleitoral", "responsaveis", "contas-irregulares", "irregulares", "lista-eleitoral", "cadirreg"):
    d = g(f"{T}/{nome}", n=600)
    if isinstance(d, dict) and d.get("items"):
        print("ACHOU", nome, len(d["items"]), {k: v for k, v in d.items() if k != "items"})
for u in ("https://certidoes.apps.tcu.gov.br/lista-implicacao-eleitoral", "https://sites.tcu.gov.br/dados-abertos/inidoneos-irregulares/dicionario-dados.html"):
    t = g(u, js=False, n=3000)
    if t:
        for s in sorted(set(re.findall(r'(?:src|href)="([^"]+\.js[^"]*)"', t)))[:10]:
            src = s if s.startswith("http") else "https://certidoes.apps.tcu.gov.br/" + s.lstrip("/")
            js = g(src, js=False, quieto=True) or ""
            print("JS", src, sorted(set(re.findall(r'https?://[a-z0-9.\-]+tcu\.gov\.br[^"\'` ]*', js)))[:30])
            print("JS rotas", sorted(set(re.findall(r'["\'`](/?(?:ords|api)[^"\'` ]{3,80})', js)))[:40])
print("===== Camara")
for i in range(3):
    d = g("https://dadosabertos.camara.leg.br/api/v2/deputados/204554", n=0, quieto=True)
    if d:
        x = d["dados"]; print("chaves:", list(x.keys()), "cpf presente:", bool(x.get("cpf")), "len", len(str(x.get("cpf") or ""))); break
    time.sleep(10)
print("===== Senado")
d = g("https://legis.senado.leg.br/dadosabertos/senador/5012.json", n=0, quieto=True)
if d: print(json.dumps(d, ensure_ascii=False)[:1500])
