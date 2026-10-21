"""Confere os links das notas fiscais: quantas notas têm link e se os links abrem.

Uso: python conferir_links.py <pasta de dados do site> <pasta de cache>
Não falha a coleta: só imprime o resultado no resumo.
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sa_etl.util import _session, read_csv_file  # noqa: E402

dados, cache = Path(sys.argv[1]), Path(sys.argv[2])
random.seed(1)

print("\n### Links das notas fiscais\n")
com, sem, exemplos = Counter(), Counter(), {}
for f in (dados / "e" / "notas").glob("*.json"):
    for data, pol, cat, valor, url in json.loads(f.read_text()):
        casa = pol.split("-")[0]
        (com if url else sem)[(casa, cat)] += 1
        if url:
            exemplos.setdefault(casa, []).append(url)
for casa in sorted({c for c, _ in com} | {c for c, _ in sem}):
    c = sum(v for (k, _), v in com.items() if k == casa)
    s = sum(v for (k, _), v in sem.items() if k == casa)
    print(f"- {casa}: {c} notas com link, {s} sem link ({100 * c / max(1, c + s):.0f}% com link)")
    for (k, cat), v in sorted(sem.items(), key=lambda kv: -kv[1])[:40]:
        if k == casa and v > 200:
            print(f"  - sem link: {cat}: {v} (com link nessa categoria: {com[(k, cat)]})")


def status(u):
    try:
        r = _session.get(u, timeout=30, allow_redirects=True, stream=True, headers={"Accept": "*/*"})
        ct = r.headers.get("content-type", "")
        r.close()
        return f"{r.status_code} {ct[:30]}"
    except Exception as e:  # noqa: BLE001
        return f"erro {type(e).__name__}"


for casa, us in exemplos.items():
    print(f"- {casa}: testando 6 links existentes")
    for u in random.sample(us, min(6, len(us))):
        print(f"  - {status(u)} · {u}")

# No arquivo da Câmara: quando urlDocumento vem vazio, o que há nas outras colunas?
for f in sorted(cache.glob("camara-cota-*.csv.zip"))[-1:]:
    rows = list(read_csv_file(f))
    vazios = [r for r in rows if not (r.get("urlDocumento") or "").strip()]
    print(f"\n- Câmara {f.name}: {len(vazios)} de {len(rows)} linhas sem urlDocumento")
    print("  - por tipo de documento (sem link):", dict(Counter(r.get("indTipoDocumento") for r in vazios)))
    print("  - por tipo de documento (todas):", dict(Counter(r.get("indTipoDocumento") for r in rows)))
    print("  - por categoria (sem link):", dict(Counter(r.get("txtDescricao") for r in vazios).most_common(8)))
    com_url = [r for r in rows if (r.get("urlDocumento") or "").strip()]
    for r in random.sample(com_url, 4):
        print("  - exemplo com link:", {k: r.get(k) for k in ("indTipoDocumento", "ideDocumento", "nuDeputadoId", "ideCadastro", "numAno", "urlDocumento")})
    for r in random.sample(vazios, min(6, len(vazios))):
        cand = [f"https://www.camara.leg.br/cota-parlamentar/documentos/publ/{r.get('nuDeputadoId')}/{r.get('numAno')}/{r.get('ideDocumento')}.pdf",
                f"https://www.camara.leg.br/cota-parlamentar/nota-fiscal-eletronica?ideDocumentoFiscal={r.get('ideDocumento')}"]
        print("  - sem link:", {k: r.get(k) for k in ("indTipoDocumento", "txtDescricao", "txtFornecedor", "ideDocumento", "txtPassageiro")})
        for u in cand:
            print(f"    - {status(u)} · {u}")
