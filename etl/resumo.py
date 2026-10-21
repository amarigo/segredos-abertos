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
print(f"- Contagens: {meta['contagens']}")
for ano, t in meta.get("total_por_ano", {}).items():
    print(f"- {ano}: cota R$ {t:,.2f} · custo conhecido R$ {meta['custo_por_ano'].get(ano, 0):,.2f} · médias {meta['medias'].get(ano)}")

print("\n### Conferência com as páginas oficiais (cota)\n")
for ano in meta.get("total_por_ano", {}):
    for casa in ("camara", "senado"):
        com = [p for p in pols if p["casa"] == casa and (p["por_ano"].get(ano) or {}).get("cota_oficial") is not None]
        comp = lambda a: a["total"] - (a.get("fora_do_periodo") or 0)  # noqa: E731 - só os meses que a página mostra
        dif = [p for p in com if abs(p["por_ano"][ano]["cota_oficial"] - comp(p["por_ano"][ano])) > max(50, 0.005 * abs(comp(p["por_ano"][ano])))]
        fora = sum(1 for p in com if p["por_ano"][ano].get("fora_do_periodo"))
        rec = sum(1 for p in pols if p["casa"] == casa and (p["por_ano"].get(ano) or {}).get("salario"))
        print(f"- {ano} {casa}: {len(com)} com valor oficial, {len(dif)} diferentes, {fora} com notas fora dos meses oficiais, {rec} com salário")
        for p in sorted(dif, key=lambda p: -abs(p["por_ano"][ano]["cota_oficial"] - comp(p["por_ano"][ano])))[:3]:
            a = p["por_ano"][ano]
            print(f"  - {p['nome']} ({p['uf']}): oficial R$ {a['cota_oficial']:,.2f} · notas R$ {a['total']:,.2f}"
                  f" · fora dos meses oficiais R$ {a.get('fora_do_periodo') or 0:,.2f}")
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
print("\n### Sócios que são empresas (holdings)")
from collections import Counter
tipos, amostra, com_holding = Counter(), [], 0
for e in emps:
    f = d / "e" / f"{e['cnpj']}.json"
    if not f.exists():
        continue
    x = json.loads(f.read_text())
    com_holding += bool(x.get("donos_finais"))
    for s in x.get("socios", []):
        tipos[s.get("tipo") or "?"] += 1
    for dono in (x.get("donos_finais") or [])[:2]:
        if dono["cadeia"] and len(amostra) < 8:
            amostra.append(" → ".join([x["nome"]] + [c["nome"] for c in dono["cadeia"]] + [dono["nome"]]) + f" ({dono['fim']})")
print(f"- Sócios por tipo (1000 maiores empresas): {dict(tipos)} · empresas com donos finais via holding: {com_holding}")
for a in amostra:
    print(f"  - {a}")
print("\n### Partidos na Câmara (posição média)")
for p in sorted((p for p in part if p["casa"] == "camara" and p["posicao"] is not None), key=lambda p: p["posicao"]):
    print(f"- {p['sigla']}: {p['posicao']:+.2f} · governo {p['alinhamento_governo']} · n={p['n']}")
print("\n### Votações recentes")
for v in vots[:5]:
    pr = v.get("proposicao") or {}
    print(f"- {v['casa']} {v['data']} {pr.get('sigla','')} {pr.get('numero','')}/{pr.get('ano','')}: sim {v['sim']} não {v['nao']}")
