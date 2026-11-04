"""Sonda temporária: onde a ALMG e o TSE publicam a foto oficial de cada deputado estadual e do governador."""
import json
import re
import sys

sys.path.insert(0, ".")
from sa_etl.util import get  # noqa: E402

B = "https://dadosabertos.almg.gov.br/api/v2"


def chaves(x, p=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from chaves(v, f"{p}.{k}")
    elif isinstance(x, list):
        for v in x[:2]:
            yield from chaves(v, p + "[]")
    else:
        yield p, x


def mostrar(url):
    print("=====", url)
    try:
        r = get(url, timeout=60)
        print("status", r.status_code, r.headers.get("content-type"))
        try:
            d = r.json()
        except Exception:  # noqa: BLE001
            t = r.text
            print("texto", len(t))
            for m in sorted(set(re.findall(r"[\"'(]([^\"'()\s]*(?:foto|Foto|\.jpg|\.jpeg|\.png)[^\"'()\s]*)", t)))[:40]:
                print("  img:", m)
            return None
        for k, v in list(chaves(d))[:80]:
            print(f"  {k} = {str(v)[:150]}")
        return d
    except Exception as e:  # noqa: BLE001
        print("ERRO", e)


d = mostrar(B + "/deputados/em_exercicio?formato=json")
ids = [str(x["id"]) for x in (d or {}).get("list", [])][:3]
for i in ids:
    mostrar(f"{B}/deputados/{i}?formato=json")
    mostrar(f"https://www.almg.gov.br/a-assembleia/deputados/deputado/?id={i}")
for u in ["https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022/fotos/foto_cand2022_MG_div.zip"]:
    try:
        import requests
        r = requests.head(u, timeout=60, allow_redirects=True)
        print("=====", u, r.status_code, r.headers.get("content-length"))
    except Exception as e:  # noqa: BLE001
        print("ERRO", u, e)
