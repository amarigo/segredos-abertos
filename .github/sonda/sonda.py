"""Sonda temporária (3): lista eleitoral e de contas irregulares do TCU, CPF na API da Câmara, links do Portal (apagar antes do merge)."""
import json, re, time
import requests
S = requests.Session(); S.headers["User-Agent"] = "SegredosAbertos/0.1 (+https://github.com/amarigo/segredos-abertos)"
def g(u, params=None, n=1500, quieto=False, **kw):
    try:
        t = time.time(); r = S.get(u, params=params, timeout=60, **kw)
        print(f"GET {r.status_code} {time.time()-t:.1f}s {r.url} ctype={r.headers.get('content-type')} len={len(r.content)}")
        try:
            d = r.json()
            if not quieto: print(json.dumps(d, ensure_ascii=False)[:n])
            return d
        except Exception:
            if not quieto: print(r.text[:n])
            return r.text
    except Exception as e:
        print("ERRO", u, e); return None
js = g("https://certidoes.apps.tcu.gov.br/assets/index-BYlpM_Uj.js", quieto=True) or ""
if not isinstance(js, str) or len(js) < 1000:
    html = g("https://certidoes.apps.tcu.gov.br/lista-implicacao-eleitoral", quieto=True) or ""
    m = re.search(r'src="(/assets/index-[^"]+\.js)"', html); js = g("https://certidoes.apps.tcu.gov.br" + m.group(1), quieto=True) if m else ""
for k in ("responsaveis-fins-eleitorais-com-paginacao", "responsaveis-contas-irregulares-com-paginacao", "responsaveis-inabilitados-com-paginacao", "eleicoes/anos", "exportar-para-csv", "baseURL", "certidoes-apf"):
    for m in list(re.finditer(re.escape(k), js))[:2]:
        print("==", k, "::", js[max(0, m.start()-700):m.start()+500].replace("\n", " "))
A = "https://certidoes-apf.apps.tcu.gov.br/api/publico"
g(f"{A}/eleicoes/anos"); g(f"{A}/eleicoes/ultimoAno")
for nome in ("responsaveis-fins-eleitorais-com-paginacao", "responsaveis-contas-irregulares-com-paginacao", "responsaveis-inabilitados-com-paginacao", "responsaveis-inidoneos-com-paginacao"):
    for p in ({}, {"pagina": 0, "tamanhoPagina": 5}, {"page": 0, "size": 5}, {"numeroPagina": 1, "quantidadeRegistros": 5}):
        g(f"{A}/{nome}", p, n=1200)
print("===== Camara")
for i in range(4):
    d = g("https://dadosabertos.camara.leg.br/api/v2/deputados/204554", quieto=True, headers={"Accept": "application/json"})
    if isinstance(d, dict):
        x = d["dados"]; print("chaves:", list(x.keys()), "cpf len", len(str(x.get("cpf") or "")), "nomeCivil", x.get("nomeCivil")); break
    time.sleep(20)
print("===== links do Portal")
for u in ("https://portaldatransparencia.gov.br/sancoes/ceis/115050", "https://portaldatransparencia.gov.br/sancoes/cnep/405977",
          "https://portaldatransparencia.gov.br/sancoes/ceaf/141911", "https://portaldatransparencia.gov.br/sancoes/consulta?cadastro=1",
          "https://pesquisa.apps.tcu.gov.br/documento/acordao-completo/*/NUMACORDAO%253A738%2520ANOACORDAO%253A2022%2520COLEGIADO%253A%2522Plen%25C3%25A1rio%2522/DTRELEVANCIA%2520desc%252C%2520NUMACORDAOINT%2520desc/0/%2520"):
    t = g(u, quieto=True, headers={"Accept": "text/html", "User-Agent": "Mozilla/5.0"})
    if isinstance(t, str):
        m = re.search(r"<title>(.*?)</title>", t, re.S); print("   title:", (m.group(1).strip() if m else "")[:150], "| tem 115050:", "115050" in t)
