"""Sonda temporária (4): lista eleitoral do TCU (POST) e páginas de detalhe das sanções no Portal (apagar antes do merge)."""
import json, re, subprocess, time
import requests
S = requests.Session(); S.headers["User-Agent"] = "SegredosAbertos/0.1 (+https://github.com/amarigo/segredos-abertos)"
def p(u, params=None, body=None, n=1500):
    try:
        t = time.time(); r = S.post(u, params=params, json=body if body is not None else {}, timeout=60, headers={"Accept": "application/json"})
        print(f"POST {r.status_code} {time.time()-t:.1f}s {r.url} ctype={r.headers.get('content-type')} len={len(r.content)}")
        print(r.text[:n]); return r
    except Exception as e:
        print("ERRO", u, e)
for base in ("https://certidoes.apps.tcu.gov.br/api/publico", "https://certidoes-apf.apps.tcu.gov.br/api/publico"):
    try:
        r = S.get(f"{base}/eleicoes/anos", timeout=60); print("GET", r.status_code, r.url, r.text[:300])
        r = S.get(f"{base}/eleicoes/ultimoAno", timeout=60); print("GET", r.status_code, r.url, r.text[:300])
    except Exception as e:
        print("ERRO", e)
    p(f"{base}/responsaveis-fins-eleitorais-com-paginacao", {"paginaAtual": 1, "tamanhoPagina": 3, "anoEleicao": 2026})
    p(f"{base}/responsaveis-contas-irregulares-com-paginacao", {"paginaAtual": 1, "tamanhoPagina": 3})
    p(f"{base}/responsaveis-inabilitados-com-paginacao", {"paginaAtual": 1, "tamanhoPagina": 2})
    r = p(f"{base}/responsaveis-fins-eleitorais-com-paginacao", {"paginaAtual": 1, "tamanhoPagina": 50000, "anoEleicao": 2026}, n=0)
    if r is not None and r.status_code == 200:
        try:
            d = r.json(); print("chaves", list(d.keys()) if isinstance(d, dict) else type(d), {k: v for k, v in d.items() if not isinstance(v, list)} if isinstance(d, dict) else "")
            itens = next((v for v in d.values() if isinstance(v, list)), []) if isinstance(d, dict) else d
            print("itens", len(itens)); print(json.dumps(itens[:2], ensure_ascii=False)[:1500])
        except Exception as e:
            print("ERRO json", e)
print("===== páginas do Portal no Chrome")
for u in ("https://portaldatransparencia.gov.br/sancoes/ceis/115050", "https://portaldatransparencia.gov.br/sancoes/cnep/405977",
          "https://portaldatransparencia.gov.br/sancoes/ceaf/141911", "https://portaldatransparencia.gov.br/sancoes/ceis?cpfCnpj=23984553000121",
          "https://portaldatransparencia.gov.br/pessoa-juridica/23984553000121"):
    try:
        out = subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=15000", "--dump-dom", u],
                             capture_output=True, text=True, timeout=90).stdout
        tit = re.search(r"<title>(.*?)</title>", out, re.S)
        txt = re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", " ", out, flags=re.S))
        txt = re.sub(r"\s+", " ", txt)
        print("CHROME", u, "| title:", (tit.group(1).strip() if tit else "")[:120], "| len", len(out))
        for k in ("ALEXANDRE AUGUSTO", "ATUANTE", "MARIA DE FATIMA", "F3C", "Sanç", "Human", "404", "não encontrad"):
            i = txt.find(k)
            if i >= 0: print("   ", k, "::", txt[max(0, i-150):i+250])
    except Exception as e:
        print("ERRO chrome", u, e)
