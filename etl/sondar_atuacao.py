"""TEMPORÁRIO: mostra o formato das páginas oficiais de atuação dos parlamentares."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sa_etl.recursos import _get_text, _texto  # noqa: E402

for dep, ano in [("74646", 2024), ("74646", 2025), ("74646", 2026), ("204554", 2025), ("220593", 2025), ("204536", 2023)]:
    t = _texto(_get_text(f"https://www.camara.leg.br/deputados/{dep}?ano={ano}") or "")
    i = t.find("Atuação no Plenário")
    print(f"\n=== Câmara {dep} {ano}: {t[i:i + 700] if i >= 0 else 'NÃO ACHOU ' + t[:300]}")

for u in ["https://legis.senado.leg.br/dadosabertos/processo/relatoria?codigoParlamentar=5012&dataInicio=2025-01-01&dataFim=2025-12-31",
          "https://legis.senado.leg.br/dadosabertos/processo/relatoria?codigoParlamentar=5012",
          "https://legis.senado.leg.br/dadosabertos/processo?codigoParlamentarAutor=5012&ano=2025"]:
    h = _get_text(u)
    print(f"\n=== {u}: {len(h or '')} bytes")
    try:
        d = json.loads(h or "null")
        if isinstance(d, list):
            print("itens:", len(d), "chaves:", list(d[0].keys()) if d else [])
            print("tipos:", Counter(x.get("tipoDocumento") or x.get("siglaTipoMateria") or x.get("descricaoTipoRelator") for x in d).most_common(12))
            print("exemplo:", json.dumps(d[0], ensure_ascii=False)[:800] if d else "")
        else:
            print(str(h)[:800])
    except ValueError:
        print((h or "")[:800])
h = _get_text("https://legis.senado.leg.br/dadosabertos/senador/5012/discursos.json?dataInicio=20250101&dataFim=20251231")
p = json.loads(h)["DiscursosParlamentar"]["Parlamentar"]["Pronunciamentos"]["Pronunciamento"]
print("\n=== discursos 2025:", len(p), Counter(x["TipoUsoPalavra"]["Descricao"] for x in p).most_common(8), Counter(x.get("SiglaCasaPronunciamento") for x in p))
