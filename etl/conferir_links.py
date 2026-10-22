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
import requests  # noqa: E402

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
        r = requests.get(u, timeout=15, allow_redirects=True, stream=True, headers={"Accept": "*/*", "User-Agent": "segredos-abertos"})
        ct = r.headers.get("content-type", "")
        r.close()
        return f"{r.status_code} {ct[:30]}"
    except Exception as e:  # noqa: BLE001
        return f"erro {type(e).__name__}"


for (casa, link), us in sorted(exemplos.items()):
    print(f"- {casa} / {link}: testando até 3 links")
    for u in random.sample(us, min(3, len(us))):
        st = status(u)
        print(f"  - {st} · {u}")
        if st.startswith("erro"):
            break  # site fora do ar ou lento: não insiste

# Passagens lidas da lista oficial da Câmara (guardadas em cache pela coleta)
arqs = list((cache / "passagens").glob("*.json"))
bilhetes = [x for f in arqs for x in json.loads(f.read_text() or "[]")]
print(f"\n- Lista oficial de passagens: {len(arqs)} meses lidos, {len(bilhetes)} bilhetes, "
      f"R$ {sum(x['valor'] for x in bilhetes):,.2f}, {sum(1 for x in bilhetes if not x['numero'])} sem número")
for x in random.sample(bilhetes, min(3, len(bilhetes))):
    print(f"  - {x}")
