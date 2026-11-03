"""Sonda TEMPORÁRIA (sai antes do merge): lê a API real do Transferegov e mostra o que veio, para conferir o coletor."""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sa_etl import transferegov  # noqa: E402
from sa_etl.util import get_json  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
for nome, caminho in transferegov.CAMINHO.items():
    try:
        d = get_json(f"{transferegov.API}/{caminho}", params={"pagina": 1, "tamanho_da_pagina": 1}, timeout=90, tries=2)
        x = (d.get("data") or [{}])[0]
        print(f"## {nome}: total {d.get('total_items')}; colunas que faltam: {[c for c in transferegov.CAMPOS[nome] if c not in x]}")
        print(json.dumps({k: x.get(k) for k in transferegov.CAMPOS[nome]}, ensure_ascii=False)[:900])
    except Exception as e:  # noqa: BLE001
        print(f"## {nome}: ERRO {e}")
saida = Path(sys.argv[1])
res = transferegov.executar([2025, 2026], Path(sys.argv[2]), saida, minutos=float(sys.argv[3]))
for ano in (2025, 2026):
    f = saida / "emendas" / "destino" / f"{ano}.json"
    if not f.exists():
        print(f"## {ano}: sem arquivo")
        continue
    d = json.loads(f.read_text())
    print(f"## {ano}: {d['n']} emendas, {len(d['beneficiarios'])} entes, valor {d['valor']:.0f}, gasto {d['gasto']:.0f} em {d['n_gastos']} pagamentos, completo={d['completo']}")
    print("códigos de emenda (amostra):", list(d["emendas"])[:5])
    for b in d["beneficiarios"][:3]:
        det = json.loads((saida / "emendas" / "destino" / str(ano) / f"{b['cnpj']}.json").read_text())
        p = det["planos"][0]
        print(json.dumps({**{k: b[k] for k in ("nome", "uf", "valor", "gasto", "n_gastos")}, "plano": {k: p[k] for k in ("plano", "emenda", "parlamentar", "objeto", "valor", "gasto")},
                          "exec": p["executores"][:1], "gastos": p["gastos"][:3], "recebedores": det["recebedores"][:3]}, ensure_ascii=False)[:1500])
