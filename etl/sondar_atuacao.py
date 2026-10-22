"""TEMPORÁRIO: mostra o formato das páginas oficiais de atuação dos parlamentares."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sa_etl.recursos import _get_text, _texto  # noqa: E402

for dep, ano in [("204554", 2025), ("204554", 2024), ("204554", 2026), ("74646", 2025)]:
    h = _get_text(f"https://www.camara.leg.br/deputados/{dep}?ano={ano}")
    t = _texto(h or "")
    i = t.find("Propostas legislativas")
    print(f"\n=== Câmara {dep} {ano}: {len(h or '')} bytes, achou em {i}")
    print(t[max(0, i - 300):i + 900])
    j = (h or "").find("Propostas legislativas")
    print("--- html:", re.sub(r"\s+", " ", (h or "")[max(0, j - 200):j + 2500]))

for u in ["https://legis.senado.leg.br/dadosabertos/senador/5012/autorias.json",
          "https://legis.senado.leg.br/dadosabertos/senador/5012/relatorias.json",
          "https://legis.senado.leg.br/dadosabertos/senador/5012/discursos.json?dataInicio=20250101&dataFim=20251231",
          "https://legis.senado.leg.br/dadosabertos/senador/5012/votacoes.json?ano=2025",
          "https://legis.senado.leg.br/dadosabertos/processo?codigoParlamentarAutor=5012&ano=2025",
          "https://legis.senado.leg.br/dadosabertos/plenario/lista/discursos/20250301/20250331.json"]:
    h = _get_text(u)
    print(f"\n=== {u}: {len(h or '')} bytes")
    print((h or "")[:1500])
