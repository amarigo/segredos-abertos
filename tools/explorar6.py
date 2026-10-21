import re, html, requests
H = {"User-Agent": "Mozilla/5.0 SegredosAbertos"}
def txt(h):
    h = re.sub(r"(?s)<(script|style|svg)[^>]*>.*?</\1>", " ", h); h = re.sub(r"<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(h))
base = "https://www.camara.leg.br/cota-parlamentar/consulta-cota-parlamentar?ideDeputado=209787&dataInicio=082025&dataFim=082025"
r = requests.get(base, headers=H, timeout=60).text
i = r.find("Resultado da pesquisa")
seg = r[i:i+15000]
seg = re.sub(r"(?s)<(script|style|svg)[^>]*>.*?</\1>", " ", seg)
print(re.sub(r"\s+", " ", seg)[:9000])
for extra in ["&agrupamento=tipoDespesa", "&agrupamento=TIPO_DESPESA", "&agrupamentoNivel1=tipoDespesa"]:
    t = txt(requests.get(base + extra, headers=H, timeout=60).text)
    j = t.find("Resultado da pesquisa"); print("=====", extra, t[j:j+1500])
