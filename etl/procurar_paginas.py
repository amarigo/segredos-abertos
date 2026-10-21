"""Procura as páginas oficiais onde aparecem as despesas que não têm link de nota (passagens, telefonia, Senado)."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sa_etl.util import _session, read_csv_file  # noqa: E402


def get(u):
    try:
        r = _session.get(u, timeout=40, headers={"Accept": "text/html,application/json"})
        return r.status_code, r.text
    except Exception as e:  # noqa: BLE001
        return f"erro {type(e).__name__}", ""


def links(h, pad):
    return sorted({m for m in re.findall(r'href="([^"]+)"', h) if re.search(pad, m)})[:15]


rows = list(read_csv_file(Path("etl/.cache/camara-cota-2025.csv.zip")))
sig = next(r for r in rows if "SIGEPA" in (r.get("txtDescricao") or "") and r.get("txtPassageiro"))
tel = next(r for r in rows if r.get("txtDescricao") == "TELEFONIA" and r.get("ideDocumento") not in ("", "0"))
for nome, r in (("SIGEPA", sig), ("TELEFONIA", tel)):
    print(f"\n## Câmara {nome}:", {k: r.get(k) for k in ("ideCadastro", "nuDeputadoId", "numAno", "numMes", "numSubCota", "txtFornecedor", "txtCNPJCPF", "txtNumero", "ideDocumento", "vlrLiquido", "txtPassageiro", "txtTrecho", "datEmissao")})
    ide, nu, ano, mes, sub = r["ideCadastro"], r["nuDeputadoId"], r["numAno"], r["numMes"], r.get("numSubCota")
    valor = r["vlrLiquido"].replace(".", ",")
    for u in [f"https://www.camara.leg.br/deputados/{ide}?ano={ano}",
              f"https://www.camara.leg.br/cota-parlamentar/sumarizado?nuDeputadoId={nu}&dataInicio={int(mes):02d}/{ano}&dataFim={int(mes):02d}/{ano}&despesa=&nomeHospede=&nomePassageiro=&nomeFornecedor=&cnpjFornecedor=&numDocumento=&sguf=&filtroNivel1=1&filtroNivel2=2&filtroNivel3=3",
              f"https://www.camara.leg.br/cota-parlamentar/sumarizado?nuDeputadoId={nu}&dataInicio={int(mes):02d}/{ano}&dataFim={int(mes):02d}/{ano}",
              f"https://www.camara.leg.br/cota-parlamentar/documento?nuDeputadoId={nu}&numMes={mes}&numAno={ano}&despesa={sub}&cnpjFornecedor={r['txtCNPJCPF']}&idDocumento={r['txtNumero']}",
              f"https://www.camara.leg.br/cota-parlamentar/consulta-cota-parlamentar?ideDeputado={ide}&ano={ano}&mes={mes}",
              f"https://www.camara.leg.br/transparencia/gastos-parlamentares?legislatura=57&ano={ano}&mes={mes}&por=deputado&deputado={ide}"]:
        st, h = get(u)
        print(f"- {st} len={len(h)} valor={'SIM' if valor in h else 'não'} fornecedor={'SIM' if (r['txtFornecedor'] or '')[:12].upper() in h.upper() else 'não'} · {u[:170]}")
        print("    links:", links(h, r"cota|despesa|documento|gastos")[:10])

print("\n## Senado")
j = _session.get("https://adm.senado.gov.br/adm-dadosabertos/api/v1/senadores/despesas_ceaps/2025", timeout=300).json()
x = j[100]
print({k: x.get(k) for k in x})
cod, forn = x.get("codSenador"), (x.get("fornecedor") or "")[:12].upper()
for u in [f"https://www6g.senado.leg.br/transparencia/sen/{cod}/?ano=2025",
          f"https://www6g.senado.leg.br/transparencia/sen/{cod}/cota-parlamentar/?ano=2025",
          f"https://www6g.senado.leg.br/transparencia/sen/{cod}/ceaps/?ano=2025",
          f"https://www6g.senado.leg.br/transparencia/sen/{cod}/recursos-utilizados/?ano=2025",
          f"https://www25.senado.leg.br/web/transparencia/sen/{cod}"]:
    st, h = get(u)
    print(f"- {st} len={len(h)} fornecedor={'SIM' if forn and forn in h.upper() else 'não'} · {u}")
    print("    links:", links(h, r"ceap|cota|despesa|recurso"))
