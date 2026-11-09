"""Sonda temporária: quais buscas de notícias respondem do GitHub Actions (apagar antes do merge)."""
import json, re, sys, time, urllib.parse
import requests
UA = {"User-Agent": "Mozilla/5.0 (compatible; SegredosAbertos/0.1; +https://github.com/amarigo/segredos-abertos)"}
casos = [("PL", "4881", "2023"), ("PL", "2338", "2023"), ("PEC", "66", "2023")]
for s, n, a in casos:
    np = f"{int(n):,}".replace(",", ".")
    frases = sorted({f'"{s} {n}/{a}"', f'"{s} {np}/{a}"'})
    q = " OR ".join(frases)
    print("=====", s, n, a, q)
    for nome, url in [
        ("gdelt", "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode({"query": f"({q}) sourcelang:portuguese" if len(frases) > 1 else f"{q} sourcelang:portuguese", "mode": "artlist", "format": "json", "maxrecords": 20, "timespan": "3months"})),
        ("gdelt2", "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode({"query": f'"{s} {n}" sourcecountry:brazil', "mode": "artlist", "format": "json", "maxrecords": 20})),
        ("bing", "https://www.bing.com/news/search?" + urllib.parse.urlencode({"q": q, "format": "rss", "setlang": "pt-BR", "cc": "BR"})),
        ("google", "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q, "hl": "pt-BR", "gl": "BR", "ceid": "BR:pt-419"})),
    ]:
        try:
            r = requests.get(url, headers=UA, timeout=40)
            print(f"--- {nome} {r.status_code} {len(r.content)}b")
            print(r.text[:2500])
        except Exception as e:
            print(f"--- {nome} ERRO {e}")
        time.sleep(6)
# um artigo conhecido, para ver se a página abre para robô
for u in ["https://agenciainfra.com/blog/mme-se-opoe-a-pl-que-reduz-conta-de-luz-no-norte-com-verba-da-eletrobras/",
          "https://cenarioenergia.com.br/2025/09/18/absae-alerta-para-riscos-do-pl-4-881-2023-a-reducao-estrutural-da-tarifa-de-energia-eletrica/"]:
    try:
        r = requests.get(u, headers=UA, timeout=40)
        print("--- artigo", r.status_code, len(r.content), r.url)
        print(re.sub(r"\s+", " ", r.text)[:300])
    except Exception as e:
        print("--- artigo ERRO", e)
