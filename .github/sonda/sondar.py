"""Sonda temporária (7): tenta de novo a chave do Portal e os arquivos da Receita. Não vai para o main."""
import sys
from pathlib import Path
sys.path.insert(0, "etl")
from sa_etl.util import _session, chave_portal, get
from sa_etl import fin_receita, renuncias

chave = chave_portal()
print("CHAVE tamanho", len(chave), "formato hex32", bool(__import__("re").fullmatch(r"[0-9a-fA-F]{32}", chave)))
for url, params in ((renuncias.API_TESTE, {"pagina": 1}),
                    ("https://api.portaldatransparencia.gov.br/api-de-dados/renuncias-valor", {"pagina": 1, "ano": 2024})):
    r = _session.get(url, params=params, timeout=120, headers={"chave-api-dados": chave, "Accept": "application/json"})
    print("PORTAL", url.rsplit("/", 1)[-1], r.status_code, r.text[:120].replace(chave, "***"))

for url in (fin_receita.URL_UF, fin_receita.URL_CNAE, fin_receita.PAGINA):
    try:
        r = get(url, tries=3, timeout=120)
        print("RECEITA", url, r.status_code, len(r.content))
    except Exception as e:
        print("RECEITA", url, "ERRO", str(e)[:150])
try:
    uf, cnae = fin_receita.baixar(Path("cache"))
    if uf:
        d = fin_receita.por_uf(uf)
        for ano in sorted(d)[-3:]:
            print("ARREC", ano, round(d[ano]["total"] / 1e9, 1), "bi até mês", d[ano]["ate_mes"])
except Exception as e:
    print("RECEITA leitura ERRO", e)
