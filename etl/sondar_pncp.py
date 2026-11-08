"""Sonda temporária do PNCP, 3ª rodada: roda o coletor de verdade (mg_etl.pncp) por 10 minutos e mostra o resultado."""
import collections
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mg" / "etl"))
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from mg_etl import cidades, pncp, siconfi  # noqa: E402
from sa_etl import util  # noqa: E402

cache, saida = Path("/tmp/cache"), Path("/tmp/saida")
for c in cidades.CIDADES:
    print(c["nome"], siconfi.codigo_ibge(c["nome"], c["uf"], cache))
t = time.time()
print(pncp.coletar(saida, cache, cidades.CIDADES, minutos=12))
print("tempo", round(time.time() - t), "s; avisos", util.AVISOS)
print(json.dumps(json.loads((saida / "licitacoes" / "index.json").read_text()), ensure_ascii=False, indent=1))
for f in sorted((saida / "licitacoes").glob("*-*.json")):
    d = json.loads(f.read_text())
    print("\n#####", f.name, f.stat().st_size, "bytes")
    print({k: d[k] for k in ("completo", "faltam", "total")})
    print("formas", d["por_forma"])
    print("andamento", d["por_andamento"])
    print("orgaos", [(o["nome"], o["n"], o["valor"]) for o in d["orgaos"][:8]])
    print("fornecedores", [(o["nome"], o["cnpj"], o["n"], o["valor"]) for o in d["fornecedores"][:10]])
    print("amparos", [(o["nome"], o["n"], o["valor"]) for o in d["amparos"][:6]])
    com = [c for c in d["compras"] if c["contratos"]]
    print("compras na lista", len(d["compras"]), "com contrato", len(com))
    for c in d["compras"][:3] + com[:3]:
        print(json.dumps(c, ensure_ascii=False)[:900])
# contratos: datas são de publicação ou assinatura? quantos órgãos estaduais?
cs = [json.loads(__import__("gzip").decompress(f.read_bytes())) for f in (cache / "pncp").glob("contratos-*")]
print("arquivos de contratos", len(cs), "contratos", sum(len(x["linhas"]) for x in cs))
print(collections.Counter(x["assinatura"][:4] for c in cs for x in c["linhas"]))
