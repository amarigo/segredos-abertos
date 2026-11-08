"""Sonda temporária da API do PNCP (o ambiente de desenvolvimento não alcança pncp.gov.br; o GitHub Actions sim)."""
import json
import time

import requests

B = "https://pncp.gov.br/api/consulta/v1"
P = "https://pncp.gov.br/api/pncp/v1"
S = requests.Session()
S.headers["User-Agent"] = "segredos-abertos/1.0 (+https://github.com/amarigo/segredos-abertos)"


def get(url, **params):
    t = time.time()
    try:
        r = S.get(url, params=params, timeout=90)
    except Exception as e:  # noqa: BLE001
        print("ERRO", url, params, e)
        return None
    print(f"\n== {r.status_code} {time.time()-t:.1f}s {r.url}")
    try:
        d = r.json()
    except ValueError:
        print(r.text[:500])
        return None
    return d


def resumo(d, n=1):
    if d is None:
        return
    if isinstance(d, dict):
        print({k: v for k, v in d.items() if k != "data"})
        lista = d.get("data") or []
    else:
        lista = d
        print("lista", len(lista))
    for x in lista[:n]:
        print(json.dumps(x, ensure_ascii=False, indent=1)[:4000])


for ibge in ("3132404", "3147402"):
    for mod in (8, 6, 9):
        d = get(B + "/contratacoes/publicacao", dataInicial="20260101", dataFinal="20261107",
                codigoModalidadeContratacao=mod, uf="MG", codigoMunicipioIbge=ibge, pagina=1, tamanhoPagina=50)
        resumo(d, 1 if mod == 8 else 0)
        if d and d.get("data"):
            for x in d["data"][:50]:
                print(" -", x["unidadeOrgao"].get("municipioNome"), x["orgaoEntidade"].get("cnpj"), x["orgaoEntidade"].get("razaoSocial"),
                      x["orgaoEntidade"].get("esferaId"), x.get("modalidadeNome"), x.get("situacaoCompraNome"),
                      x.get("valorTotalEstimado"), x.get("valorTotalHomologado"), (x.get("objetoCompra") or "")[:60])

# volume do estado: um dia, por modalidade
for mod in (4, 5, 6, 7, 8, 9, 12, 14):
    d = get(B + "/contratacoes/publicacao", dataInicial="20261103", dataFinal="20261103",
            codigoModalidadeContratacao=mod, uf="MG", pagina=1, tamanhoPagina=50)
    resumo(d, 0)
# tamanho de página maior
resumo(get(B + "/contratacoes/publicacao", dataInicial="20261103", dataFinal="20261103",
           codigoModalidadeContratacao=8, uf="MG", pagina=1, tamanhoPagina=500), 0)

# contratos: volume nacional de um dia e de um órgão
d = get(B + "/contratos", dataInicial="20261103", dataFinal="20261103", pagina=1, tamanhoPagina=50)
resumo(d, 1)
d = get(B + "/contratacoes/publicacao", dataInicial="20260101", dataFinal="20261107",
        codigoModalidadeContratacao=8, uf="MG", codigoMunicipioIbge="3132404", pagina=1, tamanhoPagina=50)
cnpjs = sorted({x["orgaoEntidade"]["cnpj"] for x in (d or {}).get("data") or []})
print("CNPJs Itajubá", cnpjs)
for c in cnpjs[:3]:
    dc = get(B + "/contratos", dataInicial="20260101", dataFinal="20261107", cnpjOrgao=c, pagina=1, tamanhoPagina=50)
    resumo(dc, 1)
    for x in ((dc or {}).get("data") or [])[:20]:
        print(" -", x.get("numeroControlePncpCompra"), x.get("tipoPessoa"), x.get("nomeRazaoSocialFornecedor"), x.get("valorGlobal"),
              x.get("dataVigenciaFim"), (x.get("objetoContrato") or "")[:60])
# itens e resultados de uma compra
if d and d.get("data"):
    x = d["data"][0]
    c, ano, seq = x["orgaoEntidade"]["cnpj"], x["anoCompra"], x["sequencialCompra"]
    it = get(f"{P}/orgaos/{c}/compras/{ano}/{seq}/itens", pagina=1, tamanhoPagina=50)
    resumo(it, 1)
    resumo(get(f"{P}/orgaos/{c}/compras/{ano}/{seq}/itens/1/resultados"), 1)
    resumo(get(f"{P}/orgaos/{c}/compras/{ano}/{seq}"), 0)
    print(json.dumps(get(f"{P}/orgaos/{c}/compras/{ano}/{seq}"), ensure_ascii=False)[:3000])
# atas
resumo(get(B + "/atas", dataInicial="20261001", dataFinal="20261107", cnpj=cnpjs[0] if cnpjs else "", pagina=1, tamanhoPagina=10), 1)
