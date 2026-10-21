"""Imprime um resumo dos dados gerados, para conferência rápida no log do GitHub Actions."""
import json
import sys
from pathlib import Path

d = Path(sys.argv[1])
meta = json.loads((d / "meta.json").read_text())
pols = json.loads((d / "politicos.json").read_text())
emps = json.loads((d / "empresas.json").read_text())
vots = json.loads((d / "votacoes.json").read_text())
part = json.loads((d / "partidos.json").read_text())

print("## Resumo da coleta\n")
print(f"- Anos: {meta['anos']} · total: R$ {meta['total_gasto']:,.2f}")
print(f"- Contagens: {meta['contagens']} · médias: {meta['medias']}")
for casa in ("camara", "senado"):
    ps = [p for p in pols if p["casa"] == casa]
    print(f"- {casa}: {len(ps)} políticos, {sum(1 for p in ps if p['total'] > 0)} com gastos, "
          f"{sum(1 for p in ps if p['n_votos'] > 0)} com votos, {sum(1 for p in ps if p['posicao'] is not None)} com posição")
print("\n### Maiores gastos")
for p in sorted(pols, key=lambda p: -p["total"])[:5]:
    print(f"- {p['nome']} ({p['partido']}-{p['uf']}): R$ {p['total']:,.2f} · {p['rotulo']} · {p['campo']}")
print("\n### Empresas que mais receberam")
for e in emps[:5]:
    print(f"- {e['nome']} ({e['cnpj']}): R$ {e['total']:,.2f} · sócios: {e['tem_socios']}")
print("\n### Partidos na Câmara (posição média)")
for p in sorted((p for p in part if p["casa"] == "camara" and p["posicao"] is not None), key=lambda p: p["posicao"]):
    print(f"- {p['sigla']}: {p['posicao']:+.2f} · governo {p['alinhamento_governo']} · n={p['n']}")
print("\n### Votações recentes")
for v in vots[:5]:
    pr = v.get("proposicao") or {}
    print(f"- {v['casa']} {v['data']} {pr.get('sigla','')} {pr.get('numero','')}/{pr.get('ano','')}: sim {v['sim']} não {v['nao']}")
