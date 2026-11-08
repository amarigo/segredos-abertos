"""Sonda temporária da API do PNCP, 2ª rodada (o ambiente de desenvolvimento não alcança pncp.gov.br)."""
import collections
import json
import time

import requests

B = "https://pncp.gov.br/api/consulta/v1"
P = "https://pncp.gov.br/api/pncp/v1"
S = requests.Session()
S.headers["User-Agent"] = "segredos-abertos/1.0 (+https://github.com/amarigo/segredos-abertos)"
N = [0]


def get(url, mostrar=True, **params):
    for t in range(5):
        time.sleep(1.0)
        N[0] += 1
        ini = time.time()
        r = S.get(url, params=params, timeout=90)
        if r.status_code == 429:
            print("429 depois de", N[0], "pedidos; espera", 5 * (t + 1))
            time.sleep(5 * (t + 1))
            continue
        break
    if mostrar:
        print(f"\n== {r.status_code} {time.time()-ini:.1f}s {r.url}")
    if r.status_code == 204:
        return {"data": [], "totalRegistros": 0}
    try:
        return r.json()
    except ValueError:
        print(r.text[:300])
        return None


ibge = get("https://servicodados.ibge.gov.br/api/v1/localidades/estados/MG/municipios")
for m in ibge or []:
    if m["nome"] in ("Itajubá", "Paraisópolis"):
        print(m["nome"], m["id"])

# contratos de um órgão: faixa longa aceita?
for di, df in (("20250101", "20261107"), ("20260101", "20261107")):
    d = get(B + "/contratos", dataInicial=di, dataFinal=df, cnpjOrgao="18025940000109", pagina=1, tamanhoPagina=50)
    print({k: v for k, v in (d or {}).items() if k != "data"})
contratos = []
pag = 1
while True:
    d = get(B + "/contratos", mostrar=False, dataInicial="20260101", dataFinal="20261107", cnpjOrgao="18025940000109", pagina=pag, tamanhoPagina=50)
    if not d or not d.get("data"):
        break
    contratos += d["data"]
    if not d.get("paginasRestantes"):
        break
    pag += 1
print("contratos Itajubá 2026:", len(contratos))
print(collections.Counter(c["tipoContrato"]["nome"] for c in contratos))
print(collections.Counter(c.get("tipoPessoa") for c in contratos))
for c in contratos[:15]:
    print(" -", c["numeroControlePNCP"], "| compra", c.get("numeroControlePncpCompra"), "|", c.get("tipoPessoa"), c.get("niFornecedor"),
          c.get("nomeRazaoSocialFornecedor"), c.get("valorGlobal"), c.get("valorAcumulado"), c.get("dataVigenciaFim"), c["tipoContrato"]["nome"])

# compras do município (todas as modalidades) e quantas têm contrato
compras = []
for mod in range(1, 15):
    pag = 1
    while True:
        d = get(B + "/contratacoes/publicacao", mostrar=False, dataInicial="20260101", dataFinal="20261107", codigoModalidadeContratacao=mod,
                uf="MG", codigoMunicipioIbge="3132404", pagina=pag, tamanhoPagina=50)
        if not d or not d.get("data"):
            break
        compras += [x for x in d["data"] if x["orgaoEntidade"]["esferaId"] == "M"]
        if not d.get("paginasRestantes"):
            break
        pag += 1
print("\ncompras municipais em Itajubá 2026:", len(compras), "pedidos até agora:", N[0])
print(collections.Counter((x["orgaoEntidade"]["razaoSocial"], x["modalidadeNome"]) for x in compras))
print(collections.Counter(x["situacaoCompraNome"] for x in compras))
print(collections.Counter(x["amparoLegal"]["nome"] for x in compras).most_common(15))
ids = {c.get("numeroControlePncpCompra") for c in contratos}
com = [x for x in compras if x["numeroControlePNCP"] in ids]
print("compras com contrato:", len(com), "sem contrato:", len(compras) - len(com))
print("emendaParlamentar:", collections.Counter(str(x.get("emendaParlamentar")) for x in compras))
sem = [x for x in compras if x["numeroControlePNCP"] not in ids and x.get("valorTotalHomologado")]
for x in sem[:2]:
    c, ano, seq = x["orgaoEntidade"]["cnpj"], x["anoCompra"], x["sequencialCompra"]
    it = get(f"{P}/orgaos/{c}/compras/{ano}/{seq}/itens", pagina=1, tamanhoPagina=50)
    print("itens:", len(it or []), json.dumps((it or [None])[0], ensure_ascii=False)[:1500])
    if it:
        r = get(f"{P}/orgaos/{c}/compras/{ano}/{seq}/itens/{it[0]['numeroItem']}/resultados")
        print("resultado:", json.dumps(r, ensure_ascii=False)[:1500])
# resultados de uma compra inteira de uma vez?
if sem:
    x = sem[0]
    c, ano, seq = x["orgaoEntidade"]["cnpj"], x["anoCompra"], x["sequencialCompra"]
    print(json.dumps(get(f"{P}/orgaos/{c}/compras/{ano}/{seq}/resultados"), ensure_ascii=False)[:800])

# estado: um mês de dispensas, quantas são do estado (esfera E)
tot = collections.Counter()
pag = 1
while pag < 400:
    d = get(B + "/contratacoes/publicacao", mostrar=False, dataInicial="20261001", dataFinal="20261031", codigoModalidadeContratacao=6,
            uf="MG", pagina=pag, tamanhoPagina=50)
    if not d or not d.get("data"):
        break
    tot.update(x["orgaoEntidade"]["esferaId"] for x in d["data"])
    if pag == 1:
        print("pregões MG out/2026:", d.get("totalRegistros"), d.get("totalPaginas"))
    if not d.get("paginasRestantes"):
        break
    pag += 1
print("pregões MG out/2026 por esfera:", tot, "pedidos:", N[0])
# faixa de datas longa no estado é aceita?
d = get(B + "/contratacoes/publicacao", dataInicial="20250101", dataFinal="20261107", codigoModalidadeContratacao=9, uf="MG", pagina=1, tamanhoPagina=50)
print({k: v for k, v in (d or {}).items() if k != "data"})
