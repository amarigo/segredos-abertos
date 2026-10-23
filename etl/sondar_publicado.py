"""Sonda temporária: lê os dados publicados e mostra quantos autores de emendas ficaram sem partido."""
import json
import urllib.request

BASE = "https://amarigo.github.io/segredos-abertos/data/"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.load(r)


anos = get("emendas/anos.json")
print("anos.json:", json.dumps(anos)[:300])
lista = anos.get("anos") if isinstance(anos, dict) else anos
for item in lista or []:
    ano = item.get("ano") if isinstance(item, dict) else item
    d = get(f"emendas/{ano}.json")
    sp = d.get("sem_partido") or {}
    print(f"Emendas {ano}: {len(d.get('autores') or [])} autores, {sp.get('n')} sem partido identificado, "
          f"R$ {sp.get('empenhado')} empenhados; nomes: {sp.get('nomes')}")
