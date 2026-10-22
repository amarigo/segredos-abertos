"""Resumo curto dos dados do Minas Nossa, para o fim do log e o resumo do GitHub Actions.

Uso: python mg/etl/resumo_mg.py site/public-mg/data
"""
import json
import sys
from pathlib import Path


def main(pasta: Path) -> None:
    if not (pasta / "meta.json").exists():
        print("### Minas Nossa\n\nSem dados de MG nesta execução.")
        return
    ler = lambda rel: json.loads((pasta / rel).read_text(encoding="utf-8"))  # noqa: E731
    meta = ler("meta.json")
    pols = ler("politicos.json")
    print("### Minas Nossa\n")
    print(f"- {sum(p['casa'] == 'camara' for p in pols)} deputados federais, {sum(p['casa'] == 'senado' for p in pols)} senadores, "
          f"{meta['contagens']['votacoes']} votações, {len(ler('empresas.json'))} empresas")
    for a in meta.get("avisos") or []:
        print(f"- aviso: {a}")
    for c in ler("cidades.json"):
        d = ler(f"cidades/{c['id']}.json")
        exe = {m["eleicao"]: f"{m['prefeito']['nome']} ({m['prefeito']['partido']}{'' if m['vice'] else ', sem vice'})" for m in d["executivo"]}
        print(f"\n**{d['nome']}**: prefeitos {sorted(exe)}; Câmara {sorted(c2['eleicao'] for c2 in d['camara'])} "
              f"(vagas {[c2['vagas'] for c2 in d['camara']]}); gerais {sorted(g['eleicao'] for g in d['gerais'])}\n")
        for ano, txt in sorted(exe.items()):
            print(f"- {ano}: {txt}")
        for a in d.get("avisos") or []:
            print(f"- aviso: {a}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
