"""Confere os links das notas fiscais: quantas notas têm link, de que tipo, e se os links abrem.

Uso: python conferir_links.py <pasta de dados do site> <pasta de cache>
Não falha a coleta: só imprime o resultado no resumo.
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sa_etl import passagens  # noqa: E402
from sa_etl.camara import LISTA_MES  # noqa: E402
from sa_etl.recursos import _get_text  # noqa: E402
from sa_etl.util import _session, read_csv_file  # noqa: E402

dados, cache = Path(sys.argv[1]), Path(sys.argv[2])
random.seed(1)

print("\n### Links das notas fiscais\n")
tipos, sem, exemplos = Counter(), Counter(), {}
for f in (dados / "e" / "notas").glob("*.json"):
    for n in json.loads(f.read_text()):
        pol, cat, url = n[1], n[2], n[4]
        link = n[5] if len(n) > 5 else ("nota" if url else "")
        casa = pol.split("-")[0]
        tipos[(casa, link or "sem link")] += 1
        if not url:
            sem[(casa, cat)] += 1
        else:
            exemplos.setdefault((casa, link), []).append(url)
for casa in sorted({c for c, _ in tipos}):
    tot = sum(v for (c, _), v in tipos.items() if c == casa)
    partes = ", ".join(f"{t}: {v} ({100 * v / tot:.0f}%)" for (c, t), v in sorted(tipos.items()) if c == casa)
    print(f"- {casa}: {tot} notas · {partes}")
    for (c, cat), v in sorted(sem.items(), key=lambda kv: -kv[1])[:10]:
        if c == casa:
            print(f"  - sem link: {cat}: {v}")


def status(u):
    try:
        r = _session.get(u, timeout=30, allow_redirects=True, stream=True, headers={"Accept": "*/*"})
        ct = r.headers.get("content-type", "")
        r.close()
        return f"{r.status_code} {ct[:30]}"
    except Exception as e:  # noqa: BLE001
        return f"erro {type(e).__name__}"


for (casa, link), us in sorted(exemplos.items()):
    print(f"- {casa} / {link}: testando 3 links")
    for u in random.sample(us, min(3, len(us))):
        print(f"  - {status(u)} · {u}")

# A lista oficial de passagens (SIGEPA) é lida da página da Câmara: confere se a leitura funciona na página real.
print("\n### Lista oficial de passagens (teste da leitura)\n")
for f in sorted(cache.glob("camara-cota-*.csv.zip"))[-1:]:
    rows = list(read_csv_file(f))
    nus = Counter((r.get("nuDeputadoId") or "").strip() for r in rows if (r.get("nuDeputadoId") or "").strip())
    ano = int(f.name.split("-")[-1].split(".")[0])
    for nu, _ in nus.most_common(2):
        for mes in (3, 6):
            u = LISTA_MES.format(nu=nu, mes=mes, ano=ano, sub=passagens.SIGEPA)
            h = _get_text(u)
            linhas = passagens.parse_lista(h or "")
            print(f"- deputado {nu}, {mes:02d}/{ano}: página {'ok' if h else 'sem resposta'}, {len(linhas)} bilhetes lidos, "
                  f"R$ {sum(x['valor'] for x in linhas):.2f}")
            for x in linhas[:2]:
                print(f"  - {x}")
