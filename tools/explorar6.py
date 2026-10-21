import re, html, sys, requests
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, "etl")
from sa_etl.util import read_csv_file, to_float
H = {"User-Agent": "Mozilla/5.0 SegredosAbertos"}
def txt(h):
    h = re.sub(r"(?s)<(script|style|svg)[^>]*>.*?</\1>", " ", h); h = re.sub(r"<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(h))
rows = list(read_csv_file(Path("etl/.cache/camara-cota-2025.csv.zip")))
for dep, nu in (("209787", "3605"),):
    for mes in (7, 8, 9):
        u = (f"https://www.camara.leg.br/cota-parlamentar/sumarizado?nuDeputadoId={nu}&dataInicio={mes}/2025&dataFim={mes}/2025"
             "&despesa=&nomeHospede=&nomePassageiro=&nomeFornecedor=&cnpjFornecedor=&numDocumento=&sguf=&filtroNivel1=1&filtroNivel2=2&filtroNivel3=3")
        r = ""
        for _ in range(4):
            try:
                r = requests.get(u, headers=H, timeout=60).text; break
            except Exception as e:
                print("falha", e)
        t = txt(r); i = t.find("Resultado da pesquisa"); j = t.find("Filtros aplicados")
        print("===== PAGINA mes", mes, t[i:j][:2500])
        links = re.findall(r'href="(/cota-parlamentar/[^"]+)"', r)
        print("links", [html.unescape(l)[:200] for l in links[:6]])
        cat = defaultdict(float)
        for x in rows:
            if x.get("ideCadastro") == dep and x.get("numMes") == str(mes):
                cat[x["txtDescricao"]] += to_float(x["vlrLiquido"])
        print("CSV mes", mes, {k: round(v, 2) for k, v in cat.items()})
    # documentos: abrir o primeiro link de detalhe
    if links:
        u = "https://www.camara.leg.br" + html.unescape(links[-1]).replace(" ", "")
        t = txt(requests.get(u, headers=H, timeout=60).text); i = t.find("Resultado"); print("===== DETALHE", u, t[i:i+3000])
