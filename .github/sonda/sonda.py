"""Sonda temporária: formato das APIs de sanções (Portal da Transparência) e das listas do TCU (apagar antes do merge)."""
import json, os, re, sys, time
import requests
S = requests.Session(); S.headers["User-Agent"] = "SegredosAbertos/0.1 (+https://github.com/amarigo/segredos-abertos)"
bruto = os.environ.get("CHAVE", "")
ach = re.findall(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])", bruto)
CH = ach[0] if ach else bruto.strip()
print("chave presente:", bool(CH))
def g(u, params=None, headers=None, n=1500, js=True):
    try:
        t = time.time(); r = S.get(u, params=params, headers=headers, timeout=90)
        print(f"GET {r.status_code} {time.time()-t:.1f}s {r.url} ctype={r.headers.get('content-type')} len={len(r.content)}")
        if js:
            try:
                d = r.json(); print(json.dumps(d, ensure_ascii=False)[:n]); return d
            except Exception:
                print(r.text[:n]); return None
        print(r.text[:n]); return r.text
    except Exception as e:
        print("ERRO", u, e); return None
P = "https://api.portaldatransparencia.gov.br/api-de-dados"
H = {"chave-api-dados": CH, "Accept": "application/json"}
for ep in ("ceis", "cnep", "ceaf", "cepim"):
    print("=====", ep)
    d = g(f"{P}/{ep}", {"pagina": 1}, H, 3000)
    if isinstance(d, list):
        print("linhas na pagina 1:", len(d))
        for pg in (100, 400, 800, 1200, 1600, 2400, 3200):
            x = g(f"{P}/{ep}", {"pagina": pg}, H, 0)
            n = len(x) if isinstance(x, list) else None
            print("  pagina", pg, "linhas", n)
            if not n: break
# filtro por CNPJ e por CPF
g(f"{P}/ceis", {"cnpjSancionado": "00000000000191", "pagina": 1}, H, 800)
g(f"{P}/ceaf", {"cpfSancionado": "00000000191", "pagina": 1}, H, 800)
g(f"{P}/pessoa-fisica", {"cpf": "00000000191", "nis": ""}, H, 800)
print("===== TCU")
for u in ("https://contas.tcu.gov.br/ords/condenacao/consulta/inabilitados",
          "https://contas.tcu.gov.br/ords/condenacao/consulta/inidoneos",
          "https://contas.tcu.gov.br/ords/condenacao/consulta/inabilitados?offset=25&limit=25",
          "https://contas.tcu.gov.br/ords/api/publica/",
          "https://contas.tcu.gov.br/ords/condenacao/",
          "https://sites.tcu.gov.br/dados-abertos/inidoneos-irregulares/",
          "https://dadosabertos.tcu.gov.br/api/3/action/package_list",
          "https://dados.gov.br/api/publico/conjuntos-dados?nomeConjuntoDados=TCU&pagina=1",
          "https://certidoes-apf.apps.tcu.gov.br/api/rest/publico/certidoes/00000000000191?seEmitirPDF=false",
          "https://contas.tcu.gov.br/ords/f?p=1660:2"):
    t = g(u, js=False, n=2500)
    if isinstance(t, str) and "<a" in t:
        links = sorted(set(re.findall(r'href="([^"]+)"', t)))
        print("links:", [l for l in links if re.search(r"csv|json|zip|xls|api|irreg|inid|inab|eleitor", l, re.I)][:60])
print("===== Camara deputado (cpf)")
d = g("https://dadosabertos.camara.leg.br/api/v2/deputados?itens=1", n=400)
if d and d.get("dados"):
    x = g(f"https://dadosabertos.camara.leg.br/api/v2/deputados/{d['dados'][0]['id']}", n=0)
    if x: print("chaves:", list(x["dados"].keys()), "cpf presente:", bool(x["dados"].get("cpf")))
