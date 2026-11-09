"""Sonda temporária: roda o coletor de notícias contra com dados reais (apagar antes do merge)."""
import json, logging, sys, tempfile
from pathlib import Path
import requests
sys.path.insert(0, "etl")
from sa_etl import noticias
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
pub = requests.get("https://amarigo.github.io/segredos-abertos/data/tramitacao.json", timeout=60).json()
itens = [{"sigla": "PL", "numero": "4881", "ano": "2023"}]
itens += [i for i in pub["itens"] if "pauta" in i["grupos"] and not (i.get("debate") or {}).get("contra")
          and i["nome"] != "PL 4881/2023"][:14]
b = noticias.Buscador(Path(tempfile.mkdtemp()), minutos=12)
for it in itens:
    r = b.contra(it)
    print("=====", it["sigla"], it["numero"], it["ano"], json.dumps(r, ensure_ascii=False, indent=1))
print("fontes ok", b.fontes_ok, "falha", b.fontes_falha)
