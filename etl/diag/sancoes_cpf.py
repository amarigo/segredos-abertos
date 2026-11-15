"""Diagnóstico temporário: onde o padrão de CPF aparece nas punições (sem mostrar dado nenhum)."""
import collections, datetime as dt, json, re, sys
from pathlib import Path
from sa_etl import sancoes as s
from sa_etl.validar import CPF_NO_TEXTO

hoje = dt.date.today()
cache = Path(sys.argv[1])
listas = {}
for cad in s.PORTAL_CADS:
    f = cache / "sancoes" / "portal" / f"{cad}.json"
    if f.exists():
        listas[cad] = json.loads(f.read_text())["linhas"]
for cad in s.TCU_CADS:
    try:
        listas[cad] = [r for r in (s.registro_tcu(cad, x) for x in s.ler_tcu(cad, hoje)) if r]
    except Exception as e:
        print(cad, "falhou", str(e)[:100])

def forma(t):
    t = re.sub(r"\d", "9", t)
    return re.sub(r"[A-Za-zÀ-ÿ]", "x", t) if not t.startswith("http") else t

cont = collections.Counter()
ex = {}
for cad, regs in listas.items():
    for r in regs:
        for k, v in s._publico(r, hoje).items():
            for item in (v if isinstance(v, list) else [v]):
                txt = str(item)
                m = CPF_NO_TEXTO.search(txt)
                if m:
                    cont[(cad, k)] += 1
                    ex.setdefault((cad, k), forma(txt[max(0, m.start() - 60):m.end() + 15]))
    print(cad, len(regs), "linhas")
for key, n in cont.most_common():
    print(key, n, "exemplo:", ex[key])
print("total", sum(cont.values()))
# rodada 2: com a correção
