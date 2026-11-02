"""Monta o painel de análises para o GitHub Pages: index.html, tabelas CSV e um .zip com todas.

Uso (no GitHub Action, depois da coleta):
    python analises/publicar.py --nacional site/public/data --mg site/public-mg/data \\
        --eleicao eleicao2026/dados/tse --terras terras-raras/dados --saida site/dist/analises

O painel fica em https://amarigo.github.io/segredos-abertos/analises/
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tabelas import Dados, exportar  # noqa: E402

AQUI = Path(__file__).resolve().parent
# analises/painel.html é escrito sem <html>/<head> para servir também como página publicada no Claude,
# que coloca esse esqueleto sozinha. No GitHub Pages o esqueleto vem daqui.
ESQUELETO = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
</head>
<body>
{conteudo}
</body>
</html>
"""


def publicar(d: Dados, saida: Path) -> dict[str, int]:
    pasta = saida / "tabelas"
    contagem = exportar(d, pasta)
    (saida / "index.html").write_text(ESQUELETO.format(conteudo=(AQUI / "painel.html").read_text(encoding="utf-8")), encoding="utf-8")
    with zipfile.ZipFile(saida / "tabelas.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(pasta.iterdir()):
            z.write(p, p.name)
    return contagem


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Monta o painel de análises")
    ap.add_argument("--nacional", type=Path)
    ap.add_argument("--mg", type=Path)
    ap.add_argument("--eleicao", type=Path)
    ap.add_argument("--terras", type=Path)
    ap.add_argument("--saida", type=Path, required=True)
    a = ap.parse_args(argv)
    contagem = publicar(Dados(a.nacional, a.mg, a.eleicao, a.terras), a.saida)
    total = sum(contagem.values())
    print(f"Painel de análises: {len(contagem)} tabelas, {total:,} linhas em {a.saida}".replace(",", "."))
    vazias = [k for k, v in contagem.items() if v == 0]
    if vazias:
        print("Tabelas sem linhas nesta coleta: " + ", ".join(vazias))
    return 0


if __name__ == "__main__":
    sys.exit(main())
