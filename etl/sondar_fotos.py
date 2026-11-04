"""Sonda temporária (2): a foto da ALMG pelo id responde para todos? O ZIP de fotos do TSE tem o governador?"""
import io
import sys
import zipfile

sys.path.insert(0, ".")
from sa_etl.util import get  # noqa: E402
import requests  # noqa: E402

B = "https://dadosabertos.almg.gov.br/api/v2"
atuais = [str(x["id"]) for x in get(B + "/deputados/em_exercicio?formato=json").json()["list"]]
print("em exercício", len(atuais))
# alguns que já saíram: arquivo de deputados (ids que não estão em exercício)
import csv  # noqa: E402
ARQ = "https://dadosabertos.almg.gov.br/arquivo/deputados/download?formato=csv"
try:
    t = get(ARQ, timeout=120).content.decode("utf-8-sig", "replace")
    linhas = list(csv.DictReader(io.StringIO(t), delimiter=";"))
    print("arquivo", len(linhas), list(linhas[0].keys()) if linhas else None)
    fora = [str(r.get("Codigo") or r.get("Código") or r.get("id")) for r in linhas if "20" in (r.get("Legislaturas") or "")]
    fora = [i for i in fora if i not in atuais][:10]
except Exception as e:  # noqa: BLE001
    print("arquivo ERRO", e)
    fora = []
print("fora", fora)
PADROES = ["https://www.almg.gov.br/a-assembleia/deputados/legislatura-atual/fotos/{id}.jpg",
           "https://www.almg.gov.br/export/sites/portal/a-assembleia/deputados/fotos/{id}.jpg"]
for nome, ids in (("atuais", atuais), ("fora", fora)):
    for p in PADROES:
        ok = 0
        ruins = []
        for i in ids:
            try:
                r = requests.get(p.format(id=i), timeout=30, headers={"User-Agent": "segredos-abertos"})
                if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/") and len(r.content) > 2000:
                    ok += 1
                else:
                    ruins.append((i, r.status_code, r.headers.get("content-type"), len(r.content)))
            except Exception as e:  # noqa: BLE001
                ruins.append((i, str(e)[:60]))
        print(nome, p, "ok", ok, "de", len(ids), "ruins", ruins[:5])

r = requests.get("https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022/fotos/foto_cand2022_MG_div.zip", timeout=300)
z = zipfile.ZipFile(io.BytesIO(r.content))
n = z.namelist()
print("zip TSE", len(n), n[:5])
